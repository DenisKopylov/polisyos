"""Neutral requirement-to-capability resolution contracts.

This module is intentionally orchestration-free. Runtime owns loading and
authority composition; lower-level compilers depend only on these DTOs and
ports.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION = "policyos.requirement_to_capability_query.v1"
CAPABILITY_SOURCE_DISCOVERY_SCHEMA_VERSION = "policyos.capability_source_discovery.v1"

AuthorityPosture = Literal["research", "governed_pilot", "production"]


class ScenarioFamilyConstructRow(BaseModel):
    """Governed source-family alias row used by legacy projections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_family: str = Field(min_length=1)
    construct_id: str = Field(alias="construct", serialization_alias="construct", min_length=1)
    producer_ref: str = Field(min_length=1)

    @property
    def construct(self) -> str:
        """Return the construct selector using the public row field name."""

        return self.construct_id

    @field_validator("scenario_family", "construct_id", "producer_ref", mode="before")
    @classmethod
    def _clean_required_text(cls, value: object) -> str:
        text = _optional_text(value) or ""
        if not text:
            raise ValueError("value must not be blank")
        return text

    @field_validator("construct_id", mode="before")
    @classmethod
    def _clean_construct(cls, value: object) -> str:
        return _bare_construct(value)


type ScenarioFamilyConstructRows = Iterable[ScenarioFamilyConstructRow | Mapping[str, Any]]


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


