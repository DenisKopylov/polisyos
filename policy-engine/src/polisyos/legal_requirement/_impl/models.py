"""Typed contracts for W7.B legal authority requirement compilation."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

LEGAL_AUTHORITY_REQUIREMENT_SPEC_SCHEMA_VERSION = "policyos.legal_requirement.spec.v1"
LEGAL_AUTHORITY_REQUIREMENT_ARTIFACT_SCHEMA_VERSION = (
    "policyos.legal_requirement_artifact.v1"
)
LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION = "legal-requirement-compiler:v1"
LEGAL_REQUIREMENT_PATTERN_REFS = ("P01", "P05", "P08", "P12")


class LegalAuthorityType(StrEnum):
    """Canonical W7.B authority-type facets for claim-level legal competence."""

    IMPLEMENTING = "implementing"
    DELEGATING = "delegating"
    ENABLING = "enabling"
    FUNDING = "funding"
    OVERSIGHT = "oversight"
    APPEAL_OR_CONTESTABILITY = "appeal_or_contestability"


class LegalRequirementFallbackMode(StrEnum):
    """How Lex may use jurisdiction fallback for one requirement."""

    GOVERNED_CONFIG_REQUIRED = "governed_config_required"
    FORBIDDEN = "forbidden"
    NOT_APPLICABLE = "not_applicable"


class LegalAdmissibilityGrade(StrEnum):
    """W7.B legal admissibility grades emitted by the Lex adapter."""

    ADMISSIBLE = "admissible"
    CONTEXT_ONLY = "context_only"
    PROXY_WITH_LIMITATION = "proxy_with_limitation"
    CONTESTED = "contested"
    BLOCKED = "blocked"
    OUT_OF_SCOPE = "out_of_scope"


class TemporalCompetenceWindow(BaseModel):
    """Legal competence window with explicit time-role semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: str | None = None
    end: str | None = None
    time_role: str = Field(default="implementation_period", min_length=1)
    legal_as_of: str | None = None

    @field_validator("start", "end", "time_role", "legal_as_of", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _validate_window(self) -> TemporalCompetenceWindow:
        if self.time_role == "":
            raise ValueError("time_role must be non-empty")
        return self


class LegalScopePredicates(BaseModel):
    """Scope predicates carried from W6 facets and claim decomposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    population: tuple[str, ...] = Field(default=())
    geography: tuple[str, ...] = Field(default=())
    time: tuple[str, ...] = Field(default=())

    @field_validator("population", "geography", "time", mode="before")
    @classmethod
    def _normalize_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


def legal_authority_requirement_authority_boundary() -> dict[str, list[str]]:
    """Return the W7.B authority boundary for legal requirement artifacts."""

    return {
        "authoritative_for": [
            "legal_authority_requirements",
            "lex_claim_level_competence_preconditions",
        ],
        "may_not_use_for": [
            "legal_admissibility_without_lex_evaluation",
            "source_family_satisfaction",
            "method_validity",
            "academic_support_strength",
            "participation_representativeness",
            "closeout_pass",
        ],
    }


class LegalRequirementFallbackPolicy(BaseModel):
    """Governed fallback policy declaration for a legal requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: LegalRequirementFallbackMode = LegalRequirementFallbackMode.GOVERNED_CONFIG_REQUIRED
    config_ref: str | None = None
    policy_ref: str | None = None
    owner: str | None = None
    review_ref: str | None = None

    @field_validator("config_ref", "policy_ref", "owner", "review_ref", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str | None:
        return _optional_text(value)


class LegalAuthorityRequirementSpec(BaseModel):
    """Claim-level legal authority requirement consumed by the Lex adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.legal_requirement.spec.v1"] = (
        LEGAL_AUTHORITY_REQUIREMENT_SPEC_SCHEMA_VERSION
    )
    requirement_id: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    mandatory: bool = True
    out_of_scope: bool = False
    required_hierarchy_depth: int = Field(default=1, ge=0)
    temporal_competence_window: TemporalCompetenceWindow = Field(
        default_factory=TemporalCompetenceWindow
    )
    authority_types: tuple[LegalAuthorityType, ...] = Field(default=())
    required_instrument_classes: tuple[str, ...] = Field(default=())
    required_actor_refs: tuple[str, ...] = Field(default=())
    required_implementation_authority_refs: tuple[str, ...] = Field(default=())
    required_fiscal_authority_refs: tuple[str, ...] = Field(default=())
    implementation_authority_required: bool = False
    fiscal_authority_required: bool = False
    contestability_or_appeal_required: bool = False
    scope_predicates: LegalScopePredicates = Field(default_factory=LegalScopePredicates)
    fallback_policy: LegalRequirementFallbackPolicy = Field(
        default_factory=LegalRequirementFallbackPolicy
    )
    jurisdiction: str | None = None
    authority_profile_ref: str | None = None
    facet_refs: tuple[str, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    concept_spine_refs: tuple[str, ...] = Field(default=())
    source_claim_refs: tuple[str, ...] = Field(default=())
    provenance_refs: tuple[str, ...] = Field(default=())
    rule_version_ref: str = Field(
        default=LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION,
        min_length=1,
    )
    pattern_refs: tuple[str, ...] = Field(default=LEGAL_REQUIREMENT_PATTERN_REFS)
    capability_reality_label: str = Field(default="implemented", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "requirement_id",
        "claim_ref",
        "claim_id",
        "jurisdiction",
        "authority_profile_ref",
        "rule_version_ref",
        "capability_reality_label",
        mode="before",
    )
    @classmethod
    def _strip_required_or_optional_text(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> str | None:
        optional = {"jurisdiction", "authority_profile_ref"}
        if info.field_name in optional:
            return _optional_text(value)
        return _required_text(value)

    @field_validator("authority_types", mode="before")
    @classmethod
    def _normalize_authority_types(cls, value: object) -> tuple[LegalAuthorityType, ...]:
        result: list[LegalAuthorityType] = []
        seen: set[LegalAuthorityType] = set()
        for token in _text_tuple(value):
            authority_type = normalize_legal_authority_type(token)
            if authority_type in seen:
                continue
            seen.add(authority_type)
            result.append(authority_type)
        return tuple(result)

    @field_validator(
        "required_instrument_classes",
        "required_actor_refs",
        "required_implementation_authority_refs",
        "required_fiscal_authority_refs",
        "facet_refs",
        "obligation_refs",
        "concept_spine_refs",
        "source_claim_refs",
        "provenance_refs",
        "pattern_refs",
        mode="before",
    )
    @classmethod
    def _normalize_tuple_fields(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_requirement_boundary(self) -> LegalAuthorityRequirementSpec:
        if self.out_of_scope and self.mandatory:
            raise ValueError("out_of_scope legal requirements cannot be mandatory")
        if self.out_of_scope and self.authority_types:
            raise ValueError("out_of_scope legal requirements cannot carry authority_types")
        if self.mandatory and not self.authority_types:
            raise ValueError("mandatory legal requirements require authority_types")
        return self


class LegalAuthorityRequirementArtifact(BaseModel):
    """Persistable compiler artifact for one run's legal authority requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.legal_requirement_artifact.v1"] = (
        LEGAL_AUTHORITY_REQUIREMENT_ARTIFACT_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    requirements: tuple[LegalAuthorityRequirementSpec, ...] = Field(default=())
    target_context: dict[str, Any] = Field(default_factory=dict)
    capability_reality_label: Literal["implemented"] = "implemented"
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    authority_boundary: dict[str, list[str]] = Field(
        default_factory=legal_authority_requirement_authority_boundary
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_runtime_event_ref(self) -> LegalAuthorityRequirementArtifact:
        if self.runtime_event_ref is None:
            object.__setattr__(
                self,
                "runtime_event_ref",
                f"event://legal-requirement/{_slug(self.run_id)}",
            )
        if not self.authority_boundary:
            object.__setattr__(
                self,
                "authority_boundary",
                legal_authority_requirement_authority_boundary(),
            )
        return self


def normalize_legal_authority_type(value: object) -> LegalAuthorityType:
    """Normalize ADR-0168/W7.B authority type aliases to canonical facets."""

    token = _required_text(value).casefold().replace("-", "_")
    aliases = {
        "appeals_or_contestability": LegalAuthorityType.APPEAL_OR_CONTESTABILITY,
        "appeal_or_contestability": LegalAuthorityType.APPEAL_OR_CONTESTABILITY,
        "contestability": LegalAuthorityType.APPEAL_OR_CONTESTABILITY,
        "appeal": LegalAuthorityType.APPEAL_OR_CONTESTABILITY,
        "appeals": LegalAuthorityType.APPEAL_OR_CONTESTABILITY,
    }
    if token in aliases:
        return aliases[token]
    return LegalAuthorityType(token)


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _optional_text(value)
        return (text,) if text else ()
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = _optional_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return tuple(result)
    text = _optional_text(value)
    return (text,) if text else ()


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if not text:
        raise ValueError("value must be non-empty text")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "LEGAL_AUTHORITY_REQUIREMENT_ARTIFACT_SCHEMA_VERSION",
    "LEGAL_AUTHORITY_REQUIREMENT_COMPILER_RULE_VERSION",
    "LEGAL_AUTHORITY_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "LEGAL_REQUIREMENT_PATTERN_REFS",
    "LegalAdmissibilityGrade",
    "LegalAuthorityRequirementArtifact",
    "LegalAuthorityRequirementSpec",
    "LegalAuthorityType",
    "LegalRequirementFallbackMode",
    "LegalRequirementFallbackPolicy",
    "LegalScopePredicates",
    "TemporalCompetenceWindow",
    "legal_authority_requirement_authority_boundary",
    "normalize_legal_authority_type",
]
