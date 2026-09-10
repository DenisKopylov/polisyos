"""Public analytics literature module API."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._internal.validation import (
    ensure_confidence_interval,
    ensure_finite_numeric,
    ensure_unique_ids,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeSource,
    GraphType,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.artifacts.contracts import ArtifactID
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import LiteratureCausalPriorRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.context import ContextProfile
else:
    from polisyos.ir.analytics.context import ContextProfile


class ParameterType(str, Enum):
    """Parameter type public type."""

    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"
    ORDINAL = "ordinal"
    DISTRIBUTIONAL = "distributional"


class EvidenceStrength(str, Enum):
    """Evidence strength public type."""

    RCT = "rct"
    QUASI_NATURAL = "quasi_natural"
    QUASI_NATURAL_EVENT = "quasi_natural_event"
    META_ANALYSIS = "meta_analysis"
    PANEL_FE = "panel_fe"
    STRUCTURAL = "structural"
    OBSERVATIONAL = "observational"
    CROSS_SECTIONAL = "cross_sectional"
    THEORETICAL = "theoretical"
    UNKNOWN = "unknown"


class EvidenceStrengthOrigin(str, Enum):
    """How a parameter strength was produced, without conferring authority.

    Unmarked stored values are unresolved. Only a producer that observed its
    input can record supplied or declared_unknown; intake must not infer them.
    """

    NOT_SUPPLIED = "not_supplied"
    SUPPLIED = "supplied"
    DECLARED_UNKNOWN = "declared_unknown"
    NORMALIZER_FALLBACK = "normalizer_fallback"
    INTAKE_FALLBACK = "intake_fallback"
    INHERITED = "inherited"
    UNRESOLVED = "unresolved"


class CausalDirection(str, Enum):
    """Causal direction public type."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NULL = "null"
    MIXED = "mixed"
    AMBIGUOUS = "ambiguous"
    NON_LINEAR = "non_linear"


class SourceBasis(str, Enum):
    """Source basis public type."""

    FULLTEXT = "fulltext"
    ABSTRACT_ONLY = "abstract_only"


class ClaimVocabularyAxisStatus(str, Enum):
    """Establishment status for one typed claim-vocabulary axis."""

    NOT_ESTABLISHED = "not_established"
    CANDIDATE = "candidate"


class TextQuality(str, Enum):
    """Text quality public type."""

    STRUCTURED_FULLTEXT = "structured_fulltext"
    EXTRACTED_FULLTEXT = "extracted_fulltext"
    ABSTRACT_ONLY = "abstract_only"
    DEGRADED = "degraded"


class ClaimType(str, Enum):
    """Claim type public type."""

    CAUSAL_CLAIM = "causal_claim"
    CAUSAL_ASSERTION = "causal_assertion"
    ASSOCIATIVE = "associative"
    ASSOCIATION = "association"
    MECHANISM = "mechanism"
    DESCRIPTIVE = "descriptive"
    NORMATIVE = "normative"
    REVIEW_SUMMARY = "review_summary"
    UNCLEAR = "unclear"
    NOT_APPLICABLE = "not_applicable"


class ClaimExplicitness(str, Enum):
    """Claim explicitness public type."""

    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    UNCLEAR = "unclear"


class DesignFamily(str, Enum):
    """Design family public type."""

    RCT = "rct"
    IV = "iv"
    DID = "did"
    RDD = "rdd"
    SYNTHETIC_CONTROL = "synthetic_control"
    EVENT_STUDY = "event_study"
    QUASI_EXPERIMENTAL_OTHER = "quasi_experimental_other"
    QUASI_EXPERIMENTAL_DID = "quasi_experimental_did"
    QUASI_EXPERIMENTAL_RDD = "quasi_experimental_rdd"
    PANEL_FE = "panel_fe"
    OLS = "ols"
    OLS_CROSS_SECTIONAL = "ols_cross_sectional"
    META_ANALYSIS = "meta_analysis"
    REVIEW = "review"
    REVIEW_NARRATIVE = "review_narrative"
    REVIEW_META_ANALYSIS = "review_meta_analysis"
    THEORETICAL = "theoretical"
    STRUCTURAL_MODEL = "structural_model"
    TIME_SERIES_COINTEGRATION = "time_series_cointegration"
    UNCLEAR = "unclear"


class CausalCredibility(str, Enum):
    """Causal credibility public type."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NOT_CAUSAL = "not_causal"
    UNCLEAR = "unclear"


class LegacyFiveFieldClaimOccurrence(BaseModel):
    """Exact five-field legacy occurrence accepted by the absence adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cause: str
    effect: str
    direction: str
    strength: str
    mechanism: str


class VersionedClaimVocabularyEnvelope(BaseModel):
    """Strict v2 vocabulary sidecar for one causal-claim occurrence.

    The sidecar travels beside the original occurrence in the lossless claim
    transport and is revalidated at the common serialization/store boundary.
    It records candidate or absent vocabulary values; it confers no authority.
    Legacy occurrences enter only through the explicit absence adapter below.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    cause: str
    effect: str
    direction: str = ""
    mechanism: str = ""

    design_family_hint: DesignFamily | None = None
    design_family_hint_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    evidence_strength: EvidenceStrength | None = None
    evidence_strength_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    claim_extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    claim_extraction_confidence_status: ClaimVocabularyAxisStatus = (
        ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    )
    source_basis: SourceBasis | None = None
    source_basis_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.NOT_ESTABLISHED

    legacy_strength_label: str | None = None
    record_extraction_mode: str | None = None

    @model_validator(mode="after")
    def _validate_axis_statuses(self) -> VersionedClaimVocabularyEnvelope:
        """Require each typed axis to declare whether its value is established."""

        axes = (
            ("design_family_hint", self.design_family_hint, self.design_family_hint_status),
            ("evidence_strength", self.evidence_strength, self.evidence_strength_status),
            (
                "claim_extraction_confidence",
                self.claim_extraction_confidence,
                self.claim_extraction_confidence_status,
            ),
            ("source_basis", self.source_basis, self.source_basis_status),
        )
        for name, value, status in axes:
            if value is None and status is not ClaimVocabularyAxisStatus.NOT_ESTABLISHED:
                raise ValueError(f"{name} must be absent when its status is not_established")
            if value is not None and status is not ClaimVocabularyAxisStatus.CANDIDATE:
                raise ValueError(f"{name} requires candidate status when present")
        return self


def adapt_legacy_claim_occurrence_as_v2_absence(
    occurrence: Mapping[str, object],
    *,
    record_extraction_mode: str | None = None,
) -> VersionedClaimVocabularyEnvelope:
    """Retain a legacy occurrence without inferring any typed v2 axis.

    The adapter is intentionally one-way and only observes occurrence fields
    plus an optional record extraction-mode observation. It cannot receive
    parent-paper design, record confidence, source basis, or trust metadata.
    """

    legacy = LegacyFiveFieldClaimOccurrence.model_validate(occurrence)
    return VersionedClaimVocabularyEnvelope(
        cause=legacy.cause,
        effect=legacy.effect,
        direction=legacy.direction,
        mechanism=legacy.mechanism,
        legacy_strength_label=legacy.strength,
        record_extraction_mode=record_extraction_mode,
    )


class RiskOfBias(str, Enum):
    """Risk of bias public type."""

    LOW = "low"
    MODERATE = "moderate"
    SERIOUS = "serious"
    CRITICAL = "critical"
    UNCLEAR = "unclear"


class SupportStatus(str, Enum):
    """Support status public type."""

    SUPPORTED = "supported"
    MIXED = "mixed"
    COUNTEREVIDENCE = "counterevidence"
    INSUFFICIENT = "insufficient"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class PaperKind(str, Enum):
    """Paper kind public type."""

    EMPIRICAL_CAUSAL = "empirical_causal"
    CONTEXT_CHARACTERIZATION = "context_characterization"
    HETEROGENEITY_ANALYSIS = "heterogeneity_analysis"
    REVIEW_SYSTEMATIC = "review_systematic"
    THEORETICAL = "theoretical"
    DESCRIPTIVE = "descriptive"
    MIXED = "mixed"


class EvidenceSpan(BaseModel):
    """Evidence span public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str = ""
    section: str = ""
    text: str
    source_ref: str = ""
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    content_sha256: str = ""
    sentence_index: int | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_offsets(self) -> EvidenceSpan:
        if self.start_char is not None and self.end_char is not None:
            if self.end_char < self.start_char:
                raise ValueError("end_char must be >= start_char")
        return self


