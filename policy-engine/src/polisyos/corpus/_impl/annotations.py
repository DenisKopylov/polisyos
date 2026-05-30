"""W11.B universal outcome corpus claim/evidence annotation contracts.

The corpus annotation is a review artifact used by fixture loaders and
compilation-truthfulness tools. It records expected claim/evidence decomposition
without minting claim, producer, legal, method, or projection authority.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

POLICY_CASE_ANNOTATION_SCHEMA_VERSION = "policyos.universal_outcome_corpus.annotation.v1"
_ARTIFACT_SUFFIX = ".annotation.json"
_ANNOTATION_AUTHORITATIVE_FOR = (
    "corpus_annotation",
    "compilation_truthfulness_reference",
)
_ANNOTATION_MAY_NOT_USE_FOR = (
    "claim_authority",
    "producer_evidence_authority",
    "legal_authority",
    "method_validity",
    "participation_legitimacy",
    "projection_authority",
)
_PATTERN_REFS = ("P01", "P02", "P03", "P05", "P10", "P13", "P14", "P15")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<yaml>.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


class PolicyCaseAnnotationError(ValueError):
    """Raised when a corpus annotation file cannot be loaded."""


class AnnotationReferenceType(StrEnum):
    """Reference families that annotation fields may point at."""

    SOURCE = "source"
    EVIDENCE = "evidence"
    METHOD = "method"
    LEGAL = "legal"
    PARTICIPATION = "participation"
    RISK = "risk"
    TRADEOFF = "tradeoff"
    LIMITATION = "limitation"
    OUTCOME = "outcome"


class PolicyCaseReference(BaseModel):
    """One declared source or annotation-local reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_id: str = Field(min_length=1)
    ref_type: AnnotationReferenceType
    title: str = Field(min_length=1)
    source_ref: str | None = None
    redacted_source_hash: str | None = None
    notes: str | None = None

    @field_validator(
        "ref_id",
        "title",
        "source_ref",
        "redacted_source_hash",
        "notes",
        mode="before",
    )
    @classmethod
    def _strip_text_fields(cls, value: object, info: ValidationInfo) -> str | None:
        if info.field_name in {"source_ref", "redacted_source_hash", "notes"}:
            return _optional_text(value)
        return _required_text(value)

    @model_validator(mode="after")
    def _require_source_or_hash(self) -> PolicyCaseReference:
        if not self.source_ref and not self.redacted_source_hash:
            raise ValueError(
                "policy case references require source_ref or redacted_source_hash"
            )
        if self.redacted_source_hash and not self.redacted_source_hash.startswith("sha256:"):
            raise ValueError("redacted_source_hash must use sha256:<digest>")
        return self


