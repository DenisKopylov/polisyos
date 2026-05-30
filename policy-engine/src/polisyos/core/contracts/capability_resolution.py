"""Neutral requirement-to-capability resolution contracts.

This module is intentionally orchestration-free. Runtime owns loading and
authority composition; lower-level compilers depend only on these DTOs and
ports.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION = (
    "policyos.requirement_to_capability_query.v1"
)
REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS: dict[str, str] = {
    "production_msme_panel": "firm_survival",
    "regional_displacement_indicators": "regional_displacement_pressure",
    "credit_program_registry": "credit_program_enrollment",
}
CONSTRUCT_TO_LEGACY_SCENARIO_FAMILY: dict[str, str] = {
    construct: family
    for family, construct in REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS.items()
}

AuthorityPosture = Literal["research", "governed_pilot", "production"]


class RequirementTimeWindow(BaseModel):
    """Claim time window used by capability resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    start: str | None = None
    end: str | None = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def _clean_optional_text(cls, value: object) -> str | None:
        return _optional_text(value)


class RequirementToCapabilityQuery(BaseModel):
    """Semantic query from a requirement to a producer-backed capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.requirement_to_capability_query.v1"] = (
        REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION
    )
    requirement_id: str = Field(min_length=1)
    construct_id: str = Field(alias="construct", serialization_alias="construct", min_length=1)
    entity_scope: str = Field(min_length=1)
    population_filter: Mapping[str, Any] = Field(default_factory=dict)
    geography: str = Field(min_length=1)
    time_window: RequirementTimeWindow = Field(default_factory=RequirementTimeWindow)
    authority_level: AuthorityPosture = "governed_pilot"
    claim_use: str = Field(min_length=1)
    required_evidence_modes: tuple[str, ...] = (
        "observed",
        "derived",
        "proxy_observational",
    )
    forbidden_evidence_modes: tuple[str, ...] = (
        "simulation_only",
        "candidate_unverified",
    )
    required_modalities: tuple[str, ...] = Field(default=())
    required_schema_regime: str | None = None
    min_sample_size: int | None = Field(default=None, ge=0)
    source_family_alias: str | None = None

    @field_validator(
        "requirement_id",
        "entity_scope",
        "geography",
        "claim_use",
        "required_schema_regime",
        "source_family_alias",
        mode="before",
    )
    @classmethod
    def _clean_text(cls, value: object) -> str | None:
        return _optional_text(value)

    @property
    def construct(self) -> str:
        """Return the construct selector using the legacy Python attribute name."""

        return self.construct_id

    @field_validator("construct_id", mode="before")
    @classmethod
    def _clean_construct(cls, value: object) -> str:
        return _bare_construct(value)

    @field_validator(
        "required_evidence_modes",
        "forbidden_evidence_modes",
        "required_modalities",
        mode="before",
    )
    @classmethod
    def _clean_text_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


@runtime_checkable
class CapabilityBindingLike(Protocol):
    """Read-only binding fields required by lower-level requirement compilers."""

    schema_version: str
    rule_version_ref: str
    requirement_id: str | None
    status: str
    selected_capability_ref: str | None
    construct_ref: str | None
    capability_index_ref: str | None
    authority_level: str
    authority_envelope_result: str
    binding_reasons: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    acquisition_strategies: tuple[Mapping[str, Any], ...]
    rejected_alternatives: tuple[Mapping[str, Any], ...]
    conflict_markers: tuple[Mapping[str, Any], ...]


@runtime_checkable
class CapabilityResolverPort(Protocol):
    """Runtime-implemented resolver port consumed by requirement compilers."""

    def resolve(
        self,
        query: RequirementToCapabilityQuery | Mapping[str, Any],
    ) -> CapabilityBindingLike:
        """Resolve a semantic requirement query into a selected or blocked binding."""


def legacy_family_for_construct(construct: str) -> str:
    """Return the rollout compatibility projection for a construct."""

    bare = _bare_construct(construct)
    return CONSTRUCT_TO_LEGACY_SCENARIO_FAMILY.get(bare, bare)


def construct_for_legacy_family(value: str) -> str | None:
    """Return the governed construct mapped from a legacy scenario family."""

    return REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS.get(_slug(value))


def _bare_construct(value: object) -> str:
    text = _optional_text(value) or ""
    if text.startswith("construct:"):
        return text.split(":", 1)[1]
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        values = (value,)
    rows: list[str] = []
    for item in values:
        text = _optional_text(item)
        if text and text not in rows:
            rows.append(text)
    return tuple(rows)


def _slug(value: object) -> str:
    text = _optional_text(value) or ""
    return "_".join(text.casefold().replace("-", "_").split())


__all__ = [
    "CONSTRUCT_TO_LEGACY_SCENARIO_FAMILY",
    "REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS",
    "REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION",
    "AuthorityPosture",
    "CapabilityBindingLike",
    "CapabilityResolverPort",
    "RequirementTimeWindow",
    "RequirementToCapabilityQuery",
    "construct_for_legacy_family",
    "legacy_family_for_construct",
]