class OpenAlexWorkText(BaseModel):
    """OpenAlex work source text used for span dereference and claim extraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    openalex_id: str
    title: str = ""
    doi: str = ""
    year: int | None = None
    cited_by_count: int = 0
    abstract_text: str = ""
    source_text: str = ""
    content_sha256: str = ""
    raw_work: dict[str, Any] = Field(default_factory=dict)

    def require_source_content(self) -> None:
        """Require complete agreement with the selected raw OpenAlex source bytes."""

        _require_openalex_source_content(self)

    @classmethod
    def from_openalex_work(cls, payload: dict[str, Any]) -> OpenAlexWorkText:
        """Build source text from one real OpenAlex work payload."""

        title = str(payload.get("display_name") or payload.get("title") or "").strip()
        abstract = _reconstruct_openalex_abstract(payload.get("abstract_inverted_index"))
        source_text = "\n".join(part for part in (title, abstract) if part).strip()
        return cls(
            openalex_id=str(payload.get("id") or "").strip(),
            title=title,
            doi=str(payload.get("doi") or "").strip(),
            year=int(payload["publication_year"])
            if isinstance(payload.get("publication_year"), int)
            else None,
            cited_by_count=int(payload.get("cited_by_count") or 0),
            abstract_text=abstract,
            source_text=source_text,
            content_sha256=_sha256_text(source_text),
            raw_work=dict(payload),
        )


class SpanGroundingResult(BaseModel):
    """Result of resolving and semantically checking a claim span."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    openalex_id: str
    status: Literal[
        "validated_supporting",
        "rejected_missing_span",
        "rejected_source_mismatch",
        "rejected_hash_mismatch",
        "rejected_unresolved_span",
        "rejected_non_supporting",
    ]
    authority_tier: Literal["design_tier_l2", "candidate_unverified"]
    support_score: float = Field(default=0.0, ge=0.0, le=1.0)
    span_id: str = ""
    span_start: int | None = None
    span_end: int | None = None
    grounding_ref: str = ""
    reason: str = ""


class ClaimSpanGoldRecord(BaseModel):
    """Human-labeled OpenAlex claim/span gold record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label_id: str
    openalex_id: str
    title: str = ""
    query: str
    claim_text: str
    treatment_or_cause: str
    effect: str
    claim_direction: str
    gold_span_text: str
    expected_supported: bool = True
    source_fixture: str


class ClaimSpanGoldSet(BaseModel):
    """Governed gold set for measuring OpenAlex claim/span extraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    gy_lifecycle_marker: str = ""
    label_owner: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    records: list[ClaimSpanGoldRecord] = Field(default_factory=list)


class LegacyExtractorAccuracyReportV1(BaseModel):
    """Measured extractor precision/recall against a governed gold set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "policyos.policy_design_case.layer3_gy.openalex_accuracy.v1"
    measurement_basis: Literal["human_labeled_gold_set"] = "human_labeled_gold_set"
    gold_record_count: int = 0
    predicted_claim_count: int = 0
    true_positive_count: int = 0
    false_positive_count: int = 0
    false_negative_count: int = 0
    true_negative_count: int = 0
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    recall: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_label_ids: list[str] = Field(default_factory=list)


class OpenAlexSourceBindingResult(BaseModel):
    """Custody of a candidate in selected source bytes, never semantic support."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    claim_id: str
    openalex_id: str
    status: Literal["source_bound_candidate", "refused"]
    authority_tier: Literal["candidate_unverified"] = "candidate_unverified"
    semantic_support: Literal["not_established"] = "not_established"
    source_snapshot_authenticity: Literal["not_established"] = "not_established"
    predicate_basis: Literal["recomputed"] = "recomputed"
    span_start: int | None = None
    span_end: int | None = None
    grounding_ref: str = ""
    reason: str = ""


class OpenAlexRecordedSource(BaseModel):
    """One parsed recorded response bound to the exact bytes read by its owner.

    Recording metadata is source-supplied custody context, not independent
    authentication of OpenAlex or scientific support for extracted claims.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    payload: dict[str, Any]
    query: str
    captured_at: str
    content_sha256: str


class OpenAlexExtractionCase(BaseModel):
    """One declared work/query in an engineering extraction population."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    case_id: str
    openalex_id: str
    query: str
    source_ref: str
    recorded_at: str | None
    work: OpenAlexWorkText | None
    source_error: str | None = None
    gold_reviewed_at: str | None = None


class OpenAlexExtractionObservation(BaseModel):
    """Complete attempted extraction, including missing or rejected predictions."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    case_id: str
    openalex_id: str
    query: str
    source_ref: str
    recorded_at: str | None
    gold_reviewed_at: str | None = None
    source_content_sha256: str | None
    disposition: Literal["extracted", "source_unavailable", "extractor_failed"]
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    constructed_negatives: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""


class ExtractorAccuracyReport(BaseModel):
    """Extractor engineering evidence; scientific accuracy awaits appointment."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["policyos.policy_design_case.layer3_gy.openalex_accuracy.v2"] = (
        "policyos.policy_design_case.layer3_gy.openalex_accuracy.v2"
    )
    measurement_basis: Literal["extractor_execution_and_constructed_negatives"] = (
        "extractor_execution_and_constructed_negatives"
    )
    accuracy_status: Literal["withheld_pending_adjudicator_appointment"] = (
        "withheld_pending_adjudicator_appointment"
    )
    standing_rule_ref: Literal["correspondence-acceptance-standing-rule"] = (
        "correspondence-acceptance-standing-rule"
    )
    precision: None = None
    recall: None = None
    observations: list[OpenAlexExtractionObservation] = Field(default_factory=list)


class IdentificationStrategy(BaseModel):
    """How a causal effect was identified (instrument, design assumptions, etc.)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identification_method: str = ""
    instrument: str = ""
    exclusion_restrictions: list[str] = Field(default_factory=list)
    design_assumptions: list[str] = Field(default_factory=list)
    identification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class HeterogeneityResult(BaseModel):
    """Result of a heterogeneity/moderation test within a single study."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    moderator: str
    dimension: str = ""
    finding: str = ""
    interaction_coefficient: float | None = None
    interaction_pvalue: float | None = None
    subgroup_effects: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class UncertaintyBudget(BaseModel):
    """Three-axis uncertainty decomposition for a causal estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conflict_residual: float = Field(default=0.0, ge=0.0, le=1.0)
    sampling_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    graph_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def total(self) -> float:
        return min(1.0, self.conflict_residual + self.sampling_uncertainty + self.graph_uncertainty)


class ContextAttribute(BaseModel):
    """A context attribute extracted from literature (Track B)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attribute_name: str
    canonical_name: str = ""
    value: float | None = None
    value_qualitative: str | None = None
    unit: str | None = None
    country_codes: list[str] = Field(default_factory=list)
    time_period: str = ""
    measurement_method: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)


