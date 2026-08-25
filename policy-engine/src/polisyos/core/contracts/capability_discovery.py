"""Canonical candidate-grade capability discovery contracts.

Discovery, execution, and admitted authority are independent sibling results.
No search or discovery value in this module grants execution or authority.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime import ApiMeta
from .search import SearchFrontier, SearchRequest

CAPABILITY_DISCOVERY_SCHEMA_VERSION = "policyos.capability_discovery.v1"

DiscoveryPosture = Literal["discoverable", "executable", "admitted_authority"]
CapabilityResourceKind = Literal[
    "method",
    "dataset",
    "source",
    "legal_norm",
    "case",
    "agent",
]
CapabilityDiscoveryAudience = Literal["REVIEWER", "EXPERT", "MACHINE"]
CapabilityFreshness = Literal["current", "stale", "unknown"]
CapabilityDiscoveryState = Literal[
    "discoverable",
    "no_match",
    "producer_missing",
    "producer_unavailable",
    "index_unavailable",
    "index_stale",
    "recall_unmeasured",
    "budget_cutoff",
    "incomplete",
]
CapabilityExecutionState = Literal[
    "executable",
    "not_executable",
    "operation_missing",
    "conformance_failed",
    "policy_disabled",
    "producer_missing",
    "execution_blocked",
    "not_established",
]
CapabilityAuthorityState = Literal[
    "admitted_authority",
    "candidate_only",
    "producer_missing",
    "bridge_missing",
    "artifact_missing",
    "invalid_source",
    "revalidation_required",
    "authority_blocked",
    "not_established",
]


class _CapabilityDiscoveryModel(BaseModel):
    """Strict immutable base for the cross-runtime discovery contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CapabilityTimeSemantics(_CapabilityDiscoveryModel):
    """Producer observation, validity interval, and declared freshness."""

    observed_at: datetime
    valid_from: datetime
    valid_until: datetime | None
    freshness: CapabilityFreshness

    @model_validator(mode="after")
    def _time_roles_are_ordered_and_timezone_aware(self) -> CapabilityTimeSemantics:
        values = (self.observed_at, self.valid_from, self.valid_until)
        if any(value is not None and value.tzinfo is None for value in values):
            raise ValueError("capability time semantics must be timezone-aware")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class CapabilityDiscoveryRequest(_CapabilityDiscoveryModel):
    """Capability kind filter wrapped around a real semantic search request."""

    search: SearchRequest
    resource_kinds: tuple[CapabilityResourceKind, ...] = Field(min_length=1)
    audience: CapabilityDiscoveryAudience

    @model_validator(mode="after")
    def _resource_kind_filter_is_unique(self) -> CapabilityDiscoveryRequest:
        if len(set(self.resource_kinds)) != len(self.resource_kinds):
            raise ValueError("resource_kinds must not contain duplicates")
        return self


class _CapabilityPostureResult(_CapabilityDiscoveryModel):
    """Evidence fields shared by each independently produced posture result."""

    producer_ref: str = Field(min_length=1)
    reason_codes: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = Field(min_length=1)
    time: CapabilityTimeSemantics


class CapabilityDiscoveryPostureResult(_CapabilityPostureResult):
    """Typed searched-index result, never execution or authority evidence."""

    state: CapabilityDiscoveryState
    snapshot_ref: str | None = None
    freshness_ref: str | None = None

    @model_validator(mode="after")
    def _discovery_state_has_index_evidence_or_negative(self) -> CapabilityDiscoveryPostureResult:
        searched_state = self.state in {"discoverable", "no_match"}
        if searched_state and (not self.snapshot_ref or not self.freshness_ref):
            raise ValueError("searched discovery states require snapshot_ref and freshness_ref")
        if self.state == "discoverable" and self.reason_codes:
            raise ValueError("discoverable cannot carry negative reason_codes")
        if self.state != "discoverable" and not self.reason_codes:
            raise ValueError("negative discovery states require reason_codes")
        return self


class CapabilityExecutionPostureResult(_CapabilityPostureResult):
    """Typed live-registry, conformance, and policy execution result."""

    state: CapabilityExecutionState
    operation_ref: str | None = None
    conformance_ref: str | None = None
    policy_ref: str | None = None

    @model_validator(mode="after")
    def _execution_positive_has_all_independent_inputs(self) -> CapabilityExecutionPostureResult:
        if self.state == "executable":
            if not self.operation_ref:
                raise ValueError("executable requires operation_ref")
            if not self.conformance_ref:
                raise ValueError("executable requires conformance_ref")
            if not self.policy_ref:
                raise ValueError("executable requires policy_ref")
            if self.reason_codes:
                raise ValueError("executable cannot carry negative reason_codes")
        elif not self.reason_codes:
            raise ValueError("negative execution states require reason_codes")
        return self