class PolicyInstrumentAnnotation(BaseModel):
    """Policy instrument fields from the annotation protocol draft."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument_type: str = Field(min_length=1)
    delivery_channel: str = Field(min_length=1)
    funding_channel: str | None = None

    @field_validator("instrument_type", "delivery_channel", "funding_channel", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: object, info: ValidationInfo) -> str | None:
        if info.field_name == "funding_channel":
            return _optional_text(value)
        return _required_text(value)


class TargetingAnnotation(BaseModel):
    """Targeting fields from the annotation protocol draft."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    targeting_type: str = Field(min_length=1)
    beneficiary_classes: tuple[str, ...] = Field(min_length=1)
    affected_populations: tuple[str, ...] = Field(min_length=1)

    @field_validator("targeting_type", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("beneficiary_classes", "affected_populations", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ClaimScope(BaseModel):
    """Claim scope recorded by W11.B annotations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    population: tuple[str, ...] = Field(min_length=1)
    geography: tuple[str, ...] = Field(min_length=1)
    time_period: str = Field(min_length=1)
    institution: tuple[str, ...] = Field(min_length=1)

    @field_validator("population", "geography", "institution", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator("time_period", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return _required_text(value)


class ClaimAnnotationRecord(BaseModel):
    """Claim/evidence decomposition record from W11.B."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    claim_type: str = Field(min_length=1)
    text_ref: str = Field(min_length=1)
    scope: ClaimScope
    evidence_refs: tuple[str, ...]
    method_refs: tuple[str, ...]
    legal_refs: tuple[str, ...]
    participation_refs: tuple[str, ...]
    risks: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    admissibility_label: Literal[
        "admissible",
        "limited",
        "contested",
        "blocked",
        "publishable",
        "publishable_with_limitation",
    ]
    limitation_refs: tuple[str, ...]
    contestability_status: Literal[
        "uncontested",
        "contested",
        "limited",
        "review_required",
        "appeal_available",
        "blocked",
        "resolved_by_court",
    ]

    @field_validator("claim_id", "claim_type", "text_ref", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator(
        "evidence_refs",
        "method_refs",
        "legal_refs",
        "participation_refs",
        "risks",
        "tradeoffs",
        "limitation_refs",
        mode="before",
    )
    @classmethod
    def _coerce_ref_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ObligationAnnotation(BaseModel):
    """Required obligation annotation used by compilation truthfulness checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str = Field(min_length=1)
    generated_from_facets: tuple[str, ...] = Field(min_length=1)
    required_evidence_family: str = Field(min_length=1)
    status: Literal[
        "satisfied",
        "missing",
        "contested",
        "blocked",
        "closeout_block",
        "limitation_required",
        "not_applicable",
        "required_for_governed_closeout",
        "required_for_production_closeout",
        "required_for_research_closeout",
        "review_required",
    ]
    reviewer_notes: str = Field(min_length=1)

    @field_validator("obligation_id", "required_evidence_family", "reviewer_notes", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("generated_from_facets", mode="before")
    @classmethod
    def _coerce_facets(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class KnownOutcomeOrFailureAnnotation(BaseModel):
    """Known outcome/failure record used to test prior-obligation coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    would_prior_obligation_have_flagged: bool | None

    @field_validator("finding_id", "source_ref", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return _required_text(value)


class AnnotationProvenance(BaseModel):
    """Reviewer provenance for a claim/evidence annotation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_role: str = Field(min_length=1)
    expertise_basis: str = Field(min_length=1)
    conflicts: tuple[str, ...] = Field(default=())
    reviewed_at: str = Field(min_length=1)
    disagreement_category: str | None = None

    @field_validator(
        "reviewer_role",
        "expertise_basis",
        "reviewed_at",
        "disagreement_category",
        mode="before",
    )
    @classmethod
    def _strip_text_fields(cls, value: object, info: ValidationInfo) -> str | None:
        if info.field_name == "disagreement_category":
            return _optional_text(value)
        return _required_text(value)

    @field_validator("conflicts", mode="before")
    @classmethod
    def _coerce_conflicts(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class AnnotationAuthorityBoundary(BaseModel):
    """Authority boundary for W11.B annotation artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoritative_for: tuple[str, ...] = _ANNOTATION_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = _ANNOTATION_MAY_NOT_USE_FOR
    may_not_be_used_for: tuple[str, ...] = _ANNOTATION_MAY_NOT_USE_FOR

    @field_validator("authoritative_for", "may_not_use_for", "may_not_be_used_for", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _enforce_annotation_boundary(self) -> AnnotationAuthorityBoundary:
        if self.authoritative_for != _ANNOTATION_AUTHORITATIVE_FOR:
            raise ValueError("annotations may only be authoritative for corpus/truthfulness review")
        if not set(_ANNOTATION_MAY_NOT_USE_FOR) <= set(self.may_not_use_for):
            raise ValueError("annotation boundary must forbid authority-bearing uses")
        if not set(_ANNOTATION_MAY_NOT_USE_FOR) <= set(self.may_not_be_used_for):
            raise ValueError("annotation boundary must expose may_not_be_used_for limits")
        return self


class PolicyCaseAnnotation(BaseModel):
    """One W11.B annotated policy case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[POLICY_CASE_ANNOTATION_SCHEMA_VERSION] = (
        POLICY_CASE_ANNOTATION_SCHEMA_VERSION
    )
    case_id: str = Field(min_length=1)
    case_title: str | None = None
    corpus_phase: str | None = None
    sourcing_status: str | None = None
    annotation_status: str | None = None
    expert_adjudication_status: str | None = None
    domain: str | None = None
    authority_level: str | None = None
    jurisdiction_authority_level: str | None = None
    jurisdiction: str = Field(min_length=1)
    policy_time: str = Field(min_length=1)
    policy_instrument: PolicyInstrumentAnnotation
    targeting: TargetingAnnotation
    expected_evidence_families: tuple[str, ...] = Field(default=())
    raw_source_refs: tuple[str, ...] = Field(default=())
    redacted_source_hashes: tuple[str, ...] = Field(default=())
    known_failure_limitation_labels: tuple[str, ...] = Field(default=())
    references: tuple[PolicyCaseReference, ...] = Field(min_length=1)
    claims: tuple[ClaimAnnotationRecord, ...] = Field(min_length=1)
    obligations: tuple[ObligationAnnotation, ...] = Field(min_length=1)
    known_outcomes_or_failures: tuple[KnownOutcomeOrFailureAnnotation, ...] = Field(
        min_length=1
    )
    annotation_provenance: AnnotationProvenance
    authority_boundary: AnnotationAuthorityBoundary = Field(
        default_factory=AnnotationAuthorityBoundary
    )
    capability_reality_label: Literal["implemented"] = "implemented"
    pattern_refs: tuple[str, ...] = _PATTERN_REFS

    @field_validator("case_id", "jurisdiction", "policy_time", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator(
        "case_title",
        "corpus_phase",
        "sourcing_status",
        "annotation_status",
        "expert_adjudication_status",
        "domain",
        "authority_level",
        "jurisdiction_authority_level",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: object) -> str | None:
        return _optional_text(value)

    @field_validator(
        "expected_evidence_families",
        "raw_source_refs",
        "redacted_source_hashes",
        "known_failure_limitation_labels",
        mode="before",
    )
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator("pattern_refs", mode="before")
    @classmethod
    def _coerce_patterns(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_unique_ids_and_grounding(self) -> PolicyCaseAnnotation:
        _validate_unique([reference.ref_id for reference in self.references], "ref_id")
        _validate_unique([claim.claim_id for claim in self.claims], "claim_id")
        _validate_unique(
            [obligation.obligation_id for obligation in self.obligations],
            "obligation_id",
        )
        _validate_unique(
            [finding.finding_id for finding in self.known_outcomes_or_failures],
            "finding_id",
        )
        registered_refs = {reference.ref_id for reference in self.references}
        used_refs: list[str] = []
        for claim in self.claims:
            used_refs.append(claim.text_ref)
            used_refs.extend(claim.evidence_refs)
            used_refs.extend(claim.method_refs)
            used_refs.extend(claim.legal_refs)
            used_refs.extend(claim.participation_refs)
            used_refs.extend(claim.risks)
            used_refs.extend(claim.tradeoffs)
            used_refs.extend(claim.limitation_refs)
        used_refs.extend(
            finding.source_ref for finding in self.known_outcomes_or_failures
        )
        missing = sorted({ref for ref in used_refs if ref not in registered_refs})
        if missing:
            raise ValueError(f"unregistered annotation refs: {missing}")
        return self


def load_policy_case_annotation(path: str | Path) -> PolicyCaseAnnotation:
    """Load a W11.B policy case annotation from Markdown YAML frontmatter."""

    annotation_path = Path(path)
    text = annotation_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise PolicyCaseAnnotationError(
            f"policy case annotation missing YAML frontmatter: {annotation_path}"
        )
    payload = yaml.safe_load(match.group("yaml"))
    if not isinstance(payload, dict):
        raise PolicyCaseAnnotationError(
            f"policy case annotation frontmatter must be a mapping: {annotation_path}"
        )
    return PolicyCaseAnnotation.model_validate(payload)


def load_outcome_corpus_annotations(corpus_dir: str | Path) -> tuple[PolicyCaseAnnotation, ...]:
    """Load all annotated Markdown cases in an outcome-corpus directory."""

    directory = Path(corpus_dir)
    annotations: list[PolicyCaseAnnotation] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        annotations.append(load_policy_case_annotation(path))
    return tuple(annotations)


def write_policy_case_annotation_artifact(
    annotation: PolicyCaseAnnotation,
    output_dir: str | Path,
) -> Path:
    """Persist a deterministic JSON copy of a W11.B annotation artifact."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(annotation.case_id)}{_ARTIFACT_SUFFIX}"
    path.write_text(
        json.dumps(annotation.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def policy_case_annotation_audit_surface(
    annotation: PolicyCaseAnnotation,
) -> dict[str, Any]:
    """Return the machine/audit surface for a W11.B corpus annotation."""

    boundary = annotation.authority_boundary.model_dump(mode="json")
    return {
        "surface": "universal_outcome_corpus.annotation_audit",
        "schema_version": annotation.schema_version,
        "case_id": annotation.case_id,
        "capability_reality_label": annotation.capability_reality_label,
        "pattern_refs": list(annotation.pattern_refs),
        "summary": {
            "claim_count": len(annotation.claims),
            "obligation_count": len(annotation.obligations),
            "known_outcome_or_failure_count": len(annotation.known_outcomes_or_failures),
            "reference_count": len(annotation.references),
        },
        "authority_boundary": boundary,
    }


def _validate_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} values must be unique")


def _required_text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _required_text(value)


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_required_text(value),)
    if not isinstance(value, (list, tuple)):
        raise TypeError("value must be a string or sequence of strings")
    return tuple(_required_text(item) for item in value)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return normalized or "policy-case-annotation"


__all__ = [
    "POLICY_CASE_ANNOTATION_SCHEMA_VERSION",
    "AnnotationAuthorityBoundary",
    "AnnotationProvenance",
    "AnnotationReferenceType",
    "ClaimAnnotationRecord",
    "ClaimScope",
    "KnownOutcomeOrFailureAnnotation",
    "ObligationAnnotation",
    "PolicyCaseAnnotation",
    "PolicyCaseAnnotationError",
    "PolicyCaseReference",
    "PolicyInstrumentAnnotation",
    "TargetingAnnotation",
    "load_outcome_corpus_annotations",
    "load_policy_case_annotation",
    "policy_case_annotation_audit_surface",
    "write_policy_case_annotation_artifact",
]
