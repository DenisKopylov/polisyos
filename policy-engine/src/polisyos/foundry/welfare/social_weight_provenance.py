"""Social-weight provenance records for welfare value choices.

The objects in this module describe who selected a social-weight schedule and
under which mandate. They are deliberately separate from Pareto frontier facts:
frontier emission can say what is dominated, while this module says who made the
normative value choice used to select one nondominated point.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon

if TYPE_CHECKING:
    from collections.abc import Mapping

SOCIAL_WEIGHT_PROVENANCE_SCHEMA_VERSION = (
    "policyos.foundry.welfare.social_weight_provenance.v1"
)

SocialWeightSourceClass = Literal[
    "governance_decision",
    "participatory_process",
    "expert_review",
    "deterministic_producer",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]
SocialWeightReviewStatus = Literal[
    "pending_review",
    "reviewed",
    "approved",
    "contested",
    "rejected",
    "superseded",
]
SponsorDisclosureStatus = Literal[
    "none_disclosed",
    "disclosed",
    "undisclosed",
    "not_applicable",
    "unknown",
]
ValueChoiceActorRole = Literal[
    "public_authority",
    "elected_body",
    "administrative_agency",
    "participatory_panel",
    "expert_panel",
    "reviewer",
    "analyst",
    "other",
]
MandateType = Literal[
    "statutory",
    "regulatory",
    "delegated",
    "participatory",
    "expert_advisory",
    "court_order",
    "internal_governance",
    "other",
]

_LLM_SOURCE_CLASSES = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})
_PUBLICATION_READY_REVIEWS = frozenset({"reviewed", "approved"})


class SocialWeightProvenanceError(ValueError):
    """Raised when social-weight provenance cannot support a value choice."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class ValueChoiceActor(BaseModel):
    """Person, office, body, or process that chose a social-weight schedule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(min_length=1)
    actor_role: ValueChoiceActorRole
    display_name: str | None = None
    organization_ref: str | None = None

    @field_validator("actor_id", "display_name", "organization_ref")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class SocialWeightMandate(BaseModel):
    """Mandate or process authority under which weights were chosen."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mandate_ref: str = Field(min_length=1)
    mandate_type: MandateType
    authority_scope: str = Field(min_length=1)
    jurisdiction: str | None = None
    expires_at: datetime | None = None

    @field_validator("mandate_ref", "authority_scope", "jurisdiction")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class AffectedGroupWeight(BaseModel):
    """Affected group named in the social-weight schedule or mandate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1)
    weight: float | None = None
    label: str | None = None
    rationale_ref: str | None = None

    @field_validator("group_id", "label", "rationale_ref")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class SocialWeightDissent(BaseModel):
    """Dissent or minority view attached to the social-weight choice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dissent_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    actor_id: str | None = None
    affected_group_ids: tuple[str, ...] = Field(default_factory=tuple)
    dissent_ref: str | None = None

    @field_validator("dissent_id", "summary", "actor_id", "dissent_ref")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("affected_group_ids")
    @classmethod
    def _strip_group_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)