class CapabilityAuthorityPostureResult(_CapabilityPostureResult):
    """Typed purpose-bound authority result independent of discovery/execution."""

    state: CapabilityAuthorityState
    authority_purpose: str = Field(min_length=1)
    binding_ref: str | None = None
    currentness_ref: str | None = None

    @model_validator(mode="after")
    def _authority_positive_has_binding_and_currentness(self) -> CapabilityAuthorityPostureResult:
        if self.state == "admitted_authority":
            if not self.binding_ref:
                raise ValueError("admitted_authority requires binding_ref")
            if not self.currentness_ref:
                raise ValueError("admitted_authority requires currentness_ref")
            if self.reason_codes:
                raise ValueError("admitted_authority cannot carry negative reason_codes")
        elif not self.reason_codes:
            raise ValueError("negative authority states require reason_codes")
        return self


class CapabilityDiscoveryItem(_CapabilityDiscoveryModel):
    """One candidate with three sibling posture results and authority boundaries."""

    schema_version: Literal["policyos.capability_discovery.v1"] = (
        CAPABILITY_DISCOVERY_SCHEMA_VERSION
    )
    capability_ref: str = Field(min_length=1)
    content_digest: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    resource_kind: CapabilityResourceKind
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    discovery_result: CapabilityDiscoveryPostureResult
    execution_result: CapabilityExecutionPostureResult
    authority_result: CapabilityAuthorityPostureResult
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    authority_purpose: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    time: CapabilityTimeSemantics

    @model_validator(mode="after")
    def _authority_boundary_matches_authority_arm(self) -> CapabilityDiscoveryItem:
        if self.authority_result.authority_purpose != self.authority_purpose:
            raise ValueError("authority_result purpose must match item authority_purpose")
        overlap = set(self.authoritative_for) & set(self.may_not_use_for)
        if overlap:
            raise ValueError("authoritative_for and may_not_use_for must be disjoint")
        if self.authority_result.state == "admitted_authority":
            if self.authority_purpose not in self.authoritative_for:
                raise ValueError("admitted authority must include its purpose in authoritative_for")
        elif self.authoritative_for:
            raise ValueError("non-authority posture cannot populate authoritative_for")
        return self


class CapabilityDiscoveryResponse(_CapabilityDiscoveryModel):
    """Replayable capability discovery response with candidate-grade frontier truth."""

    schema_version: Literal["policyos.capability_discovery.v1"] = (
        CAPABILITY_DISCOVERY_SCHEMA_VERSION
    )
    meta: ApiMeta
    request: CapabilityDiscoveryRequest
    request_digest: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    authority_purpose: str = Field(min_length=1)
    audience: CapabilityDiscoveryAudience
    results: tuple[CapabilityDiscoveryItem, ...]
    frontier: SearchFrontier
    rule_version: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = Field(min_length=1)
    time: CapabilityTimeSemantics

    @model_validator(mode="after")
    def _response_binds_request_results_and_frontier(self) -> CapabilityDiscoveryResponse:
        if self.authority_purpose != self.request.search.authority_purpose:
            raise ValueError("response authority_purpose must match the search request")
        if self.audience != self.request.audience:
            raise ValueError("response audience must match the discovery request")
        refs = [item.capability_ref for item in self.results]
        if len(set(refs)) != len(refs):
            raise ValueError("capability_ref values must be unique")
        if any(item.authority_purpose != self.authority_purpose for item in self.results):
            raise ValueError("result authority_purpose must match the response")
        if any(item.rule_version != self.rule_version for item in self.results):
            raise ValueError("result rule_version must match the response")
        selected_refs = [candidate.candidate_ref for candidate in self.frontier.candidates]
        if selected_refs != refs:
            raise ValueError("results must preserve selected SearchLedger candidate order")
        return self


__all__ = [
    "CAPABILITY_DISCOVERY_SCHEMA_VERSION",
    "CapabilityAuthorityPostureResult",
    "CapabilityAuthorityState",
    "CapabilityDiscoveryAudience",
    "CapabilityDiscoveryItem",
    "CapabilityDiscoveryPostureResult",
    "CapabilityDiscoveryRequest",
    "CapabilityDiscoveryResponse",
    "CapabilityDiscoveryState",
    "CapabilityExecutionPostureResult",
    "CapabilityExecutionState",
    "CapabilityFreshness",
    "CapabilityResourceKind",
    "CapabilityTimeSemantics",
    "DiscoveryPosture",
]
