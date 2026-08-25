"""Policy Evidence Capability Index DTOs.

The capability index is a release-time authority projection over existing
production-data layers. These DTOs are deliberately strict: an index record is
allowed to be incomplete only through explicit authority states, limitations,
or failure-mode nodes, not through silent extra fields.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.contracts.capability_discovery import (  # noqa: TC001
    CapabilityResourceKind,
    CapabilityTimeSemantics,
)

CAPABILITY_INDEX_SCHEMA_VERSION = "policyos.evidence_capability_index.v1"
EVIDENCE_CAPABILITY_SCHEMA_VERSION = "policyos.evidence_capability.v1"
CAPABILITY_SOURCE_ASSET_SCHEMA_VERSION = "policyos.capability_source_asset.v1"
CAPABILITY_FAILURE_MODE_SCHEMA_VERSION = "policyos.capability_failure_mode.v1"
ACQUISITION_STRATEGY_SCHEMA_VERSION = "policyos.capability_acquisition_strategy.v1"
CONFLICT_RECORD_SCHEMA_VERSION = "policyos.runtime.construct_conflict_record.v1"

PRODUCTION_ADMISSIBLE_STATES = frozenset(
    {
        "admissible",
        "admissible_with_limitation",
        "admissible_with_proxy_limitation",
        "publishable",
    }
)
SIMULATION_ONLY_EVIDENCE_MODES = frozenset({"simulation_only"})
SIMULATION_MODALITIES = frozenset({"simulation_state"})


class CapabilityScope(BaseModel):
    """Semantic scope over which a capability can be considered."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    geography: str = Field(min_length=1)
    time_start: str | None = None
    time_end: str | None = None
    schema_regime: str | None = None
    population: str | None = None
    entity_scope: str = Field(min_length=1)
    jurisdiction: str | None = None
    spatial_granularity: str | None = None
    temporal_granularity: str | None = None

    @field_validator("geography", "entity_scope")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "time_start",
        "time_end",
        "schema_regime",
        "population",
        "jurisdiction",
        "spatial_granularity",
        "temporal_granularity",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class CapabilitySourceAsset(BaseModel):
    """One producer-side input that supports or limits a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.capability_source_asset.v1"] = (
        CAPABILITY_SOURCE_ASSET_SCHEMA_VERSION
    )
    ref: str = Field(min_length=1)
    source_layer: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    role: str = Field(min_length=1)
    path: str | None = None
    table: str | None = None
    row_count: int | None = Field(default=None, ge=0)
    fields: tuple[str, ...] = Field(default=())
    compatibility_only: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ref", "source_layer", "asset_type", "role")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("path", "table")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("fields", mode="before")
    @classmethod
    def _coerce_fields(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class AuthorityEnvelope(BaseModel):
    """Purpose-scoped admissibility states for a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    research: str = Field(min_length=1)
    governed_pilot: str = Field(min_length=1)
    production: str = Field(min_length=1)
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())
    authority_basis: tuple[str, ...] = Field(default=())

    @field_validator("research", "governed_pilot", "production")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("authoritative_for", "may_not_use_for", "authority_basis", mode="before")
    @classmethod
    def _coerce_tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class RightsEnvelope(BaseModel):
    """Access and export rights relevant to evidence authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    access_class: str = Field(min_length=1)
    public_export_allowed: str = "aggregate_only"
    claim_evidence_use_allowed: bool = True
    license: str | None = None
    restrictions: tuple[str, ...] = Field(default=())

    @field_validator("access_class", "public_export_allowed")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("license")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("restrictions", mode="before")
    @classmethod
    def _coerce_restrictions(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class FreshnessEnvelope(BaseModel):
    """Freshness and release-time context for a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    freshness_class: str = Field(min_length=1)
    last_updated: str | None = None
    observed_through: str | None = None
    source_release_ref: str | None = None

    @field_validator("freshness_class")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("last_updated", "observed_through", "source_release_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class QualityScore(BaseModel):
    """Composite and dimension-level quality score."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    composite: float = Field(ge=0.0, le=1.0)
    breakdown: dict[str, float] = Field(default_factory=dict)

    @field_validator("breakdown")
    @classmethod
    def _validate_breakdown(cls, value: dict[str, float]) -> dict[str, float]:
        clean: dict[str, float] = {}
        for key, score in sorted(value.items()):
            normalized_key = _required_text(str(key))
            numeric = float(score)
            if numeric < 0.0 or numeric > 1.0:
                raise ValueError(f"quality breakdown score out of range: {normalized_key}")
            clean[normalized_key] = numeric
        return clean


class CapabilityLifecycle(BaseModel):
    """Lifecycle state and replay rule refs for a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    state: Literal["draft", "governed", "active", "deprecated", "withdrawn"] = "active"
    rule_version_ref: str = "capability-index-v1.0"
    superseded_by: str | None = None
    deprecation_reason: str | None = None
    retired_at: str | None = None

    @field_validator("rule_version_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("superseded_by", "deprecation_reason", "retired_at")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class FailureModeNode(BaseModel):
    """First-class missing or blocked evidence node for acquisition planning."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        strict=True,
    )

    schema_version: Literal["policyos.capability_failure_mode.v1"] = (
        CAPABILITY_FAILURE_MODE_SCHEMA_VERSION
    )
    failure_id: str = Field(min_length=1)
    construct_id: str = Field(alias="construct", min_length=1)
    geography: str = Field(min_length=1)
    cause_class: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    acquisition_strategy_refs: tuple[str, ...] = Field(default=())
    affected_authority_postures: tuple[str, ...] = Field(default=())
    detected_at: str
    last_review_at: str | None = None
    status: str = Field(default="blocked_acquisition_required", min_length=1)
    gap_type: str = Field(default="acquisition_gap", min_length=1)
    domain: tuple[str, ...] = Field(default=())
    producer_owner: str | None = None
    authority_posture: str = Field(default="production", min_length=1)
    ttl: str | None = None
    review_cadence: str | None = None
    escalation_owner: str | None = None

    @field_validator(
        "acquisition_strategy_refs",
        "affected_authority_postures",
        "domain",
        mode="before",
    )
    @classmethod
    def _coerce_tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator(
        "producer_owner",
        "ttl",
        "review_cadence",
        "escalation_owner",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class AcquisitionStrategy(BaseModel):
    """Owned strategy for closing a first-class capability gap."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.capability_acquisition_strategy.v1"] = (
        ACQUISITION_STRATEGY_SCHEMA_VERSION
    )
    strategy_id: str = Field(min_length=1)
    target_construct: str = Field(min_length=1)
    owner: tuple[str, ...] = Field(min_length=1)
    authority_class: str = Field(min_length=1)
    estimated_cost: str = Field(min_length=1)
    estimated_time: str = Field(min_length=1)
    prerequisites: tuple[str, ...] = Field(default=())
    resulting_authority_envelope: dict[str, str] = Field(default_factory=dict)
    contact_path: str = Field(
        default="ops://team-data-acquisition#acquisitions",
        min_length=1,
    )
    owner_team: str | None = None
    legal_counsel_owner: str | None = None
    ttl: str = Field(default="P30D", min_length=1)
    review_cadence: str = Field(default="P14D", min_length=1)
    escalation_owner: str | None = None
    requires_construct_validity_review: bool = True

    @field_validator("owner", "prerequisites", mode="before")
    @classmethod
    def _coerce_tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator(
        "owner_team",
        "legal_counsel_owner",
        "escalation_owner",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _validate_owned_strategy(self) -> AcquisitionStrategy:
        if not self.owner:
            raise ValueError("acquisition strategies require at least one owner")
        if not self.prerequisites:
            raise ValueError("acquisition strategies require prerequisites")
        owner_team = self.owner_team or _first_non_legal_owner(self.owner)
        if owner_team is None:
            raise ValueError("acquisition strategies require a non-legal owner team")
        legal_counsel_owner = self.legal_counsel_owner or _first_legal_owner(self.owner)
        if _government_data_involved(self.authority_class) and legal_counsel_owner is None:
            raise ValueError("government acquisition strategies require legal counsel owner")
        production_state = self.resulting_authority_envelope.get("production")
        if production_state == "admissible" and not self.requires_construct_validity_review:
            raise ValueError(
                "production admissible acquisition strategies require "
                "requires_construct_validity_review"
            )
        object.__setattr__(self, "owner_team", owner_team)
        object.__setattr__(self, "legal_counsel_owner", legal_counsel_owner)
        object.__setattr__(self, "escalation_owner", self.escalation_owner or owner_team)
        return self


class EvidenceCapability(BaseModel):
    """One authority-scoped capability compiled from producer-backed assets."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        strict=True,
    )

    schema_version: Literal["policyos.evidence_capability.v1"] = EVIDENCE_CAPABILITY_SCHEMA_VERSION
    capability_id: str = Field(min_length=1)
    construct_id: str = Field(alias="construct", min_length=1)
    modality: tuple[str, ...] = Field(min_length=1)
    evidence_mode: str = Field(min_length=1)
    concept_spine_refs: tuple[str, ...] = Field(default=())
    scope: CapabilityScope
    identification_mode: str = Field(min_length=1)
    trust_tier: str = Field(min_length=1)
    quality_score: QualityScore
    source_assets: tuple[CapabilitySourceAsset, ...] = Field(default=())
    method_contract_targets: tuple[str, ...] = Field(default=())
    proxy_validation: dict[str, Any] = Field(default_factory=dict)
    limitations: tuple[str, ...] = Field(default=())
    authority_envelope: AuthorityEnvelope
    lineage_refs: tuple[str, ...] = Field(default=())
    freshness_envelope: FreshnessEnvelope
    rights_envelope: RightsEnvelope
    capability_lifecycle: CapabilityLifecycle = Field(default_factory=CapabilityLifecycle)
    conflict_summary: dict[str, Any] = Field(default_factory=dict)
    may_not_use_for: tuple[str, ...] = Field(default=())
    compatibility_only: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "capability_id",
        "construct_id",
        "evidence_mode",
        "identification_mode",
        "trust_tier",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "modality",
        "concept_spine_refs",
        "method_contract_targets",
        "limitations",
        "lineage_refs",
        "may_not_use_for",
        mode="before",
    )
    @classmethod
    def _coerce_tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_authority_boundary(self) -> EvidenceCapability:
        if self.compatibility_only and not any(
            "compatibility" in purpose for purpose in self.may_not_use_for
        ):
            object.__setattr__(
                self,
                "may_not_use_for",
                tuple(
                    sorted(
                        {
                            *self.may_not_use_for,
                            "production_data_authority_without_l1_l6_support",
                        }
                    )
                ),
            )
        return self


class CapabilityConflictRecord(BaseModel):
    """W8.E-compatible same-construct conflict projection."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        strict=True,
    )

    schema_version: Literal["policyos.runtime.construct_conflict_record.v1"] = (
        CONFLICT_RECORD_SCHEMA_VERSION
    )
    conflict_id: str = Field(min_length=1)
    construct_id: str = Field(alias="construct", min_length=1)
    geography: str = Field(min_length=1)
    conflict_class: str = Field(min_length=1)
    conflict_resolution_route: str = Field(min_length=1)
    capability_refs: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(default=())
    status: str = "contested"

    @field_validator("capability_refs", "evidence_refs", mode="before")
    @classmethod
    def _coerce_tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class CapabilityIndex(BaseModel):
    """Signed release-time capability index payload before persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.evidence_capability_index.v1"] = (
        CAPABILITY_INDEX_SCHEMA_VERSION
    )
    compiler_version: str = Field(min_length=1)
    release_ref: str = Field(min_length=1)
    mode: Literal["fixture", "full", "incremental"]
    capabilities: tuple[EvidenceCapability, ...] = Field(default=())
    failure_modes: tuple[FailureModeNode, ...] = Field(default=())
    acquisition_strategies: tuple[AcquisitionStrategy, ...] = Field(default=())
    conflicts: tuple[CapabilityConflictRecord, ...] = Field(default=())
    white_space: tuple[FailureModeNode, ...] = Field(default=())
    generated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "capabilities",
        "failure_modes",
        "acquisition_strategies",
        "conflicts",
        "white_space",
        mode="before",
    )
    @classmethod
    def _coerce_tuple_objects(cls, value: object) -> tuple[Any, ...]:
        if value is None:
            return ()
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        raise TypeError("expected sequence")


class LegalNormOwnerTruth(BaseModel):
    """Grounded Lex truth required before an L3 row becomes a legal capability."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.lex.legal_norm_truth.v1"] = "policyos.lex.legal_norm_truth.v1"
    legal_norm_ref: str = Field(min_length=1)
    normative_fact_ref: str = Field(min_length=1)
    source_document_ref: str = Field(min_length=1)
    provision_citation: str = Field(min_length=1)
    grounding_status: Literal["grounded"]
    hallucination_status: Literal["verified_clear"]
    jurisdiction: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None
    temporal_state: Literal["effective"]
    temporal_resolution_status: Literal["resolved"]
    temporal_snapshot_at: datetime
    temporal_audit_ref: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _temporal_interval_contains_release_snapshot(self) -> LegalNormOwnerTruth:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("legal norm effective_to cannot precede effective_from")
        if self.temporal_snapshot_at.tzinfo is None:
            raise ValueError("legal norm temporal snapshot must be timezone-aware")
        snapshot_date = self.temporal_snapshot_at.astimezone(UTC).date()
        if snapshot_date < self.effective_from:
            raise ValueError("legal norm is not yet effective at the release snapshot")
        if self.effective_to is not None and snapshot_date > self.effective_to:
            raise ValueError("legal norm is expired at the release snapshot")
        return self