class ModerationEdge(BaseModel):
    """A context variable that moderates a causal edge (Track C)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_cause: str
    base_effect: str
    moderator: str
    base_claim_id: str | None = None
    direction_of_moderation: str = ""
    quantitative_interaction: float | None = None
    interaction_pvalue: float | None = None
    evidence_count: int = 1
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    match_quality: str = ""
    alignment_source: str = ""
    source_openalex_ids: list[str] = Field(default_factory=list)
    evidence_text: str = ""


class EvidenceParameter(BaseModel):
    """Evidence parameter public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    display_name: str = ""
    parameter_type: ParameterType = ParameterType.QUANTITATIVE

    value: float | None = None
    value_range: tuple[float, float] | None = None
    value_qualitative: str | None = None
    confidence_interval: tuple[float, float] | None = None
    std_error: float | None = None
    unit: str | None = None

    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    evidence_strength_origin: EvidenceStrengthOrigin = EvidenceStrengthOrigin.NOT_SUPPLIED
    geographic_scope: str = ""
    time_period: str = ""
    aggregation_level: str = ""

    transferability: str = "unknown"
    transfer_conditions: list[str] = Field(default_factory=list)
    heterogeneity_note: str | None = None
    subgroup_estimates: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _retain_unresolved_strength_origin(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "evidence_strength_origin" not in value and "evidence_strength" in value:
            return {**value, "evidence_strength_origin": EvidenceStrengthOrigin.UNRESOLVED}
        if "evidence_strength" not in value and value.get("evidence_strength_origin") not in {
            None,
            EvidenceStrengthOrigin.NOT_SUPPLIED,
            EvidenceStrengthOrigin.UNRESOLVED,
        }:
            raise ValueError("A strength origin cannot record a value that was not supplied")
        return value

    @model_validator(mode="after")
    def _validate_value_present(self) -> EvidenceParameter:
        unknown_only = {
            EvidenceStrengthOrigin.NOT_SUPPLIED,
            EvidenceStrengthOrigin.DECLARED_UNKNOWN,
            EvidenceStrengthOrigin.NORMALIZER_FALLBACK,
            EvidenceStrengthOrigin.INTAKE_FALLBACK,
        }
        if (
            self.evidence_strength_origin in unknown_only
            and self.evidence_strength != EvidenceStrength.UNKNOWN
        ):
            raise ValueError("This strength origin requires an unknown value")
        if (
            self.evidence_strength_origin == EvidenceStrengthOrigin.SUPPLIED
            and self.evidence_strength == EvidenceStrength.UNKNOWN
        ):
            raise ValueError("An explicit unknown judgment requires declared_unknown origin")
        if self.value is None and self.value_range is None and self.value_qualitative is None:
            raise ValueError("At least one of value, value_range, value_qualitative is required")
        if self.value is not None:
            ensure_finite_numeric(self.value, field_name="value")
        if self.value_range is not None:
            ensure_confidence_interval(self.value_range, label="value_range")
        if self.confidence_interval is not None:
            ensure_confidence_interval(self.confidence_interval, label="confidence_interval")
        if self.std_error is not None:
            ensure_finite_numeric(self.std_error, field_name="std_error")
            if self.std_error < 0.0:
                raise ValueError("std_error must be >= 0")
        for subgroup_name, subgroup_estimate in self.subgroup_estimates.items():
            ensure_finite_numeric(
                subgroup_estimate,
                field_name=f"subgroup_estimates.{subgroup_name}",
            )
        return self


class CausalClaim(BaseModel):
    """Causal claim public type.

    Derived aliases are resolved in a payload-normalization step so validated
    instances are no longer mutated by validators.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = ""
    cause_variable: str
    effect_variable: str
    direction: CausalDirection = CausalDirection.MIXED
    claim_text: str = ""
    claim_type: ClaimType = ClaimType.UNCLEAR
    claim_explicitness: ClaimExplicitness = ClaimExplicitness.UNCLEAR
    design_family_hint: DesignFamily = DesignFamily.UNCLEAR
    magnitude_qualitative: str | None = None
    effect_size: float | None = None
    evidence_strength: EvidenceStrength = EvidenceStrength.UNKNOWN
    scope_conditions: list[str] = Field(default_factory=list)
    counterevidence_notes: str = ""
    supporting_spans: list[EvidenceSpan] = Field(default_factory=list)
    method_spans: list[EvidenceSpan] = Field(default_factory=list)
    supporting_span_ids: list[str] = Field(default_factory=list)
    method_span_ids: list[str] = Field(default_factory=list)
    source_basis: SourceBasis = SourceBasis.FULLTEXT
    claim_extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extraction_warnings: list[str] = Field(default_factory=list)
    strong_design_evidence: bool = False
    publish_to_graph: bool = False
    publish_blockers: list[str] = Field(default_factory=list)
    design_quality_tier: int | None = Field(default=None, ge=1, le=4)
    span_contamination_detected: bool = False

    # v1.4: transportability fields
    identification_strategy: IdentificationStrategy | None = None
    uncertainty_budget: UncertaintyBudget | None = None

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_claim(cls, data: object) -> object:
        return cls.normalize_payload(data)

    @classmethod
    def normalize_payload(cls, data: object) -> object:
        """Return a claim payload with legacy aliases and span IDs normalized."""

        return _normalize_causal_claim_payload(data)

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> CausalClaim:
        """Construct a causal claim through the explicit compatibility normalizer."""

        return cls.model_validate(cls.normalize_payload(data))

    @model_validator(mode="after")
    def _validate_claim(self) -> CausalClaim:
        if self.effect_size is not None:
            ensure_finite_numeric(self.effect_size, field_name="effect_size")
        ensure_unique_ids(
            self.supporting_span_ids,
            key_fn=lambda item: item,
            label="supporting_span_id",
        )
        ensure_unique_ids(
            self.method_span_ids,
            key_fn=lambda item: item,
            label="method_span_id",
        )
        return self


class Mechanism(BaseModel):
    """Mechanism public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    mediating_variables: list[str] = Field(default_factory=list)
    evidence_type: str = ""
    theoretical_framework: str | None = None


class BoundaryCondition(BaseModel):
    """Boundary condition public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str = ""
    condition_type: str = ""
    required_value: str | float | None = None
    violated_by: list[str] = Field(default_factory=list)
    consequence_if_violated: str = ""

    # legacy fields (v1.0)
    operator: str = ""
    threshold_value: str = ""
    scope_text: str = ""
    confidence: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_boundary(cls, data: object) -> object:
        return cls.normalize_payload(data)

    @classmethod
    def normalize_payload(cls, data: object) -> object:
        """Return a boundary-condition payload with legacy threshold aliases resolved."""

        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("condition_type"):
            payload["condition_type"] = "threshold" if payload.get("operator") else "categorical"
        if payload.get("required_value") is None:
            if payload.get("threshold_value") not in (None, ""):
                payload["required_value"] = str(payload.get("threshold_value"))
            elif payload.get("scope_text"):
                payload["required_value"] = str(payload.get("scope_text"))
        if not payload.get("consequence_if_violated"):
            payload["consequence_if_violated"] = "effect transportability may fail"
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> BoundaryCondition:
        """Construct a boundary condition through the explicit compatibility normalizer."""

        return cls.model_validate(cls.normalize_payload(data))


class ArticleExtractionResult(BaseModel):
    """Primary IR contract for literature extraction pipeline.

    Legacy field mirrors (`year` / `publication_year`) stay supported, but they
    are synchronized before instantiation instead of via instance mutation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.5"
    openalex_id: str
    doi: str = ""
    title: str

    # v1.1 canonical field
    year: int | None = None
    # v1.0 compatibility
    publication_year: int | None = None

    cited_by_count: int = 0

    methodology: str = ""
    methodology_enum: EvidenceStrength = EvidenceStrength.UNKNOWN
    paper_relevance: bool = True
    paper_relevance_reason: str = ""
    sample_size: int | None = None
    source_basis: SourceBasis = SourceBasis.FULLTEXT
    text_quality: TextQuality = TextQuality.EXTRACTED_FULLTEXT
    supporting_spans: list[EvidenceSpan] = Field(default_factory=list)
    method_spans: list[EvidenceSpan] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)

    empirical_parameters: list[EvidenceParameter] = Field(default_factory=list)
    causal_claims: list[CausalClaim] = Field(default_factory=list)
    mechanisms: list[Mechanism] = Field(default_factory=list)
    boundary_conditions: list[BoundaryCondition] = Field(default_factory=list)
    citation_summary: str = ""

    extraction_model: str
    extraction_timestamp: str
    extraction_confidence: float
    provider_finish_reason: str = ""
    provider_latency_ms: float = 0.0
    truncated_output: bool = False
    llm_error_class: str = ""

    source_context: ContextProfile | None = None

    # v1.4: three-track extraction fields
    paper_kind: PaperKind = PaperKind.EMPIRICAL_CAUSAL
    heterogeneity_results: list[HeterogeneityResult] = Field(default_factory=list)
    external_validity_assessment: str = ""
    context_attributes: list[ContextAttribute] = Field(default_factory=list)
    moderation_edges: list[ModerationEdge] = Field(default_factory=list)
    reconciliation_diagnostics: dict[str, Any] = Field(default_factory=dict)

    screening_cost_usd: float = 0.0
    extraction_cost_usd: float = 0.0
    token_count_prompt: int = 0
    token_count_completion: int = 0

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_payload(cls, data: object) -> object:
        return cls.normalize_payload(data)

    @classmethod
    def normalize_payload(cls, data: object) -> object:
        """Return an article-extraction payload with versioned aliases normalized."""

        return _normalize_article_extraction_payload(data)

    @classmethod
    def from_payload(cls, data: dict[str, Any]) -> ArticleExtractionResult:
        """Construct an article extraction result via explicit compatibility rules."""

        return cls.model_validate(cls.normalize_payload(data))

    @model_validator(mode="after")
    def _validate_confidence(self) -> ArticleExtractionResult:
        if not (0.0 <= self.extraction_confidence <= 1.0):
            raise ValueError(
                f"extraction_confidence must be [0,1], got {self.extraction_confidence}"
            )
        ensure_finite_numeric(self.provider_latency_ms, field_name="provider_latency_ms")
        if self.provider_latency_ms < 0.0:
            raise ValueError("provider_latency_ms must be >= 0")
        ensure_finite_numeric(self.screening_cost_usd, field_name="screening_cost_usd")
        ensure_finite_numeric(self.extraction_cost_usd, field_name="extraction_cost_usd")
        if self.screening_cost_usd < 0.0 or self.extraction_cost_usd < 0.0:
            raise ValueError("screening_cost_usd and extraction_cost_usd must be >= 0")
        if self.token_count_prompt < 0 or self.token_count_completion < 0:
            raise ValueError("token counts must be >= 0")
        return self