class CapabilitySourceCandidate(BaseModel):
    """A content-bound source descriptor requiring independent native admission.

    The descriptor is the actual owner's complete JSON capability row. Its
    identity check establishes which row was searched, never source truth,
    rights, freshness, execution permission, or claim-evidence authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_ref: str = Field(min_length=1)
    construct_ref: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    descriptor: dict[str, Any]
    limitations: tuple[str, ...] = Field(min_length=1)

    @property
    def source_assets(self) -> tuple[Mapping[str, Any], ...]:
        """Return the owner's source descriptors without promoting them."""
        return tuple(self.descriptor["source_assets"])

    @property
    def scope(self) -> Mapping[str, Any]:
        """Return the source's declared scope, separately from the query."""
        return self.descriptor["scope"]

    @model_validator(mode="after")
    def _bind_descriptor(self) -> CapabilitySourceCandidate:
        if self.descriptor.get("capability_id") != self.capability_ref:
            raise ValueError("candidate_source_descriptor_identity_mismatch")
        if _bare_construct(self.descriptor.get("construct")) != _bare_construct(self.construct_ref):
            raise ValueError("candidate_source_descriptor_construct_mismatch")
        assets = self.descriptor.get("source_assets")
        if (
            not isinstance(assets, list | tuple)
            or not assets
            or any(
                not isinstance(asset, Mapping) or not _optional_text(asset.get("ref"))
                for asset in assets
            )
        ):
            raise ValueError("candidate_source_descriptor_assets_missing")
        if not isinstance(self.descriptor.get("scope"), Mapping):
            raise ValueError("candidate_source_descriptor_scope_missing")
        encoded = json.dumps(
            self.descriptor,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if self.content_digest != "sha256:" + hashlib.sha256(encoded).hexdigest():
            raise ValueError("candidate_source_descriptor_digest_mismatch")
        return self


class CapabilitySourceDiscoveryUnavailableError(RuntimeError):
    """Declare an optional source-discovery outage without erasing claim work."""

    def __init__(self, reason_code: str) -> None:
        if not isinstance(reason_code, str) or not reason_code.strip():
            raise ValueError("candidate_source_discovery_unavailable_reason_missing")
        self.reason_code = reason_code.strip()
        super().__init__(f"candidate_source_discovery_unavailable:{self.reason_code}")


class CapabilitySourceDiscoveryResult(BaseModel):
    """Candidate source lookup beside, never replacing, claim resolution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.capability_source_discovery.v1"] = (
        CAPABILITY_SOURCE_DISCOVERY_SCHEMA_VERSION
    )
    purpose: Literal["candidate_source_discovery"] = "candidate_source_discovery"
    query: RequirementToCapabilityQuery
    capability_index_ref: str = Field(min_length=1)
    rule_version_ref: str = Field(min_length=1)
    state: Literal["candidates_returned", "no_match"]
    candidates: tuple[CapabilitySourceCandidate, ...] = ()
    rejected_candidates: tuple[dict[str, Any], ...] = ()
    limitations: tuple[str, ...] = (
        "finite_loaded_index_slice_only",
        "discovery_is_not_source_admission",
        "discovery_is_not_claim_evidence",
        "descriptor_identity_does_not_establish_external_source_provenance",
    )
    satisfies_claim_evidence: Literal[False] = False
    requires_native_source_admission: Literal[True] = True

    @field_serializer("query")
    def _serialize_query(self, value: RequirementToCapabilityQuery) -> dict[str, Any]:
        return value.model_dump(mode="json", by_alias=True)

    @model_validator(mode="after")
    def _bind_original_query(self) -> CapabilitySourceDiscoveryResult:
        if bool(self.candidates) != (self.state == "candidates_returned"):
            raise ValueError("candidate_source_discovery_state_mismatch")
        refs = [candidate.capability_ref for candidate in self.candidates]
        if len(refs) != len(set(refs)):
            raise ValueError("candidate_source_discovery_duplicate_descriptor")
        if any(
            _bare_construct(candidate.construct_ref) != self.query.construct
            for candidate in self.candidates
        ):
            raise ValueError("candidate_source_discovery_query_construct_mismatch")
        return self


@runtime_checkable
class CapabilityCandidateDiscoveryPort(Protocol):
    """Optional source lookup; existing authority-only resolver ports stay valid."""

    def discover_sources(
        self,
        query: RequirementToCapabilityQuery | Mapping[str, Any],
    ) -> CapabilitySourceDiscoveryResult:
        """Return source candidates requiring separate native admission."""


@runtime_checkable
class CapabilityResolverPort(Protocol):
    """Runtime-implemented resolver port consumed by requirement compilers."""

    def resolve(
        self,
        query: RequirementToCapabilityQuery | Mapping[str, Any],
    ) -> CapabilityBindingLike:
        """Resolve a semantic requirement query into a selected or blocked binding."""


def legacy_family_for_construct(
    construct: str,
    *,
    rows: ScenarioFamilyConstructRows = (),
) -> str | None:
    """Return the rollout compatibility projection for a construct."""

    bare = _bare_construct(construct)
    for row in _scenario_family_construct_rows(rows):
        if row.construct == bare:
            return row.scenario_family
    return None


def construct_for_legacy_family(
    value: str,
    *,
    rows: ScenarioFamilyConstructRows = (),
) -> str | None:
    """Return the governed construct mapped from a legacy scenario family."""

    slug = _slug(value)
    for row in _scenario_family_construct_rows(rows):
        if _slug(row.scenario_family) == slug:
            return row.construct
    return None


def _scenario_family_construct_rows(
    rows: ScenarioFamilyConstructRows,
) -> tuple[ScenarioFamilyConstructRow, ...]:
    normalized: list[ScenarioFamilyConstructRow] = []
    for row in rows:
        model = (
            row
            if isinstance(row, ScenarioFamilyConstructRow)
            else ScenarioFamilyConstructRow.model_validate(row)
        )
        normalized.append(model)
    return tuple(normalized)


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
    "CAPABILITY_SOURCE_DISCOVERY_SCHEMA_VERSION",
    "REQUIREMENT_TO_CAPABILITY_QUERY_SCHEMA_VERSION",
    "AuthorityPosture",
    "CapabilityBindingLike",
    "CapabilityCandidateDiscoveryPort",
    "CapabilityResolverPort",
    "CapabilitySourceCandidate",
    "CapabilitySourceDiscoveryResult",
    "CapabilitySourceDiscoveryUnavailableError",
    "RequirementTimeWindow",
    "RequirementToCapabilityQuery",
    "ScenarioFamilyConstructRow",
    "ScenarioFamilyConstructRows",
    "construct_for_legacy_family",
    "legacy_family_for_construct",
]