class ScientistCapabilityOwnerTruth(BaseModel):
    """One Scientist NodeRegistry or ToolRegistry capability entry receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.scientist.capability_owner_truth.v1"] = (
        "policyos.scientist.capability_owner_truth.v1"
    )
    capability_ref: str = Field(min_length=1)
    registry_kind: Literal["node_registry", "tool_registry"]
    registry_schema_ref: Literal[
        "scientist.node_registry.v1",
        "scientist.tool_registry.v1",
    ]
    registry_entry_ref: str = Field(min_length=1)
    registry_snapshot_ref: str = Field(min_length=1)
    registry_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provenance_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _registry_kind_matches_schema(self) -> ScientistCapabilityOwnerTruth:
        expected = {
            "node_registry": "scientist.node_registry.v1",
            "tool_registry": "scientist.tool_registry.v1",
        }[self.registry_kind]
        if self.registry_schema_ref != expected:
            raise ValueError("Scientist registry kind must match its schema")
        return self


class CapabilityIndexDiscoveryRow(BaseModel):
    """Owner-projected capability row consumed by discovery federation.

    This row carries searched index identity and candidate content only. It is
    neither an execution registration nor an authority decision.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    capability_ref: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    resource_kind: CapabilityResourceKind
    construct_refs: tuple[str, ...] = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    producer_ref: str = Field(min_length=1)
    snapshot_ref: str = Field(min_length=1)
    freshness_ref: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = Field(min_length=1)
    owner_truth: LegalNormOwnerTruth | ScientistCapabilityOwnerTruth | None = None
    may_not_use_for: tuple[str, ...] = Field(default=())
    time: CapabilityTimeSemantics

    @model_validator(mode="after")
    def _kind_requires_its_exact_owner_truth(self) -> CapabilityIndexDiscoveryRow:
        if self.resource_kind == "legal_norm":
            if type(self.owner_truth) is not LegalNormOwnerTruth:
                raise ValueError("legal_norm rows require LegalNormOwnerTruth")
            if self.owner_truth.legal_norm_ref != self.capability_ref:
                raise ValueError("Lex owner truth must bind capability_ref")
            if not set(self.owner_truth.provenance_refs) <= set(self.provenance_refs):
                raise ValueError("Lex owner truth provenance must be carried by the row")
        elif self.resource_kind == "agent":
            if type(self.owner_truth) is not ScientistCapabilityOwnerTruth:
                raise ValueError("agent rows require ScientistCapabilityOwnerTruth")
            if self.owner_truth.capability_ref != self.capability_ref:
                raise ValueError("Scientist owner truth must bind capability_ref")
            if not set(self.owner_truth.provenance_refs) <= set(self.provenance_refs):
                raise ValueError("Scientist owner truth provenance must be carried by the row")
        elif self.owner_truth is not None:
            raise ValueError("owner_truth is only valid for legal_norm or agent rows")
        return self


def capability_is_production_admissible(capability: EvidenceCapability) -> bool:
    """Return whether the production slot claims an admissible authority state."""

    return capability.authority_envelope.production in PRODUCTION_ADMISSIBLE_STATES


def _required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_required_text(value),)
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError("expected a sequence of text values")
    return tuple(sorted({_required_text(str(item)) for item in value}))


def _first_non_legal_owner(owner: tuple[str, ...]) -> str | None:
    for item in owner:
        if "legal" not in item.casefold() and "counsel" not in item.casefold():
            return item
    return None


def _first_legal_owner(owner: tuple[str, ...]) -> str | None:
    for item in owner:
        normalized = item.casefold()
        if "legal" in normalized or "counsel" in normalized:
            return item
    return None


def _government_data_involved(authority_class: str) -> bool:
    normalized = authority_class.casefold()
    return any(
        marker in normalized for marker in ("government", "official", "registry", "administrative")
    )