class ClaimAdjudicationInputItem(BaseModel):
    """Authority-neutral claim evidence supplied to Scientist for adjudication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    openalex_id: str = Field(min_length=1)
    title: str = ""
    methodology: str = ""
    methodology_enum: EvidenceStrength = EvidenceStrength.UNKNOWN
    source_basis: SourceBasis = SourceBasis.FULLTEXT
    text_quality: TextQuality = TextQuality.EXTRACTED_FULLTEXT
    claim_text: str = ""
    cause_variable: str = Field(min_length=1)
    effect_variable: str = Field(min_length=1)
    direction: CausalDirection = CausalDirection.MIXED
    claim_type_hint: ClaimType = ClaimType.UNCLEAR
    claim_explicitness: ClaimExplicitness = ClaimExplicitness.UNCLEAR
    design_family_hint: DesignFamily = DesignFamily.UNCLEAR
    effect_size: float | None = None
    scope_conditions: list[str] = Field(default_factory=list)
    supporting_spans: list[EvidenceSpan] = Field(default_factory=list)
    method_spans: list[EvidenceSpan] = Field(default_factory=list)
    extraction_model: str = ""
    extraction_timestamp: str = ""
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    intra_paper_contradiction: bool = False

    @model_validator(mode="after")
    def _validate_effect_size(self) -> ClaimAdjudicationInputItem:
        if self.effect_size is not None:
            ensure_finite_numeric(self.effect_size, field_name="effect_size")
        return self


class ClaimAdjudicationInputBatch(BaseModel):
    """Immutable raw-input denominator for one claim-adjudication run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    source_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    retraction_artifact_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    items: list[ClaimAdjudicationInputItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_claims(self) -> ClaimAdjudicationInputBatch:
        ensure_unique_ids(
            self.items,
            key_fn=lambda item: item.claim_id,
            label="claim_id",
        )
        return self


class ClaimAdjudicationResult(BaseModel):
    """Claim-level causal adjudication contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    openalex_id: str
    cause_variable: str
    effect_variable: str
    source_basis: SourceBasis = SourceBasis.FULLTEXT
    paper_asserts_causality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_type: ClaimType = ClaimType.ASSOCIATION
    design_family: DesignFamily = DesignFamily.UNCLEAR
    causal_credibility: CausalCredibility = CausalCredibility.UNCLEAR
    risk_of_bias: RiskOfBias = RiskOfBias.UNCLEAR
    support_status: SupportStatus = SupportStatus.INSUFFICIENT
    claim_validity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    adjudication_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    publishable_edge: bool = False
    adjudication_notes: str = ""
    consensus_passes: int = Field(default=1, ge=1)
    consensus_stability: float = Field(default=1.0, ge=0.0, le=1.0)
    claim_type_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    design_family_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    direction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    intra_paper_contradiction: bool = False


class AdmittedClaimAdjudicationBatch(BaseModel):
    """Scientist-signed claim publishability results and their admitted basis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    rule_version: Literal["claim-adjudication-admission.v1"] = "claim-adjudication-admission.v1"
    raw_input_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evaluation_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    champion_pointer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    admission_predicate: Literal["independently_reconciled"] = "independently_reconciled"
    authoritative_for: tuple[Literal["academic_claim_edge_publishability"]] = (
        "academic_claim_edge_publishability",
    )
    may_not_use_for: tuple[
        Literal["method_validity"],
        Literal["governance_admissibility"],
    ] = (
        "method_validity",
        "governance_admissibility",
    )
    input_claim_ids: list[str] = Field(default_factory=list)
    results: list[ClaimAdjudicationResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_exact_claim_denominator(self) -> AdmittedClaimAdjudicationBatch:
        ensure_unique_ids(
            self.input_claim_ids,
            key_fn=lambda item: item,
            label="input_claim_id",
        )
        ensure_unique_ids(
            self.results,
            key_fn=lambda item: item.claim_id,
            label="result_claim_id",
        )
        result_ids = [item.claim_id for item in self.results]
        if result_ids != self.input_claim_ids:
            raise ValueError("results must preserve the exact ordered input claim denominator")
        return self


class LiteratureEdgePrior(BaseModel):
    """Literature edge prior public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    src: str
    dst: str
    confidence: float = Field(ge=0.0, le=1.0)
    n_articles: int = Field(default=0, ge=0)
    evidence_strength: EvidenceStrength | None = EvidenceStrength.UNKNOWN
    evidence_strength_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.CANDIDATE
    article_refs: list[str] = Field(default_factory=list)
    scope_conditions: list[str] = Field(default_factory=list)
    direction: CausalDirection = CausalDirection.MIXED
    meta_effect_size: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_evidence_strength_status(self) -> LiteratureEdgePrior:
        if self.evidence_strength is None:
            if self.evidence_strength_status is not ClaimVocabularyAxisStatus.NOT_ESTABLISHED:
                raise ValueError(
                    "evidence_strength must be absent when its status is not_established"
                )
        elif self.evidence_strength_status is not ClaimVocabularyAxisStatus.CANDIDATE:
            raise ValueError("evidence_strength requires candidate status when present")
        return self


class ReconciliationDiagnostics(BaseModel):
    """Reconciliation diagnostics public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cyclic_inconsistency_norm: float = Field(default=0.0, ge=0.0)
    irreducible_conflict_norm: float = Field(default=0.0, ge=0.0)
    gradient_norm: float = Field(default=0.0, ge=0.0)
    curl_norm: float = Field(default=0.0, ge=0.0)
    harmonic_norm: float = Field(default=0.0, ge=0.0)
    diagnostics_truncated: bool = False
    truncation_reason: str | None = None
    d0_shape: tuple[int, int] = (0, 0)
    d1_shape: tuple[int, int] = (0, 0)
    delta0_shape: tuple[int, int] = (0, 0)
    delta1_shape: tuple[int, int] = (0, 0)
    n_components: int = 0
    n_sources: int = 0
    n_edges: int = 0
    n_triangles: int = 0
    operators: dict[str, Any] = Field(default_factory=dict)


class EnvironmentAuditReport(BaseModel):
    """Environment audit report data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok", "warning", "skipped", "degraded"] = "skipped"
    n_environments: int = Field(default=0, ge=0)
    ks_passed: bool | None = None
    ks_rejected_variables: list[int] = Field(default_factory=list)
    ks_p_values: dict[str, float] = Field(default_factory=dict)
    icp_run: bool = False
    icp_passed: bool | None = None
    invariant_features: list[int] = Field(default_factory=list)
    variant_features: list[int] = Field(default_factory=list)
    icp_p_values: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiteratureCausalPrior(BaseModel):
    """Literature causal prior public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    edges: list[LiteratureEdgePrior] = Field(default_factory=list)
    skg_version_id: int | None = None
    skg_snapshot_ref: str | None = None
    environment_audit: EnvironmentAuditReport | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_causal_graph_model(
        self,
        *,
        nodes: list[str] | None = None,
        min_confidence: float = 0.0,
    ) -> CausalGraphModel:
        node_set: set[str] = set(nodes or [])
        graph_edges: list[CausalEdge] = []
        for edge in self.edges:
            if edge.confidence < min_confidence:
                continue
            node_set.add(edge.src)
            node_set.add(edge.dst)
            edge_metadata = dict(edge.metadata)
            edge_metadata.setdefault(
                "evidence_strength",
                edge.evidence_strength.value if edge.evidence_strength is not None else None,
            )
            edge_metadata.setdefault(
                "evidence_strength_status", edge.evidence_strength_status.value
            )
            edge_metadata.setdefault("scope_conditions", list(edge.scope_conditions))
            edge_metadata.setdefault("direction", edge.direction.value)
            if edge.meta_effect_size is not None:
                edge_metadata.setdefault("meta_effect_size", float(edge.meta_effect_size))
            graph_edges.append(
                CausalEdge(
                    src=edge.src,
                    dst=edge.dst,
                    sources=[EdgeSource.LITERATURE],
                    literature_confidence=edge.confidence,
                    combined_confidence=edge.confidence,
                    evidence_refs=list(edge.article_refs),
                    metadata=edge_metadata,
                )
            )

        return CausalGraphModel(
            graph_type=GraphType.CPDAG,
            nodes=sorted(node_set),
            edges=graph_edges,
            discovery_method="literature_prior",
            skg_version_id=self.skg_version_id,
            metadata={
                "skg_snapshot_ref": self.skg_snapshot_ref,
                "literature_prior_edge_count": len(graph_edges),
                **(
                    {
                        "environment_audit_status": self.environment_audit.status,
                        "environment_audit_n_environments": self.environment_audit.n_environments,
                    }
                    if self.environment_audit is not None
                    else {}
                ),
                **self.metadata,
            },
        )


def extract_span_grounded_claims_from_openalex_work(
    work: OpenAlexWorkText,
    *,
    query: str,
    max_claims: int = 3,
    span_support_client: Any | None = None,
) -> list[CausalClaim]:
    """Extract source-bound candidates without assigning semantic authority.

    An explicitly supplied semantic client retains the existing optional filter.
    Current candidate extraction and its instrument do not request that authority.
    """

    _require_openalex_source_content(work)
    candidates = _extract_openalex_source_candidates(work, query=query, max_claims=max_claims)
    if span_support_client is None:
        return candidates
    return [
        claim
        for claim in candidates
        if validate_causal_claim_span_grounding(
            work, claim, span_support_client=span_support_client
        ).status
        == "validated_supporting"
    ]


def _require_openalex_source_content(work: OpenAlexWorkText) -> None:
    rebuilt = OpenAlexWorkText.from_openalex_work(work.raw_work)
    if not re.fullmatch(r"https://openalex\.org/W[0-9]+", rebuilt.openalex_id):
        raise ValueError("openalex_source_identity_invalid")
    abstract = work.raw_work.get("abstract_inverted_index")
    if not isinstance(abstract, dict) or not abstract:
        raise ValueError("openalex_source_abstract_missing")
    positions = []
    for token, token_positions in abstract.items():
        if not isinstance(token, str) or not token or not isinstance(token_positions, list):
            raise ValueError("openalex_source_abstract_invalid")
        if any(type(position) is not int or position < 0 for position in token_positions):
            raise ValueError("openalex_source_abstract_invalid")
        positions.extend(token_positions)
    if len(set(positions)) != len(positions) or sorted(positions) != list(range(len(positions))):
        raise ValueError("openalex_source_abstract_positions_invalid")
    if rebuilt.model_dump(mode="json") != work.model_dump(mode="json"):
        raise ValueError("openalex_source_content_mismatch")
    if work.raw_work.get("is_retracted") is True:
        raise ValueError("openalex_source_retracted")


def validate_openalex_source_bound_candidate(
    work: OpenAlexWorkText,
    claim: CausalClaim,
    *,
    query: str,
    max_claims: int = 3,
) -> OpenAlexSourceBindingResult:
    """Rederive the complete candidate from its selected raw source and query."""

    try:
        _require_openalex_source_content(work)
        checked = CausalClaim.model_validate_json(claim.model_dump_json())
        if checked.model_dump(mode="json") != claim.model_dump(mode="json"):
            raise ValueError("openalex_candidate_typed_content_mismatch")
        expected = _extract_openalex_source_candidates(work, query=query, max_claims=max_claims)
        if not any(
            checked.model_dump(mode="json") == row.model_dump(mode="json") for row in expected
        ):
            raise ValueError("openalex_candidate_extractor_content_mismatch")
        span = checked.supporting_spans[0]
        resolved = _resolve_span(work.source_text, span)
        if resolved is None:
            raise ValueError("openalex_candidate_span_unresolved")
        start, end, _ = resolved
    except (ValueError, TypeError, AttributeError, IndexError) as exc:
        return OpenAlexSourceBindingResult(
            claim_id=str(getattr(claim, "claim_id", "")),
            openalex_id=work.openalex_id,
            status="refused",
            reason=str(exc),
        )
    return OpenAlexSourceBindingResult(
        claim_id=claim.claim_id,
        openalex_id=work.openalex_id,
        status="source_bound_candidate",
        span_start=start,
        span_end=end,
        grounding_ref=f"openalex-source-bound://{work.content_sha256}/{claim.claim_id}",
    )


def _extract_openalex_source_candidates(
    work: OpenAlexWorkText,
    *,
    query: str,
    max_claims: int = 3,
) -> list[CausalClaim]:
    """Extract conservative candidate claims from real OpenAlex source text.

    The extractor is intentionally rule-based and source-bound: it only emits a
    claim when the supporting span is a sentence that dereferences to the work
    text. Accuracy is measured separately by `evaluate_openalex_claim_extractor_accuracy`.
    """

    sentences = _split_sentences(work.abstract_text or work.source_text)
    scored: list[tuple[float, int, str]] = []
    query_terms = _meaningful_terms(query)
    for index, sentence in enumerate(sentences):
        normalized = _normalize_ws(sentence)
        if not normalized:
            continue
        score = _claim_sentence_score(normalized, query_terms)
        if score <= 0.0:
            continue
        scored.append((score, index, normalized))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))

    claims: list[CausalClaim] = []
    seen_spans: set[str] = set()
    for score, sentence_index, sentence in scored:
        if sentence in seen_spans:
            continue
        seen_spans.add(sentence)
        start = work.source_text.find(sentence)
        if start < 0:
            start = work.source_text.find(_denormalize_apostrophe(sentence))
        end = start + len(sentence) if start >= 0 else None
        cause, effect = _infer_cause_effect(sentence, query=query)
        direction = _infer_causal_direction(sentence)
        claim_id = _stable_claim_id(work.openalex_id, sentence, cause, effect)
        span = EvidenceSpan(
            span_id=f"{claim_id}.support.1",
            section="abstract",
            text=sentence,
            source_ref=work.openalex_id,
            start_char=start if start >= 0 else None,
            end_char=end,
            content_sha256=work.content_sha256,
            sentence_index=sentence_index,
            score=min(1.0, score),
        )
        claim = CausalClaim(
            claim_id=claim_id,
            cause_variable=cause,
            effect_variable=effect,
            direction=direction,
            claim_text=_claim_text_for_span(sentence, cause=cause, effect=effect),
            claim_type=ClaimType.CAUSAL_ASSERTION,
            claim_explicitness=ClaimExplicitness.EXPLICIT,
            design_family_hint=_infer_design_family(sentence),
            evidence_strength=_infer_evidence_strength(sentence),
            supporting_spans=[span],
            supporting_span_ids=[span.span_id],
            source_basis=SourceBasis.ABSTRACT_ONLY,
            claim_extraction_confidence=round(min(0.95, max(0.1, score)), 4),
            design_quality_tier=_design_tier_for_sentence(sentence),
            publish_to_graph=False,
        )
        claims.append(claim)
        if len(claims) >= max_claims:
            break
    return claims