class SponsorDisclosure(BaseModel):
    """Sponsor disclosure record for the process that selected weights."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sponsor_id: str = Field(min_length=1)
    sponsor_name: str = Field(min_length=1)
    interest: str = Field(min_length=1)
    disclosure_ref: str | None = None

    @field_validator("sponsor_id", "sponsor_name", "interest", "disclosure_ref")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class SocialWeightProvenance(BaseModel):
    """Claim-bound provenance for a social-weight schedule.

    LLM-generated material may be recorded as a source class for audit, but it
    cannot be consumed as value-choice authority. Use
    `assert_social_weight_provenance_usable_for_value_choice()` before binding a
    provenance record to a value-choice decision point.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SOCIAL_WEIGHT_PROVENANCE_SCHEMA_VERSION
    provenance_id: str = Field(min_length=1)
    social_weight_ref: str = Field(min_length=1)
    source_class: SocialWeightSourceClass
    chosen_by: tuple[ValueChoiceActor, ...] = Field(min_length=1)
    mandate: SocialWeightMandate
    chosen_at: datetime
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    affected_groups: tuple[AffectedGroupWeight, ...] = Field(min_length=1)
    dissent: tuple[SocialWeightDissent, ...] = Field(default_factory=tuple)
    review_status: SocialWeightReviewStatus
    review_refs: tuple[str, ...] = Field(default_factory=tuple)
    sponsor_disclosure_status: SponsorDisclosureStatus
    sponsor_disclosures: tuple[SponsorDisclosure, ...] = Field(default_factory=tuple)
    claim_refs: tuple[str, ...] = Field(min_length=1)
    audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    authoritative_for: tuple[str, ...] = ("social_weight_provenance",)
    may_not_use_for: tuple[str, ...] = (
        "claim_authority",
        "pareto_frontier_fact",
        "scalar_welfare_authority",
        "projection_authority",
    )

    @field_validator(
        "provenance_id",
        "social_weight_ref",
        "schema_version",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-empty")
        return stripped

    @field_validator("claim_refs", "audit_refs", "review_refs", "authoritative_for")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)

    @field_validator("may_not_use_for")
    @classmethod
    def _strip_limits(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(values)

    @model_validator(mode="after")
    def _validate_provenance(self) -> SocialWeightProvenance:
        if (
            self.valid_until is not None
            and self.valid_from is not None
            and self.valid_until <= self.valid_from
        ):
            raise ValueError("valid_until must be after valid_from")
        if self.sponsor_disclosure_status == "disclosed" and not self.sponsor_disclosures:
            raise ValueError("sponsor_disclosures required when sponsor status is disclosed")
        if self.sponsor_disclosure_status == "none_disclosed" and self.sponsor_disclosures:
            raise ValueError("sponsor_disclosures conflict with none_disclosed status")
        limits = list(self.may_not_use_for)
        if self._needs_value_choice_review() and "value_choice_authority" not in limits:
            object.__setattr__(self, "may_not_use_for", (*limits, "value_choice_authority"))
        return self

    @property
    def is_llm_source(self) -> bool:
        """Whether the weight record originated from an LLM-only source."""

        return self.source_class in _LLM_SOURCE_CLASSES

    @property
    def publication_readiness(self) -> Literal["ready", "review_required", "blocked"]:
        """Publication readiness for surfaces that expose the value choice."""

        if self.is_llm_source or self.review_status in {"rejected", "superseded"}:
            return "blocked"
        if self._needs_value_choice_review():
            return "review_required"
        return "ready"

    def _needs_value_choice_review(self) -> bool:
        if self.review_status not in _PUBLICATION_READY_REVIEWS:
            return True
        if not self.review_refs:
            return True
        return self.sponsor_disclosure_status in {"undisclosed", "unknown"}


def coerce_social_weight_provenance(
    provenance: SocialWeightProvenance | Mapping[str, Any],
) -> SocialWeightProvenance:
    """Normalize a provenance mapping or model into a strict record."""

    if isinstance(provenance, SocialWeightProvenance):
        return provenance
    return SocialWeightProvenance.model_validate(provenance)


def assert_social_weight_provenance_usable_for_value_choice(
    provenance: SocialWeightProvenance | Mapping[str, Any],
) -> SocialWeightProvenance:
    """Fail closed when provenance would launder authority into a value choice."""

    record = coerce_social_weight_provenance(provenance)
    if record.is_llm_source:
        raise SocialWeightProvenanceError(
            "social_weight_llm_source_not_authoritative",
            "LLM social-weight candidates cannot support value-choice authority.",
        )
    if record.review_status in {"rejected", "superseded"}:
        raise SocialWeightProvenanceError(
            "social_weight_review_status_blocked",
            "Rejected or superseded social-weight provenance cannot support a value choice.",
        )
    return record


def assert_social_weight_provenance_publication_ready(
    provenance: SocialWeightProvenance | Mapping[str, Any],
) -> SocialWeightProvenance:
    """Require review and sponsor disclosure before a production publication."""

    record = assert_social_weight_provenance_usable_for_value_choice(provenance)
    if record.publication_readiness == "review_required":
        raise SocialWeightProvenanceError(
            "social_weight_review_required",
            "Social-weight provenance must expose completed review and sponsor disclosure.",
        )
    if record.publication_readiness == "blocked":
        raise SocialWeightProvenanceError(
            "social_weight_publication_blocked",
            "Social-weight provenance is blocked from production publication.",
        )
    return record


def persist_social_weight_provenance(
    store: artifacts.FileSystemCAS,
    provenance: SocialWeightProvenance | Mapping[str, Any],
    *,
    inputs: list[artifacts.InputRef] | None = None,
) -> artifacts.ArtifactRef:
    """Persist social-weight provenance as a CAS artifact."""

    record = coerce_social_weight_provenance(provenance)
    return store.put_json(
        record.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="foundry.social_weight_provenance",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.foundry.welfare.SocialWeightProvenance",
                version=record.schema_version,
            ),
            inputs=inputs,
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def load_social_weight_provenance(
    store: artifacts.FileSystemCAS,
    ref: artifacts.ArtifactRef,
) -> SocialWeightProvenance:
    """Load a persisted social-weight provenance record."""

    payload = canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return SocialWeightProvenance.model_validate(payload)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _clean_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if len(cleaned) != len(values):
        raise ValueError("tuple values must be non-empty and unique")
    return cleaned


__all__ = [
    "SOCIAL_WEIGHT_PROVENANCE_SCHEMA_VERSION",
    "AffectedGroupWeight",
    "SocialWeightDissent",
    "SocialWeightMandate",
    "SocialWeightProvenance",
    "SocialWeightProvenanceError",
    "SponsorDisclosure",
    "ValueChoiceActor",
    "assert_social_weight_provenance_publication_ready",
    "assert_social_weight_provenance_usable_for_value_choice",
    "coerce_social_weight_provenance",
    "load_social_weight_provenance",
    "persist_social_weight_provenance",
]
