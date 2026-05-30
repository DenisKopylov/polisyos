"""Typed data requirement contracts emitted by the W7.A compiler."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DATA_REQUIREMENT_SPEC_SCHEMA_VERSION = "policyos.data_requirement_spec.v1"
DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION = "policyos.data_requirement_compilation.v1"

LineageStrictness = Literal["strict", "standard", "relaxed"]
TransformationTolerance = Literal[
    "none",
    "traceable",
    "derived_feature_allowed",
    "proxy_with_limitation",
]
DataRequirementTimeRole = Literal[
    "observation_time",
    "valid_time",
    "transaction_time",
    "ingestion_time",
    "publication_time",
    "forecast_time",
]


def data_requirement_authority_boundary() -> dict[str, list[str]]:
    """Return the W7.A authority boundary for data requirement artifacts."""

    return {
        "authoritative_for": [
            "data_requirements",
            "fabric_source_selection_preconditions",
            "scenario_evidence_contract_legacy_projection",
        ],
        "may_not_use_for": [
            "source_contract_binding_without_fabric_validation",
            "scenario_family_authority_lookup",
            "claim_support",
            "legal_authority",
            "method_validity",
            "projection_authority",
            "closeout_pass",
        ],
    }


class DataRequirementScope(BaseModel):
    """Population, geography, and time scope for a claim-bound data requirement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    population: str = Field(min_length=1)
    geography: str = Field(min_length=1)
    time: str = Field(min_length=1)
    time_role: DataRequirementTimeRole = "observation_time"
    jurisdiction: str | None = None

    @field_validator("population", "geography", "time", "jurisdiction", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class DataQualityMinimums(BaseModel):
    """Minimum quality bar a Fabric SourceContract must satisfy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_quality_score: float = Field(default=0.8, ge=0.0, le=1.0)
    min_completeness: float = Field(default=0.95, ge=0.0, le=1.0)
    required_quality_refs: tuple[str, ...] = Field(default=())

    @field_validator("required_quality_refs", mode="before")
    @classmethod
    def _clean_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class DataRequirementSpec(BaseModel):
    """Claim-bound data requirement consumed by Fabric source selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_requirement_spec.v1"] = (
        DATA_REQUIREMENT_SPEC_SCHEMA_VERSION
    )
    requirement_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim_family: str | None = None
    claim_type: str | None = None
    claim_use: str | None = None
    required_data_families: tuple[str, ...] = Field(min_length=1)
    scope: DataRequirementScope
    recency_horizon: str = Field(min_length=1)
    lineage_strictness: LineageStrictness = "strict"
    quality_minima: DataQualityMinimums
    missingness_tolerance: float = Field(ge=0.0, le=1.0)
    transformation_tolerance: TransformationTolerance
    admissibility_predicates: tuple[str, ...] = Field(min_length=1)
    mandatory_facets: tuple[str, ...] = Field(min_length=1)
    facet_refs: tuple[str, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    concept_spine_refs: tuple[str, ...] = Field(min_length=1)
    authority_profile_refs: tuple[str, ...] = Field(min_length=1)
    rule_version_ref: str = "policyos.data_requirement.compiler.v1"
    producer: str = "polisyos.data_requirement.compiler.DataRequirementCompiler"
    source_requirement_refs: tuple[str, ...] = Field(default=())
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "requirement_id",
        "claim_id",
        "claim_family",
        "claim_type",
        "claim_use",
        "recency_horizon",
        "rule_version_ref",
        "producer",
        mode="before",
    )
    @classmethod
    def _clean_optional_or_required_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator(
        "required_data_families",
        "admissibility_predicates",
        "mandatory_facets",
        "facet_refs",
        "obligation_refs",
        "concept_spine_refs",
        "authority_profile_refs",
        "source_requirement_refs",
        mode="before",
    )
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_authority_and_facets(self) -> DataRequirementSpec:
        if not self.authority_profile_refs:
            raise ValueError("authority_profile_refs are required for data authority boundary")
        if not self.concept_spine_refs:
            raise ValueError("concept_spine_refs are required for data requirement grounding")
        if not self.mandatory_facets:
            raise ValueError("mandatory_facets are required for Fabric admissibility")
        if self.missingness_tolerance > 1.0 - self.quality_minima.min_completeness:
            raise ValueError(
                "missingness_tolerance cannot exceed the completeness gap allowed by "
                "quality_minima"
            )
        return self


class DataRequirementCompilationReport(BaseModel):
    """Compiler report carrying specs plus legacy bridge projection fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.data_requirement_compilation.v1"] = (
        DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    scenario_id: str | None = None
    specs: tuple[DataRequirementSpec, ...] = Field(default=())
    legacy_admissible_data_source_families: tuple[str, ...] = Field(default=())
    capability_reality_label: Literal["implemented"] = "implemented"
    pattern_refs: tuple[str, ...] = ("P02", "P05", "P08", "P12", "P14")
    runtime_event_ref: str | None = Field(default=None, min_length=1)
    authority_boundary: dict[str, Any] = Field(
        default_factory=data_requirement_authority_boundary
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("legacy_admissible_data_source_families", mode="before")
    @classmethod
    def _clean_family_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _derive_legacy_families(self) -> DataRequirementCompilationReport:
        if not self.legacy_admissible_data_source_families:
            families = tuple(
                dict.fromkeys(
                    family
                    for spec in self.specs
                    for family in spec.required_data_families
                )
            )
            object.__setattr__(self, "legacy_admissible_data_source_families", families)
        if self.runtime_event_ref is None:
            object.__setattr__(
                self,
                "runtime_event_ref",
                f"event://data-requirement/{_slug(self.run_id)}",
            )
        if not self.authority_boundary:
            object.__setattr__(
                self,
                "authority_boundary",
                data_requirement_authority_boundary(),
            )
        return self


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return tuple(cleaned)


def _slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {".", "_", "-"} else "-" for ch in value)
    return slug.strip("-") or "run"


__all__ = [
    "DATA_REQUIREMENT_COMPILATION_SCHEMA_VERSION",
    "DATA_REQUIREMENT_SPEC_SCHEMA_VERSION",
    "DataQualityMinimums",
    "DataRequirementCompilationReport",
    "DataRequirementScope",
    "DataRequirementSpec",
    "DataRequirementTimeRole",
    "LineageStrictness",
    "TransformationTolerance",
    "data_requirement_authority_boundary",
]