def validate_causal_claim_span_grounding(
    work: OpenAlexWorkText,
    claim: CausalClaim,
    *,
    span_support_client: Any | None = None,
) -> SpanGroundingResult:
    """Resolve a claim span to OpenAlex source text and require semantic support."""

    span = claim.supporting_spans[0] if claim.supporting_spans else None
    if span is None:
        return _span_grounding_result(
            claim,
            work,
            status="rejected_missing_span",
            reason="claim has no supporting span",
        )
    if span.source_ref and span.source_ref != work.openalex_id:
        return _span_grounding_result(
            claim,
            work,
            status="rejected_source_mismatch",
            span=span,
            reason="span source_ref does not match OpenAlex work",
        )
    if span.content_sha256 and span.content_sha256 != work.content_sha256:
        return _span_grounding_result(
            claim,
            work,
            status="rejected_hash_mismatch",
            span=span,
            reason="span content hash does not match OpenAlex source text",
        )

    resolved = _resolve_span(work.source_text, span)
    if resolved is None:
        return _span_grounding_result(
            claim,
            work,
            status="rejected_unresolved_span",
            span=span,
            reason="span text and offsets do not dereference to source text",
        )
    start, end, resolved_text = resolved
    entailment = _evaluate_span_claim_entailment(
        claim=_claim_entailment_payload(claim, work=work, span=span),
        evidence=_span_entailment_payload(work=work, span=span, resolved_text=resolved_text),
        client=span_support_client,
    )
    support_score = float(entailment.get("score") or 0.0)
    if str(entailment.get("label") or "") not in _span_entailment_support_labels():
        return _span_grounding_result(
            claim,
            work,
            status="rejected_non_supporting",
            span=span,
            span_start=start,
            span_end=end,
            support_score=support_score,
            reason=(
                "resolved span does not entail the claim: "
                + ",".join(str(item) for item in entailment.get("reason_codes") or ())
            ),
        )
    return _span_grounding_result(
        claim,
        work,
        status="validated_supporting",
        span=span,
        span_start=start,
        span_end=end,
        support_score=support_score,
        reason="span resolves to source text and supports the claim",
    )


def evaluate_openalex_claim_extractor_accuracy(
    gold_set: ClaimSpanGoldSet | None = None,
    *,
    extractor: Callable[[OpenAlexWorkText, str], Sequence[CausalClaim]] | None = None,
    span_support_client: Any | None = None,
    cases: Sequence[OpenAlexExtractionCase] | None = None,
) -> ExtractorAccuracyReport:
    """Run the extractor and constructed negatives without a positive accuracy claim.

    Gold labels remain historical inputs identifying a dated population; neither
    a label nor a model response supplies the absent adjudicator appointment.
    """

    del span_support_client
    if cases is None:
        if gold_set is None:
            raise ValueError("openalex_extraction_population_missing")
        declared = {}
        for record in gold_set.records:
            key = (record.source_fixture, record.openalex_id, record.query)
            if key in declared:
                continue
            source_error = None
            source = None
            try:
                path = Path(record.source_fixture)
                if not path.is_absolute():
                    path = Path(__file__).resolve().parents[4] / path
                source = load_recorded_openalex_source(path, query=record.query)
                matches = [
                    item for item in source.payload["results"] if item["id"] == record.openalex_id
                ]
                work = (
                    OpenAlexWorkText.from_openalex_work(matches[0]) if len(matches) == 1 else None
                )
            except (OSError, ValueError, TypeError) as exc:
                work = None
                source_error = f"{type(exc).__name__}:{exc}"
            declared[key] = OpenAlexExtractionCase(
                case_id=_sha256_text(json.dumps(key)),
                openalex_id=record.openalex_id,
                query=record.query,
                source_ref=(
                    f"{record.source_fixture}@{source.content_sha256}"
                    if source is not None
                    else record.source_fixture
                ),
                recorded_at=source.captured_at if source is not None else None,
                work=work,
                source_error=source_error,
                gold_reviewed_at=gold_set.provenance.get("reviewed_at"),
            )
        cases = [declared[key] for key in sorted(declared)]
    active_extractor = extractor or (
        lambda work, query: extract_span_grounded_claims_from_openalex_work(work, query=query)
    )
    observations = []
    for case in cases:
        base = {
            "case_id": case.case_id,
            "openalex_id": case.openalex_id,
            "query": case.query,
            "source_ref": case.source_ref,
            "recorded_at": case.recorded_at,
            "gold_reviewed_at": case.gold_reviewed_at,
            "source_content_sha256": case.work.content_sha256 if case.work is not None else None,
        }
        if case.work is None:
            observations.append(
                OpenAlexExtractionObservation(
                    **base,
                    disposition="source_unavailable",
                    reason=case.source_error or "declared_work_not_resolved",
                )
            )
            continue
        try:
            claims = list(active_extractor(case.work, case.query))
        except Exception as exc:
            observations.append(
                OpenAlexExtractionObservation(
                    **base,
                    disposition="extractor_failed",
                    reason=f"{type(exc).__name__}:{exc}",
                )
            )
            continue
        predictions = []
        negatives = []
        for claim in claims:
            if not isinstance(claim, CausalClaim):
                predictions.append(
                    {
                        "disposition": "prediction_unreadable",
                        "type": type(claim).__name__,
                        "reason": "extractor_prediction_is_not_a_typed_causal_claim",
                    }
                )
                continue
            binding = validate_openalex_source_bound_candidate(case.work, claim, query=case.query)
            predictions.append(
                {
                    "claim": claim.model_dump(mode="json"),
                    "source_binding": binding.model_dump(mode="json"),
                }
            )
            poisoned_spans = [
                span.model_copy(
                    update={
                        "text": "This constructed span is absent from the selected source: "
                        + case.case_id,
                    }
                )
                for span in claim.supporting_spans
            ]
            poisoned = claim.model_copy(
                update={
                    "claim_text": "This constructed claim is absent from the selected source: "
                    + case.case_id,
                    "supporting_spans": poisoned_spans,
                }
            )
            refusal = validate_openalex_source_bound_candidate(
                case.work, poisoned, query=case.query
            )
            negatives.append(
                {
                    "claim_id": claim.claim_id,
                    "construction": "absent_claim_and_span_text",
                    "disposition": refusal.status,
                    "reason": refusal.reason,
                }
            )
        observations.append(
            OpenAlexExtractionObservation(
                **base,
                disposition="extracted",
                predictions=predictions,
                constructed_negatives=negatives,
            )
        )
    return ExtractorAccuracyReport(observations=observations)


def _evaluate_gold_span_support_accuracy(
    gold_set: ClaimSpanGoldSet,
    *,
    span_support_client: Any | None,
) -> LegacyExtractorAccuracyReportV1:
    """Fence the former default; historical report bytes remain readable in v1."""

    del gold_set, span_support_client
    raise ValueError("correspondence-acceptance-standing-rule:adjudicator_appointment_missing")


def _gold_record_to_causal_claim(
    record: ClaimSpanGoldRecord,
    work: OpenAlexWorkText,
) -> CausalClaim:
    span_start = work.source_text.find(record.gold_span_text)
    span_end = span_start + len(record.gold_span_text) if span_start >= 0 else None
    span = EvidenceSpan(
        span_id=f"{record.label_id}.gold_span",
        section="title"
        if _normalize_ws(record.gold_span_text) == _normalize_ws(work.title)
        else "abstract",
        text=record.gold_span_text,
        source_ref=work.openalex_id,
        start_char=span_start if span_start >= 0 else None,
        end_char=span_end,
        content_sha256=work.content_sha256,
    )
    direction = _normal_causal_direction(record.claim_direction)
    return CausalClaim(
        claim_id=record.label_id,
        cause_variable=record.treatment_or_cause,
        effect_variable=record.effect,
        direction=direction,
        claim_text=record.claim_text,
        claim_type=ClaimType.CAUSAL_CLAIM,
        claim_explicitness=ClaimExplicitness.EXPLICIT,
        design_family_hint=DesignFamily.QUASI_EXPERIMENTAL_OTHER,
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        supporting_spans=[span],
        supporting_span_ids=[span.span_id],
        source_basis=SourceBasis.ABSTRACT_ONLY,
        claim_extraction_confidence=1.0,
        design_quality_tier=2,
        publish_to_graph=False,
    )


def _normal_causal_direction(value: object) -> CausalDirection:
    text = str(value or "").strip().lower()
    try:
        return CausalDirection(text)
    except ValueError:
        return CausalDirection.MIXED


def _normalize_causal_claim_payload(data: object) -> object:
    if not isinstance(data, dict):
        return data
    payload = dict(data)
    if "cause_variable" not in payload and "cause" in payload:
        payload["cause_variable"] = payload.get("cause")
    if "effect_variable" not in payload and "effect" in payload:
        payload["effect_variable"] = payload.get("effect")
    payload.pop("cause", None)
    payload.pop("effect", None)
    direction = str(payload.get("direction") or "").strip().lower()
    if direction == "mixed":
        payload["direction"] = CausalDirection.MIXED.value
    if (
        "claim_type" not in payload
        and payload.get("claim_explicitness") == ClaimExplicitness.EXPLICIT.value
    ):
        payload["claim_type"] = ClaimType.CAUSAL_CLAIM.value
    cause_variable = str(payload.get("cause_variable") or "").strip()
    effect_variable = str(payload.get("effect_variable") or "").strip()
    if not str(payload.get("claim_text") or "").strip() and cause_variable and effect_variable:
        payload["claim_text"] = f"{cause_variable} -> {effect_variable}"
    payload.setdefault("supporting_span_ids", _extract_span_ids(payload.get("supporting_spans")))
    payload.setdefault("method_span_ids", _extract_span_ids(payload.get("method_spans")))
    return payload


def _normalize_article_extraction_payload(data: object) -> object:
    if not isinstance(data, dict):
        return data
    payload = dict(data)
    if "year" not in payload and "publication_year" in payload:
        payload["year"] = payload.get("publication_year")
    if "publication_year" not in payload and "year" in payload:
        payload["publication_year"] = payload.get("year")
    if "schema_version" not in payload:
        payload["schema_version"] = (
            "1.0" if "publication_year" in payload and "year" not in payload else "1.5"
        )
    return payload


def _extract_span_ids(spans: object) -> list[str]:
    if not isinstance(spans, Sequence) or isinstance(spans, (str, bytes, bytearray)):
        return []
    span_ids: list[str] = []
    for span in spans:
        if isinstance(span, dict):
            span_id = str(span.get("span_id") or "").strip()
        else:
            span_id = str(getattr(span, "span_id", "") or "").strip()
        if span_id:
            span_ids.append(span_id)
    return span_ids


def _reconstruct_openalex_abstract(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, raw_positions in value.items():
        if not isinstance(raw_positions, list):
            continue
        for position in raw_positions:
            if isinstance(position, int):
                positions.append((position, str(word)))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    normalized = _normalize_ws(text)
    if not normalized:
        return []
    return [
        sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", normalized) if sentence.strip()
    ]


_TERM_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "using",
    "with",
}
_CLAIM_CUES = (
    "effect",
    "impact",
    "increase",
    "decrease",
    "reduce",
    "improve",
    "estimate",
    "find",
    "show",
    "lead",
    "associated",
    "correlated",
    "limit",
    "limiting",
    "unchanged",
    "employment",
    "survival",
    "growth",
    "failure",
)


def _meaningful_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.casefold())
        if token not in _TERM_STOPWORDS
    }


def _claim_sentence_score(sentence: str, query_terms: set[str]) -> float:
    lowered = sentence.casefold()
    cue_hits = sum(1 for cue in _CLAIM_CUES if cue in lowered)
    if cue_hits <= 0:
        return 0.0
    sentence_terms = _meaningful_terms(sentence)
    query_overlap = len(sentence_terms & query_terms) / max(1, len(query_terms))
    cue_score = min(0.65, cue_hits * 0.13)
    return min(1.0, cue_score + min(0.35, query_overlap))


def _infer_cause_effect(sentence: str, *, query: str) -> tuple[str, str]:
    clean = _normalize_ws(sentence)
    patterns = (
        r"(?P<cause>.+?)\s+(?:increases?|decreases?|reduces?|improves?|affects?|impacts?|"
        r"causes?|spurs?|leads? to|is associated with|is correlated with)\s+(?P<effect>.+)",
        r"(?P<effect>.+?)\s+(?:is|are|was|were)\s+(?:limited|affected|reduced|increased)\s+by\s+"
        r"(?P<cause>.+)",
        r"(?:effect|impact)\s+of\s+(?P<cause>.+?)\s+on\s+(?P<effect>.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            cause = _trim_variable_phrase(match.group("cause"))
            effect = _trim_variable_phrase(match.group("effect"))
            if cause and effect and cause != effect:
                return cause, effect
    query_terms = sorted(_meaningful_terms(query))
    if len(query_terms) >= 2:
        return " ".join(query_terms[:2]), " ".join(query_terms[-2:])
    return "literature exposure", "reported outcome"


def _trim_variable_phrase(value: str) -> str:
    text = re.sub(r"\([^)]*\)", "", value)
    text = re.sub(
        r"^[,;:\s]*(we|this paper|this study|the results|results)\s+", "", text, flags=re.I
    )
    text = re.split(r"[,.;:]", text, maxsplit=1)[0]
    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z'-]*", text.casefold())
        if word not in _TERM_STOPWORDS
    ]
    if not words:
        return ""
    return " ".join(words[-6:])


def _infer_causal_direction(sentence: str) -> CausalDirection:
    lowered = sentence.casefold()
    if any(
        term in lowered for term in ("unchanged", "no evidence", "little or no", "no discernible")
    ):
        return CausalDirection.NULL
    if any(
        term in lowered
        for term in (
            "reduce",
            "decrease",
            "lower",
            "loss",
            "failure",
            "limit",
            "limiting",
            "limits",
        )
    ):
        return CausalDirection.NEGATIVE
    if any(term in lowered for term in ("increase", "improve", "positive", "growth", "gain")):
        return CausalDirection.POSITIVE
    return CausalDirection.MIXED


def _infer_design_family(sentence: str) -> DesignFamily:
    lowered = sentence.casefold()
    if "difference-in-differences" in lowered or "difference in differences" in lowered:
        return DesignFamily.DID
    if "randomized" in lowered or "randomised" in lowered:
        return DesignFamily.RCT
    if "regression discontinuity" in lowered:
        return DesignFamily.RDD
    if "fixed effects" in lowered or "panel" in lowered:
        return DesignFamily.PANEL_FE
    if "review" in lowered or "meta-analysis" in lowered:
        return DesignFamily.REVIEW
    return DesignFamily.UNCLEAR


def _infer_evidence_strength(sentence: str) -> EvidenceStrength:
    family = _infer_design_family(sentence)
    if family == DesignFamily.RCT:
        return EvidenceStrength.RCT
    if family in {DesignFamily.DID, DesignFamily.RDD, DesignFamily.EVENT_STUDY}:
        return EvidenceStrength.QUASI_NATURAL
    if family == DesignFamily.PANEL_FE:
        return EvidenceStrength.PANEL_FE
    if family == DesignFamily.REVIEW:
        return EvidenceStrength.META_ANALYSIS
    return EvidenceStrength.UNKNOWN


def _design_tier_for_sentence(sentence: str) -> int | None:
    family = _infer_design_family(sentence)
    if family in {DesignFamily.RCT, DesignFamily.DID, DesignFamily.RDD}:
        return 1
    if family in {DesignFamily.PANEL_FE, DesignFamily.EVENT_STUDY}:
        return 2
    if family == DesignFamily.REVIEW:
        return 3
    return 4


def _stable_claim_id(openalex_id: str, sentence: str, cause: str, effect: str) -> str:
    payload = f"{openalex_id}|{cause}|{effect}|{sentence}".encode()
    return "openalex.claim." + hashlib.sha256(payload).hexdigest()[:24]


def _claim_text_for_span(sentence: str, *, cause: str, effect: str) -> str:
    if cause and effect:
        return f"{cause} -> {effect}: {sentence}"
    return sentence


def _denormalize_apostrophe(text: str) -> str:
    return text.replace("'", "\u2019")


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _resolve_span(source_text: str, span: EvidenceSpan) -> tuple[int, int, str] | None:
    span_text = _normalize_ws(span.text)
    if not span_text:
        return None
    if span.start_char is not None and span.end_char is not None:
        candidate = source_text[span.start_char : span.end_char]
        if _normalize_ws(candidate) == span_text:
            return span.start_char, span.end_char, candidate
    start = _normalize_ws(source_text).find(span_text)
    if start >= 0:
        return start, start + len(span_text), span_text
    denormalized = _denormalize_apostrophe(span_text)
    start = source_text.find(denormalized)
    if start >= 0:
        return start, start + len(denormalized), denormalized
    return None


def _claim_entailment_payload(
    claim: CausalClaim,
    *,
    work: OpenAlexWorkText,
    span: EvidenceSpan,
) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "claim_text": claim.claim_text,
        "claim_family": "causal",
        "cause_variable": claim.cause_variable,
        "effect_variable": claim.effect_variable,
        "direction": claim.direction.value,
        "data_refs": [work.openalex_id],
        "source_attribution": work.openalex_id,
        "method_refs": [claim.design_family_hint.value],
        "identification_strategy": claim.design_family_hint.value,
        "citation_refs": [span.span_id],
        "design_family": claim.design_family_hint.value,
    }


def _span_entailment_payload(
    *,
    work: OpenAlexWorkText,
    span: EvidenceSpan,
    resolved_text: str,
) -> dict[str, Any]:
    section = span.section
    if not section and _normalize_ws(resolved_text) == _normalize_ws(work.title):
        section = "title"
    return {
        "ref_id": span.span_id,
        "source_id": work.openalex_id,
        "source_ref": span.source_ref or work.openalex_id,
        "section": section,
        "text": resolved_text,
        "source_content_sha256": work.content_sha256,
        "span_content_sha256": span.content_sha256,
    }


def _evaluate_span_claim_entailment(
    *,
    claim: dict[str, Any],
    evidence: dict[str, Any],
    client: Any | None = None,
) -> dict[str, Any]:
    module = importlib.import_module("polisyos.scientist.validation.citation_faithfulness")
    evaluator = module.evaluate_span_claim_entailment
    return dict(evaluator(claim=claim, evidence=evidence, client=client))


def _span_entailment_support_labels() -> frozenset[str]:
    module = importlib.import_module("polisyos.scientist.validation.citation_faithfulness")
    labels = module.SPAN_ENTAILMENT_SUPPORT_LABELS
    return frozenset(str(label) for label in labels)


def _span_grounding_result(
    claim: CausalClaim,
    work: OpenAlexWorkText,
    *,
    status: Literal[
        "validated_supporting",
        "rejected_missing_span",
        "rejected_source_mismatch",
        "rejected_hash_mismatch",
        "rejected_unresolved_span",
        "rejected_non_supporting",
    ],
    span: EvidenceSpan | None = None,
    span_start: int | None = None,
    span_end: int | None = None,
    support_score: float = 0.0,
    reason: str,
) -> SpanGroundingResult:
    authority_tier = (
        "design_tier_l2" if status == "validated_supporting" else "candidate_unverified"
    )
    span_id = span.span_id if span else ""
    return SpanGroundingResult(
        claim_id=claim.claim_id,
        openalex_id=work.openalex_id,
        status=status,
        authority_tier=authority_tier,
        support_score=round(support_score, 6),
        span_id=span_id,
        span_start=span_start,
        span_end=span_end,
        grounding_ref=(
            f"openalex-span-grounding://{work.openalex_id.rsplit('/', 1)[-1]}/{claim.claim_id}"
            if status == "validated_supporting"
            else ""
        ),
        reason=reason,
    )


def _span_match_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalize_ws(text).casefold()).strip()


def recorded_openalex_capture_time(payload: dict[str, Any]) -> str:
    """Require the supplied UTC capture coordinate without inventing a date."""

    recording = payload.get("_recording")
    captured = recording.get("captured_at") if isinstance(recording, dict) else None
    if not isinstance(captured, str) or not captured:
        raise ValueError("openalex_recorded_capture_time_missing")
    try:
        parsed = datetime.fromisoformat(captured)
    except ValueError as exc:
        raise ValueError("openalex_recorded_capture_time_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("openalex_recorded_capture_time_not_utc")
    return captured


def validate_recorded_openalex_response(
    payload: dict[str, Any], *, query: str, allow_empty: bool = False
) -> str:
    """Validate recorded response context and return its supplied capture time."""

    recording = payload.get("_recording")
    if not isinstance(recording, dict):
        raise ValueError("OpenAlex fixture lacks recording metadata")
    captured_at = recorded_openalex_capture_time(payload)
    if recording.get("real_openalex_api_response") is not True:
        raise ValueError("OpenAlex fixture is not marked recorded-real")
    if recording.get("source") != "https://api.openalex.org/works":
        raise ValueError("OpenAlex fixture source drift")
    request_params = recording.get("request_params")
    if not isinstance(request_params, dict):
        raise ValueError("OpenAlex fixture request params missing")
    if not isinstance(query, str) or not query or recording.get("query") != query:
        raise ValueError("OpenAlex fixture recording query drift")
    if request_params.get("search") != query:
        raise ValueError("OpenAlex fixture request search drift")
    if "abstract_inverted_index" not in str(request_params.get("select") or ""):
        raise ValueError("OpenAlex fixture select omits abstract text")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("OpenAlex fixture results missing")
    if not allow_empty and not results:
        raise ValueError("OpenAlex fixture results unexpectedly empty")
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("OpenAlex fixture result shape invalid")
        if not str(item.get("id") or "").startswith("https://openalex.org/W"):
            raise ValueError("OpenAlex fixture work id invalid")
        if not isinstance(item.get("abstract_inverted_index"), dict):
            raise ValueError("OpenAlex fixture work lacks abstract text")
    return captured_at


def load_recorded_openalex_source(
    path: Path, *, query: str | None = None, allow_empty: bool = False
) -> OpenAlexRecordedSource:
    """Read once and bind source bytes, request context, and capture metadata."""

    raw = path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("openalex_recorded_response_object_required")
    recording = payload.get("_recording")
    selected_query = (
        query
        if query is not None
        else (recording.get("query") if isinstance(recording, dict) else None)
    )
    captured_at = validate_recorded_openalex_response(
        payload, query=selected_query, allow_empty=allow_empty
    )
    return OpenAlexRecordedSource(
        payload=payload,
        query=selected_query,
        captured_at=captured_at,
        content_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
    )


def _load_gold_works(gold_set: ClaimSpanGoldSet) -> dict[str, OpenAlexWorkText]:
    repo_root = Path(__file__).resolve().parents[4]
    works: dict[str, OpenAlexWorkText] = {}
    for record in gold_set.records:
        path = Path(record.source_fixture)
        if not path.is_absolute():
            path = repo_root / path
        payload = load_recorded_openalex_source(path, query=record.query).payload
        for item in payload.get("results", []):
            if isinstance(item, dict) and str(item.get("id") or "") == record.openalex_id:
                works[record.openalex_id] = OpenAlexWorkText.from_openalex_work(item)
                break
    return works


_SCHEMA_NAME = "ir.article_extraction_result"
_SCHEMA_VERSION = "1.2"
_LITERATURE_PRIOR_SCHEMA_NAME = "ir.literature_causal_prior"
_LITERATURE_PRIOR_SCHEMA_VERSION = "1.0"


def persist_article_extraction_result(
    store: ArtifactStore,
    result: ArticleExtractionResult,
    *,
    inputs: list[InputRef] | None = None,
) -> dict:
    """Persist article extraction result helper."""
    return put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind=_SCHEMA_NAME,
        schema_name=_SCHEMA_NAME,
        schema_version=_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_article_extraction_result(store: ArtifactStore, ref: object) -> ArticleExtractionResult:
    """Load article extraction result."""
    artifact_id = ref.artifact_id if hasattr(ref, "artifact_id") else ref
    artifact = artifact_id if isinstance(artifact_id, ArtifactID) else ArtifactID(str(artifact_id))
    payload = get_json_artifact(store, artifact)
    return ArticleExtractionResult.model_validate(payload)


def persist_literature_causal_prior(
    store: ArtifactStore,
    prior: LiteratureCausalPrior,
    *,
    inputs: list[InputRef] | None = None,
) -> LiteratureCausalPriorRef:
    """Persist literature causal prior helper."""
    ref = put_json_artifact(
        store,
        prior.model_dump(mode="json"),
        kind=_LITERATURE_PRIOR_SCHEMA_NAME,
        schema_name=_LITERATURE_PRIOR_SCHEMA_NAME,
        schema_version=_LITERATURE_PRIOR_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return LiteratureCausalPriorRef.model_validate(ref)


def load_literature_causal_prior(
    store: ArtifactStore,
    ref: LiteratureCausalPriorRef | object,
) -> LiteratureCausalPrior:
    """Load literature causal prior."""
    artifact_id = ref.artifact_id if hasattr(ref, "artifact_id") else ref
    artifact = artifact_id if isinstance(artifact_id, ArtifactID) else ArtifactID(str(artifact_id))
    payload = get_json_artifact(store, artifact)
    return LiteratureCausalPrior.model_validate(payload)


__all__ = [
    "AdmittedClaimAdjudicationBatch",
    "ArticleExtractionResult",
    "BoundaryCondition",
    "CausalClaim",
    "CausalCredibility",
    "CausalDirection",
    "ClaimAdjudicationInputBatch",
    "ClaimAdjudicationInputItem",
    "ClaimAdjudicationResult",
    "ClaimExplicitness",
    "ClaimSpanGoldRecord",
    "ClaimSpanGoldSet",
    "ClaimType",
    "ClaimVocabularyAxisStatus",
    "ContextAttribute",
    "DesignFamily",
    "EnvironmentAuditReport",
    "EvidenceParameter",
    "EvidenceSpan",
    "EvidenceStrength",
    "EvidenceStrengthOrigin",
    "ExtractorAccuracyReport",
    "HeterogeneityResult",
    "IdentificationStrategy",
    "LegacyFiveFieldClaimOccurrence",
    "LiteratureCausalPrior",
    "LiteratureEdgePrior",
    "Mechanism",
    "ModerationEdge",
    "OpenAlexExtractionCase",
    "OpenAlexExtractionObservation",
    "OpenAlexRecordedSource",
    "OpenAlexSourceBindingResult",
    "OpenAlexWorkText",
    "PaperKind",
    "ParameterType",
    "ReconciliationDiagnostics",
    "RiskOfBias",
    "SourceBasis",
    "SpanGroundingResult",
    "SupportStatus",
    "TextQuality",
    "UncertaintyBudget",
    "VersionedClaimVocabularyEnvelope",
    "adapt_legacy_claim_occurrence_as_v2_absence",
    "evaluate_openalex_claim_extractor_accuracy",
    "extract_span_grounded_claims_from_openalex_work",
    "load_article_extraction_result",
    "load_literature_causal_prior",
    "load_recorded_openalex_source",
    "persist_article_extraction_result",
    "persist_literature_causal_prior",
    "recorded_openalex_capture_time",
    "validate_causal_claim_span_grounding",
    "validate_openalex_source_bound_candidate",
    "validate_recorded_openalex_response",
]
