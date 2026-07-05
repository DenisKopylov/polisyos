"""Evidence acquisition decision-boundary planner.

The planner implements ADR-0166 as a runtime routing artifact: evidence gaps are
mapped to eligible strategies before VOI ranking is considered. The resulting
records are governance and closeout inputs; they do not satisfy domain evidence
slots.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from importlib import import_module
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon
from polisyos.pdc import SearchTerminalKind, SearchTerminalState, VOISelectionAudit
from polisyos.runtime.quality.substrate_registry import (
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateRegistryError,
    register_substrate_entry,
)

ACQUISITION_PLANNER_SCHEMA_VERSION = "policyos.runtime.acquisition_planner.v1"
ACQUISITION_PLANNER_KIND = "runtime.acquisition_planner_report"
ACQUISITION_PLANNER_SCHEMA_NAME = "polisyos.runtime.quality.AcquisitionPlannerReport"
ACQUISITION_PLANNER_SCHEMA_VERSION_SHORT = "1.0"
ACQUISITION_PLANNER_REPORT_KEY = "acquisition_planner_report"
ACQUISITION_PLANNER_GATE_LAYER = "acquisition_planner"
ACQUISITION_PLANNER_GATE_PHASE = "evidence_acquisition_boundary"
ACQUISITION_RECEIPT_SCHEMA_VERSION = "policyos.runtime.quality.acquisition_receipt.v1"
ACQUISITION_RECEIPT_KIND = "runtime.quality.acquisition_receipt"
ACQUISITION_FAMILY_DENOMINATOR = ("ID", "CERT", "COV", "HV", "HKG", "ADV", "AUD", "SAFE")
DEFAULT_ACQUISITION_TTL_SECONDS = 7 * 24 * 60 * 60

_REPORT_KEYS = (
    "acquisition_planner_report",
    "evidence_acquisition_planner",
    "evidence_acquisition_report",
    "acquisition_planner",
)
_SERIOUS_AUTHORITY_LEVELS = frozenset({"governed", "production", "serious_runtime"})
_LOGGER = logging.getLogger(__name__)
_VOI_PER_COST_THRESHOLD = 0.0001
_SCORED_ACQUISITION_FAMILIES = frozenset({"ID", "CERT", "COV"})
_HOOK_ONLY_ACQUISITION_FAMILIES = frozenset({"HV", "HKG", "ADV", "AUD", "SAFE"})
_REVALIDATION_STAGES = ("identification", "calibration", "value_set", "grounding")
_GROUNDED_STATUSES = frozenset({"current_valid", "grounded_shadow"})
_REAL_OWNER_COMPONENT_PREFIXES = (
    "fabric.retrieval",
    "fabric.ingestion",
    "fabric.data_plane",
    "data_forge.skg",
    "data_forge.openalex",
    "polisyos.fabric",
    "polisyos.data_forge",
)
_ACQUISITION_RATE_BASIS = {
    "enumerator_day_usd": 180.0,
    "expert_hour_usd": 125.0,
    "data_license_day_usd": 60.0,
    "registry_extract_base_usd": 450.0,
}
_ACQUISITION_GAP_BASIS = {
    "local_tourism_site_traffic": {
        "basis_ref": "gap-cost-basis:local_tourism_site_traffic:v1",
        "collection_mode": "site-count intercept survey plus mobile-footfall panel",
        "enumerator_days": 10,
        "expert_hours": 8,
        "data_license_days": 14,
        "calendar_days": 21,
        "authority_gain_base": 0.72,
        "decision_value_base": 0.82,
    },
    "administrative_tax_receipts": {
        "basis_ref": "gap-cost-basis:administrative_tax_receipts:v1",
        "collection_mode": "municipal registry extract plus treasury time-series check",
        "registry_extracts": 1,
        "expert_hours": 5,
        "data_license_days": 3,
        "calendar_days": 9,
        "authority_gain_base": 0.58,
        "decision_value_base": 0.74,
    },
}


class AcquisitionStrategy(StrEnum):
    """Canonical ADR-0166 acquisition strategy values."""

    PUBLIC_REGISTRY = "public_registry"
    AGENCY_REQUEST = "agency_request"
    SURVEY = "survey"
    CONSULTATION = "consultation"
    LEGAL_CORPUS_EXPANSION = "legal_corpus_expansion"
    ACADEMIC_RETRIEVAL = "academic_retrieval"
    PRODUCTION_SNAPSHOT_BUILD = "production_snapshot_build"
    SOURCE_CONTRACT_REMEDIATION = "source_contract_remediation"
    METHOD_REMEDIATION = "method_remediation"
    PROXY_WITH_DEGRADED_AUTHORITY = "proxy_with_degraded_authority"
    ACCEPTED_DEFICIT = "accepted_deficit"
    RERUN = "rerun"
    PUBLISH_WITH_LIMITATION = "publish_with_limitation"
    CLOSEOUT_BLOCK = "closeout_block"


class AcquisitionGapType(StrEnum):
    """ADR-0166 evidence-gap categories used for eligibility."""

    LEGAL_CORPUS_COVERAGE = "legal_corpus_coverage"
    LEGAL_COMPETENCE_AUTHORITY = "legal_competence_authority"
    SCENARIO_SOURCE_FAMILY = "scenario_source_family"
    DATA_SNAPSHOT_RELEASE = "data_snapshot_release"
    FACET = "facet"
    METHOD_OBLIGATION = "method_obligation"
    ACADEMIC_SCHOLAR_SUPPORT = "academic_scholar_support"
    PARTICIPATION_AFFECTED_PERSON_CLAIM = "participation_affected_person_claim"
    COUNTEREVIDENCE_REBUTTAL = "counterevidence_rebuttal"
    COST_SLA_RUNTIME_DEGRADATION = "cost_sla_runtime_degradation"


class RequirementGapFamily(StrEnum):
    """Compiled RequirementSpec family that produced an acquisition gap."""

    DATA = "data_requirement"
    LEGAL_AUTHORITY = "legal_authority_requirement"
    METHOD_VALIDITY = "method_validity_requirement"
    SCHOLAR_SUPPORT = "scholar_support_requirement"
    PARTICIPATION_PROVENANCE = "participation_provenance_requirement"


class AuthorityLevel(StrEnum):
    """Authority level for the gap's active claim scope."""

    RESEARCH = "research"
    GOVERNED = "governed"
    PRODUCTION = "production"


class MandatoryGateState(StrEnum):
    """Mandatory-gate state from ADR-0166."""

    NONE = "none"
    OVERRIDABLE_BY_GOVERNED_COMMIT = "overridable_by_governed_commit"
    NON_OVERRIDABLE = "non_overridable"


class AcquisitionDisposition(StrEnum):
    """Planner disposition after eligibility and VOI filtering."""

    ACQUIRE = "acquire"
    RERUN = "rerun"
    PROXY_WITH_LIMITATION = "proxy_with_limitation"
    ACCEPTED_DEFICIT = "accepted_deficit"
    PUBLISH_WITH_LIMITATION = "publish_with_limitation"
    CLOSEOUT_BLOCK = "closeout_block"


class AcquisitionFamily(StrEnum):
    """N7 acquisition-family taxonomy."""

    ID = "ID"
    CERT = "CERT"
    COV = "COV"
    HV = "HV"
    HKG = "HKG"
    ADV = "ADV"
    AUD = "AUD"
    SAFE = "SAFE"


class AcquisitionGap(BaseModel):
    """One evidence gap requiring acquisition routing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.acquisition_gap.v1"] = (
        "policyos.runtime.acquisition_gap.v1"
    )
    gap_id: str = Field(min_length=1)
    gap_type: AcquisitionGapType
    claim_ref: str = Field(min_length=1)
    scenario_requirement_refs: tuple[str, ...] = Field(default=())
    requirement_gap_ref: str | None = None
    requirement_family: str | None = None
    compiled_requirement_ref: str | None = None
    requirement_schema_version: str | None = None
    missing_requirement_fields: tuple[str, ...] = Field(default=())
    authority_level: AuthorityLevel
    mandatory_gate_state: MandatoryGateState = MandatoryGateState.NONE
    mandatory_gate_refs: tuple[str, ...] = Field(default=())
    limitation_permitted: bool = False
    decision_owner_ref: str | None = None
    producer_output_ref: str | None = None
    calibration_feedback_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("gap_id", "claim_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "scenario_requirement_refs",
        "mandatory_gate_refs",
        "missing_requirement_fields",
        mode="before",
    )
    @classmethod
    def _tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator(
        "requirement_gap_ref",
        "requirement_family",
        "compiled_requirement_ref",
        "requirement_schema_version",
        "decision_owner_ref",
        "producer_output_ref",
        "calibration_feedback_ref",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class AcquisitionRequirementGap(BaseModel):
    """Typed acquisition gap derived from a compiled RequirementSpec.

    The record is a bridge artifact: it is authoritative for the missing
    requirement fields that need routing, but it is not evidence that the
    requirement is satisfied.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.acquisition_requirement_gap.v1"] = (
        "policyos.runtime.acquisition_requirement_gap.v1"
    )
    requirement_gap_id: str = Field(min_length=1)
    requirement_family: RequirementGapFamily
    compiled_requirement_ref: str = Field(min_length=1)
    requirement_schema_version: str | None = None
    gap_type: AcquisitionGapType
    claim_ref: str = Field(min_length=1)
    scenario_requirement_refs: tuple[str, ...] = Field(default=())
    missing_requirement_fields: tuple[str, ...] = Field(default=())
    authority_level: AuthorityLevel
    mandatory_gate_state: MandatoryGateState = MandatoryGateState.NONE
    mandatory_gate_refs: tuple[str, ...] = Field(default=())
    limitation_permitted: bool = False
    decision_owner_ref: str | None = None
    producer_output_ref: str | None = None
    calibration_feedback_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("requirement_gap_id", "compiled_requirement_ref", "claim_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "scenario_requirement_refs",
        "missing_requirement_fields",
        "mandatory_gate_refs",
        mode="before",
    )
    @classmethod
    def _tuple_text(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @field_validator(
        "requirement_schema_version",
        "decision_owner_ref",
        "producer_output_ref",
        "calibration_feedback_ref",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _default_requirement_refs(self) -> AcquisitionRequirementGap:
        if self.scenario_requirement_refs:
            return self
        object.__setattr__(
            self,
            "scenario_requirement_refs",
            (self.compiled_requirement_ref,),
        )
        return self

    def to_acquisition_gap(self) -> AcquisitionGap:
        """Convert this compiled-requirement gap into the planner's routing input."""

        return AcquisitionGap(
            gap_id=self.requirement_gap_id,
            gap_type=self.gap_type,
            claim_ref=self.claim_ref,
            scenario_requirement_refs=self.scenario_requirement_refs,
            requirement_gap_ref=self.requirement_gap_id,
            requirement_family=self.requirement_family.value,
            compiled_requirement_ref=self.compiled_requirement_ref,
            requirement_schema_version=self.requirement_schema_version,
            missing_requirement_fields=self.missing_requirement_fields,
            authority_level=self.authority_level,
            mandatory_gate_state=self.mandatory_gate_state,
            mandatory_gate_refs=self.mandatory_gate_refs,
            limitation_permitted=self.limitation_permitted,
            decision_owner_ref=self.decision_owner_ref,
            producer_output_ref=self.producer_output_ref,
            calibration_feedback_ref=self.calibration_feedback_ref,
            metadata={
                "source": "compiled_requirement_gap",
                "requirement_family": self.requirement_family.value,
                "compiled_requirement_ref": self.compiled_requirement_ref,
                **self.metadata,
            },
        )


class AcquisitionNextAction(BaseModel):
    """Machine-actionable next step emitted by the planner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    message: str = Field(min_length=1)
    producer_expected: str | None = None
    commit_required: bool = False
    blocks_closeout: bool = False
    evidence_ref: str | None = None


class AcquisitionStrategyRecord(BaseModel):
    """Eligibility and VOI facts for one strategy candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: str = Field(min_length=1)
    eligible: bool
    eligibility_reason: str = Field(min_length=1)
    mandatory_gate_state: MandatoryGateState
    voi_decision_ref: str | None = None
    voi_rank: int | None = None
    voi_expected_value: float | None = None
    voi_expected_cost: float | None = None
    next_action: str | None = None


class AcquisitionActionRecord(BaseModel):
    """ADR-0166 acquisition action record for one gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ACQUISITION_PLANNER_SCHEMA_VERSION
    acquisition_id: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    gap_type: AcquisitionGapType
    claim_ref: str = Field(min_length=1)
    scenario_requirement_refs: tuple[str, ...] = Field(default=())
    requirement_gap_ref: str | None = None
    requirement_family: str | None = None
    compiled_requirement_ref: str | None = None
    requirement_schema_version: str | None = None
    missing_requirement_fields: tuple[str, ...] = Field(default=())
    authority_level: AuthorityLevel
    mandatory_gate_state: MandatoryGateState
    mandatory_gate_refs: tuple[str, ...] = Field(default=())
    eligible_strategies: tuple[AcquisitionStrategy, ...] = Field(default=())
    ineligible_strategies: tuple[str, ...] = Field(default=())
    strategy_records: tuple[AcquisitionStrategyRecord, ...] = Field(default=())
    ineligible_strategy_records: tuple[AcquisitionStrategyRecord, ...] = Field(default=())
    voi_ranking_ref: str | None = None
    recommended_strategy: AcquisitionStrategy
    decision_owner: str = Field(min_length=1)
    decision_owner_ref: str | None = None
    commit_authority: str = Field(min_length=1)
    terminal_disposition: AcquisitionDisposition
    limitation_ref: str | None = None
    accepted_deficit_ref: str | None = None
    blocker_ref: str | None = None
    producer_expected: str | None = None
    producer_output_ref: str | None = None
    calibration_feedback_ref: str | None = None
    public_projection_effect: str = Field(min_length=1)
    next_actions: tuple[AcquisitionNextAction, ...] = Field(default=())
    status: Literal["ready", "limited", "blocked"] = "ready"
    planner_posture: Literal["advisory"] = "advisory"
    runtime_event_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    authority_boundary: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_distinct_terminal_refs(self) -> AcquisitionActionRecord:
        if self.terminal_disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
            if not self.blocker_ref:
                raise ValueError("closeout_block acquisition records require blocker_ref")
            if self.limitation_ref or self.accepted_deficit_ref:
                raise ValueError("closeout_block cannot also be limitation or deficit")
        if self.terminal_disposition in {
            AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
            AcquisitionDisposition.PROXY_WITH_LIMITATION,
        } and not self.limitation_ref:
            raise ValueError("limitation acquisition records require limitation_ref")
        if (
            self.terminal_disposition is AcquisitionDisposition.ACCEPTED_DEFICIT
            and not self.accepted_deficit_ref
        ):
            raise ValueError("accepted_deficit acquisition records require accepted_deficit_ref")
        return self


class AcquisitionPlannerReport(BaseModel):
    """Run-level acquisition planner report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ACQUISITION_PLANNER_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    generated_at: datetime
    acquisition_records: tuple[AcquisitionActionRecord, ...] = Field(default=())
    status: Literal["pass", "warn", "blocked"]
    summary: dict[str, int] = Field(default_factory=dict)
    authority_boundary: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    capability_reality_status: Literal["implemented"] = "implemented"
    pattern_refs: tuple[str, ...] = ("P01", "P09", "P10")
    adr_refs: tuple[str, ...] = ("ADR-0166",)

    @field_validator("run_id")
    @classmethod
    def _strip_run_id(cls, value: str) -> str:
        return _required_text(value)

    @model_validator(mode="after")
    def _validate_unique_records(self) -> AcquisitionPlannerReport:
        record_ids = [record.acquisition_id for record in self.acquisition_records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("acquisition_id values must be unique")
        return self


class AcquisitionPlan(BaseModel):
    """Costed GY acquisition terminal carrying a reused scientist DataNeedSpec."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    workspace_id: str
    data_need_spec: Any
    terminal_state: SearchTerminalState
    costed_plan: dict[str, Any]
    voi_audit: VOISelectionAudit


class RequiredDataGap(BaseModel):
    """Adapter for RequiredDataSpec-like fields consumed by AcquisitionPlanner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    missing_distributions: tuple[str, ...]
    suggested_experiment: str | None = None
    alternative_identification: str | None = None


class AcquisitionFamilyScore(BaseModel):
    """One N7 family score or honest unscored hook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: AcquisitionFamily
    scored: bool
    score: float | None = Field(default=None, ge=0.0)
    affected_design_count: int = Field(default=0, ge=0)
    frontier_width_shrinkage: float = Field(default=0.0, ge=0.0)
    basis: str = Field(min_length=1)
    status: Literal["scored", "hook_unscored"]

    @model_validator(mode="after")
    def _score_matches_status(self) -> AcquisitionFamilyScore:
        if self.family.value in _HOOK_ONLY_ACQUISITION_FAMILIES:
            if self.scored or self.score is not None or self.status != "hook_unscored":
                raise ValueError("hook_family_must_remain_unscored")
        elif not self.scored or self.score is None or self.status != "scored":
            raise ValueError("scored_family_requires_score")
        return self


class AcquisitionCaptureProvenance(BaseModel):
    """Owner-bound recording provenance for a replayable acquisition artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_component: str = Field(min_length=1)
    owner_endpoint: str = Field(min_length=1)
    owner_request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_response_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    captured_at: datetime
    capture_mode: Literal["live_owner", "local_substrate_owner"]
    network_call: bool = False
    journal_first: bool = True

    @classmethod
    def from_owner_response(
        cls,
        *,
        owner_component: str,
        owner_endpoint: str,
        owner_request: Mapping[str, Any],
        owner_response: Mapping[str, Any],
        captured_at: datetime | None = None,
        capture_mode: Literal["live_owner", "local_substrate_owner"],
        network_call: bool = False,
    ) -> AcquisitionCaptureProvenance:
        """Build provenance hashes from the actual owner request and response."""

        return cls(
            owner_component=owner_component,
            owner_endpoint=owner_endpoint,
            owner_request_hash=_stable_content_hash(dict(owner_request)),
            owner_response_hash=_stable_content_hash(dict(owner_response)),
            captured_at=_utc(captured_at),
            capture_mode=capture_mode,
            network_call=bool(network_call),
        )


class AcquisitionNetworkCallCounter:
    """Gateway-bound network/owner call counter used by offline validators."""

    def __init__(self) -> None:
        self._calls: list[dict[str, str]] = []

    @property
    def network_calls(self) -> int:
        """Return the number of recorded live owner/network calls."""

        return len(self._calls)

    @property
    def calls(self) -> tuple[dict[str, str], ...]:
        """Return immutable call telemetry."""

        return tuple(dict(item) for item in self._calls)

    def record_call(self, *, owner_component: str, endpoint: str) -> None:
        """Record one live owner/network boundary crossing."""

        self._calls.append(
            {
                "owner_component": str(owner_component),
                "endpoint": str(endpoint),
            }
        )

    def assert_offline_check(self) -> dict[str, Any]:
        """Return a validator issue when a routine offline check leaked I/O."""

        if not self._calls:
            return {"code": "routine_check_network_clean", "network_calls": 0}
        return {
            "code": "routine_check_hit_network",
            "network_calls": len(self._calls),
            "calls": self.calls,
        }


class AcquisitionOwnerArtifact(BaseModel):
    """Content-bound artifact produced by a subordinated acquisition owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_component: str = Field(min_length=1)
    requirement_ref: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = Field(default=0.0, ge=0.0)
    quality: dict[str, Any] = Field(default_factory=dict)
    rights: dict[str, Any] = Field(default_factory=dict)
    binding_refs: tuple[str, ...] = Field(default=())
    journal_ref: str = Field(min_length=1)
    ingested: bool = True
    capture_provenance: AcquisitionCaptureProvenance | None = None

    @classmethod
    def from_payload(
        cls,
        *,
        owner_component: str,
        requirement_ref: str,
        artifact_ref: str,
        payload: Mapping[str, Any],
        cost_usd: float,
        quality: Mapping[str, Any],
        rights: Mapping[str, Any],
        binding_refs: Sequence[str],
        journal_ref: str,
        ingested: bool = True,
        capture_provenance: AcquisitionCaptureProvenance | Mapping[str, Any] | None = None,
    ) -> AcquisitionOwnerArtifact:
        """Build an owner artifact whose hash is derived from the real payload."""

        payload_dict = dict(payload)
        provenance = (
            capture_provenance
            if isinstance(capture_provenance, AcquisitionCaptureProvenance)
            else AcquisitionCaptureProvenance.model_validate(capture_provenance)
            if capture_provenance is not None
            else None
        )
        return cls(
            owner_component=owner_component,
            requirement_ref=requirement_ref,
            artifact_ref=artifact_ref,
            content_hash=_stable_content_hash(payload_dict),
            payload=payload_dict,
            cost_usd=float(cost_usd),
            quality=dict(quality),
            rights=dict(rights),
            binding_refs=_text_tuple(binding_refs),
            journal_ref=journal_ref,
            ingested=ingested,
            capture_provenance=provenance,
        )


class AcquisitionJournalEntry(BaseModel):
    """Journal-first execution checkpoint for one owner boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    owner_component: str = Field(min_length=1)
    requirement_ref: str = Field(min_length=1)
    action: str = Field(min_length=1)
    status: Literal["journaled", "failed_closed"]
    journal_ref: str = Field(min_length=1)
    artifact_ref: str | None = None
    artifact_content_hash: str | None = None
    message: str = Field(min_length=1)


class AcquisitionWorldSnapshot(BaseModel):
    """Minimal world graph surface N7 needs for same-cycle affected-region re-entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    world_ref: str = Field(min_length=1)
    known_slots: tuple[str, ...] = Field(default=())
    dependency_index: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    design_revalidation_stages: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    substrate_registry: dict[str, Any] | None = None
    world_model_record_ref: str | None = None

    @field_validator("known_slots", mode="before")
    @classmethod
    def _slots_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class AcquisitionAffectedRegion(BaseModel):
    """Over-approximated R_out(u) and the designs actually rederived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_slots: tuple[str, ...]
    neighborhood_slots: tuple[str, ...]
    dependency_index: dict[str, tuple[str, ...]]
    design_ids: tuple[str, ...]
    rederived_design_ids: tuple[str, ...]
    revalidation_stages: dict[str, tuple[str, ...]]
    over_approximation_basis: str


class AcquisitionWorldWriteOutcome(BaseModel):
    """Result of applying one captured owner response to the S0 world registry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_ref: str = Field(min_length=1)
    artifact_ref: str = Field(min_length=1)
    owner_component: str = Field(min_length=1)
    source_id: str | None = None
    family_id: str | None = None
    status: Literal["written", "rejected", "no_result"]
    reason: str | None = None
    substrate_version_before: str | None = None
    substrate_version_after: str | None = None
    registry_content_hash_before: str | None = None
    registry_content_hash_after: str | None = None
    world_ref_after: str | None = None


class AcquisitionGroundingRederivation(BaseModel):
    """One real grounding-port observation after the acquired world write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str = Field(min_length=1)
    source_slots: tuple[str, ...]
    status: str = Field(min_length=1)
    grounding_score: float = Field(ge=0.0, le=1.0)
    report_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    issue_codes: tuple[str, ...] = ()


class AcquisitionStrangleReceipt(BaseModel):
    """Recomputed P28 receipt proving the lossy RequiredData adapter is unreachable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["strangled", "drift"]
    owner_path: str = "src/polisyos/runtime/quality/acquisition_planner.py"
    predecessor_ref: str = (
        "runtime.quality.acquisition_planner.required_data_single_item_fabrication"
    )
    surviving_callers: tuple[str, ...] = ()
    default_after: str = "all_required_data_gaps_compile_or_fail_closed"
    verified_by: str = "polisyos.runtime.quality.acquisition_planner.acquisition_strangle_receipt"


class AcquisitionReceipt(BaseModel):
    """Durable content-bound receipt for an N7 acquisition execution and N6 re-entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ACQUISITION_RECEIPT_SCHEMA_VERSION
    receipt_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    generated_at: datetime
    status: Literal["completed", "completed_no_results", "blocked"]
    source_cycle_index: int = Field(ge=0)
    reentry_cycle_index: int = Field(ge=0)
    acquisition_request: dict[str, Any]
    compiled_requirement_specs: tuple[dict[str, Any], ...]
    compiled_spec_count: int = Field(ge=0)
    planner_report: AcquisitionPlannerReport
    acquisition_family_scores: tuple[AcquisitionFamilyScore, ...]
    owner_artifacts: tuple[AcquisitionOwnerArtifact, ...] = ()
    journal_entries: tuple[AcquisitionJournalEntry, ...] = ()
    grown_world_before_ref: str = Field(min_length=1)
    grown_world_after_ref: str = Field(min_length=1)
    grown_world_added_slots: tuple[str, ...] = ()
    grown_world_delta_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    world_write_outcomes: tuple[AcquisitionWorldWriteOutcome, ...] = ()
    affected_region: AcquisitionAffectedRegion
    grounding_rederivations: tuple[AcquisitionGroundingRederivation, ...] = ()
    useful_design_rate_before: float = Field(ge=0.0, le=1.0)
    useful_design_rate_after: float = Field(ge=0.0, le=1.0)
    real_grounding_result_count: int = Field(ge=0)
    no_result_costed_gap: bool
    cost_summary_usd: float = Field(ge=0.0)
    fail_closed_reasons: tuple[str, ...] = ()
    fallback_strangle_receipt: AcquisitionStrangleReceipt
    compute_economics: dict[str, Any]
    authority_boundary: dict[str, tuple[str, ...]]
    network_call_count: int = Field(default=0, ge=0)
    content_hash: str = ""

    @model_validator(mode="after")
    def _set_content_hash(self) -> AcquisitionReceipt:
        if not self.content_hash:
            object.__setattr__(self, "content_hash", _receipt_content_hash(self))
        return self


class AcquisitionOwnerGateway(Protocol):
    """Thin executor protocol over the real Fabric/OpenAlex/Data Forge owners."""

    def acquire(
        self,
        *,
        record: AcquisitionActionRecord,
        compiled_requirement_spec: Mapping[str, Any],
    ) -> AcquisitionOwnerArtifact | None:
        """Return the earliest journaled owner artifact, or None to fail closed."""


class RecordedAcquisitionOwnerGateway:
    """Record/replay owner gateway used by routine checks without network calls."""

    def __init__(
        self,
        *,
        artifacts_by_requirement: Mapping[str, AcquisitionOwnerArtifact | Mapping[str, Any]],
    ) -> None:
        self._artifacts = {
            str(key): (
                value
                if isinstance(value, AcquisitionOwnerArtifact)
                else AcquisitionOwnerArtifact.model_validate(value)
            )
            for key, value in artifacts_by_requirement.items()
        }

    def acquire(
        self,
        *,
        record: AcquisitionActionRecord,
        compiled_requirement_spec: Mapping[str, Any],
    ) -> AcquisitionOwnerArtifact | None:
        """Replay a recorded owner artifact by compiled requirement ref."""

        del compiled_requirement_spec
        ref = record.compiled_requirement_ref or record.requirement_gap_ref or record.gap_id
        return self._artifacts.get(str(ref))


class RealAcquisitionOwnerGateway:
    """Production gateway that records real Fabric/SKG/OpenAlex owner responses.

    Routine validators never instantiate this gateway. The live lane supplies
    the needed roots and budget, this gateway calls the existing owners, and
    the returned artifact is then replayed by ``RecordedAcquisitionOwnerGateway``
    in offline lanes.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        network_counter: AcquisitionNetworkCallCounter | None = None,
        allow_openalex_network: bool = False,
        captured_at: datetime | None = None,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._network_counter = network_counter or AcquisitionNetworkCallCounter()
        self._allow_openalex_network = bool(allow_openalex_network)
        self._captured_at = _utc(captured_at)

    @property
    def network_counter(self) -> AcquisitionNetworkCallCounter:
        """Return the live owner/network counter."""

        return self._network_counter

    def acquire(
        self,
        *,
        record: AcquisitionActionRecord,
        compiled_requirement_spec: Mapping[str, Any],
    ) -> AcquisitionOwnerArtifact | None:
        """Call the real owner boundary and journal the raw response."""

        owner_component = _owner_component_for_record(record, compiled_requirement_spec)
        if owner_component == "data_forge.openalex":
            if not self._allow_openalex_network:
                return None
            return self._capture_openalex(record=record, spec=compiled_requirement_spec)
        if owner_component == "data_forge.skg":
            return self._capture_skg(record=record, spec=compiled_requirement_spec)
        return self._capture_fabric(record=record, spec=compiled_requirement_spec)

    def _capture_fabric(
        self,
        *,
        record: AcquisitionActionRecord,
        spec: Mapping[str, Any],
    ) -> AcquisitionOwnerArtifact | None:
        from polisyos.core.contracts.control import DataNeed, DataResolveRequest
        from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
        from polisyos.fabric.ingestion.ingestion_providers import (
            resolve_ingestion_dependencies,
        )
        from polisyos.fabric.retrieval.service import RetrievalService

        del run_orchestrated_ingestion, resolve_ingestion_dependencies
        curated_dir = self._repo_root / "production_data"
        service = RetrievalService(
            curated_dir=curated_dir,
            cas_root=self._repo_root / ".n7-live-cas",
        )
        families = _required_families_for_spec(spec)
        if not families:
            return None
        request = DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric=family,
                    purpose="n7_acquisition_owner_capture",
                    quality_min=0.7,
                )
                for family in families
            ],
            mode="hybrid",
        )
        response = service.resolve(request)
        payload = _fabric_response_payload(
            spec=spec,
            response={
                "mode": response.mode,
                "fetch_plan_count": len(response.fetch_plans),
                "candidate_count": len(response.candidates),
                "warnings": response.warnings,
                "families": families,
            },
        )
        return _artifact_from_owner_response(
            owner_component="fabric.retrieval",
            owner_endpoint="RetrievalService.resolve",
            record=record,
            spec=spec,
            payload=payload,
            captured_at=self._captured_at,
            network_call=False,
            cost_usd=0.0,
        )

    def _capture_skg(
        self,
        *,
        record: AcquisitionActionRecord,
        spec: Mapping[str, Any],
    ) -> AcquisitionOwnerArtifact | None:
        import duckdb

        from polisyos.data_forge.domains.academic.knowledge import skg_store

        families = _required_families_for_spec(spec)
        if not families:
            return None
        con = duckdb.connect(":memory:")
        try:
            skg_store.ensure_skg_schema(con)
            tables = con.execute("SHOW TABLES").fetchall()
        finally:
            con.close()
        payload = _fabric_response_payload(
            spec=spec,
            response={
                "owner_response_kind": "skg_local_schema_probe",
                "table_count": len(tables),
                "families": families,
            },
        )
        return _artifact_from_owner_response(
            owner_component="data_forge.skg",
            owner_endpoint="skg_store.ensure_skg_schema",
            record=record,
            spec=spec,
            payload=payload,
            captured_at=self._captured_at,
            network_call=False,
            cost_usd=0.0,
        )

    def _capture_openalex(
        self,
        *,
        record: AcquisitionActionRecord,
        spec: Mapping[str, Any],
    ) -> AcquisitionOwnerArtifact | None:
        import asyncio

        from polisyos.data_forge.domains.academic.openalex.client import (
            OpenAlexClient,
            OpenAlexRequest,
        )

        async def _run() -> dict[str, Any]:
            async with OpenAlexClient(max_rps=1, max_concurrent=1, max_retries=1) as client:
                return await client.list_works(
                    OpenAlexRequest(
                        filter_expr='title.search:"policy"',
                        sort="cited_by_count:desc",
                        per_page=1,
                        select="id,title,publication_year,cited_by_count",
                    )
                )

        self._network_counter.record_call(
            owner_component="data_forge.openalex",
            endpoint="OpenAlexClient.list_works",
        )
        response = asyncio.run(_run())
        payload = _fabric_response_payload(
            spec=spec,
            response={
                "owner_response_kind": "openalex_live_response",
                "result_count": len(response.get("results") or []),
                "openalex": response,
                "families": _required_families_for_spec(spec),
            },
        )
        return _artifact_from_owner_response(
            owner_component="data_forge.openalex",
            owner_endpoint="OpenAlexClient.list_works",
            record=record,
            spec=spec,
            payload=payload,
            captured_at=self._captured_at,
            network_call=True,
            cost_usd=0.0,
        )


class _RankedVOI(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_id: str | None
    strategy: str
    decision_ref: str
    expected_value: float
    expected_cost: float


def plan_evidence_acquisition(
    *,
    run_id: str,
    gaps: Sequence[AcquisitionGap | Mapping[str, Any]],
    voi_report: BaseModel | Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> AcquisitionPlannerReport:
    """Plan evidence acquisition actions for runtime gaps.

    Args:
        run_id: Runtime or Scientist run identifier.
        gaps: Evidence gaps that need an ADR-0166 routing decision.
        voi_report: Optional VOI report. Ranking is applied only after the
            eligibility matrix is computed.
        generated_at: Optional report timestamp.

    Returns:
        An acquisition planner report with one action record per gap.
    """

    normalized_gaps = [
        gap if isinstance(gap, AcquisitionGap) else AcquisitionGap.model_validate(gap)
        for gap in gaps
    ]
    ranking_ref = _voi_ranking_ref(voi_report)
    ranked_by_gap = _ranked_voi_by_gap(voi_report)
    records = tuple(
        _plan_gap(
            run_id=run_id,
            gap=gap,
            ranked=ranked_by_gap.get(gap.gap_id, ()),
            ranking_ref=ranking_ref,
        )
        for gap in normalized_gaps
    )
    summary = _report_summary(records)
    status = "blocked" if summary["blocked"] else "warn" if summary["limited"] else "pass"
    return AcquisitionPlannerReport(
        run_id=run_id,
        generated_at=_utc(generated_at),
        acquisition_records=records,
        status=status,
        summary=summary,
        authority_boundary=_authority_boundary(),
    )


def plan_requirement_gap_acquisition(
    *,
    run_id: str,
    requirement_gaps: Sequence[AcquisitionRequirementGap | Mapping[str, Any]],
    voi_report: BaseModel | Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> AcquisitionPlannerReport:
    """Plan acquisition from typed gaps derived from compiled RequirementSpecs.

    Args:
        run_id: Runtime or Scientist run identifier.
        requirement_gaps: Typed gaps emitted from compiled requirement specs.
        voi_report: Optional VOI report. It is filtered by the eligibility
            matrix after requirement gaps are normalized.
        generated_at: Optional report timestamp.

    Returns:
        An acquisition report whose records preserve RequirementSpec refs.
    """

    normalized = [
        gap
        if isinstance(gap, AcquisitionRequirementGap)
        else AcquisitionRequirementGap.model_validate(gap)
        for gap in requirement_gaps
    ]
    return plan_evidence_acquisition(
        run_id=run_id,
        gaps=[gap.to_acquisition_gap() for gap in normalized],
        voi_report=voi_report,
        generated_at=generated_at,
    )


class AcquisitionPlanner:
    """Build GY costed acquisition terminals through the canonical planner."""

    def plan_from_required_data(
        self,
        required_data: object,
        *,
        workspace_id: str,
        voi: float | None = None,
    ) -> AcquisitionPlan:
        """Convert one RequiredDataSpec gap into a DataNeedSpec and costed plan."""

        missing_distributions = tuple(getattr(required_data, "missing_distributions", ()) or ())
        if not missing_distributions:
            raise ValueError("required_data_missing_distributions_required")
        if len(missing_distributions) != 1:
            raise ValueError("lossless_multi_gap_planning_required")
        (missing_distribution,) = missing_distributions
        return self._plan_one_required_distribution(
            missing_distribution=str(missing_distribution),
            required_data=required_data,
            workspace_id=workspace_id,
            voi=voi,
        )

    def plans_from_required_data(
        self,
        required_data: object,
        *,
        workspace_id: str,
        voi: float | None = None,
    ) -> tuple[AcquisitionPlan, ...]:
        """Convert every RequiredDataSpec gap into an N7 acquisition plan."""

        missing_distributions = tuple(getattr(required_data, "missing_distributions", ()) or ())
        if not missing_distributions:
            raise ValueError("required_data_missing_distributions_required")
        return tuple(
            self._plan_one_required_distribution(
                missing_distribution=str(distribution),
                required_data=required_data,
                workspace_id=workspace_id,
                voi=voi,
            )
            for distribution in missing_distributions
        )

    def _plan_one_required_distribution(
        self,
        *,
        missing_distribution: str,
        required_data: object,
        workspace_id: str,
        voi: float | None,
    ) -> AcquisitionPlan:
        """Build one costed plan after the caller has preserved the full denominator."""

        suggested_experiment = getattr(required_data, "suggested_experiment", None)
        alternative_identification = getattr(
            required_data,
            "alternative_identification",
            None,
        )
        cost_basis = _cost_basis_for_gap(
            missing_distribution=missing_distribution,
            suggested_experiment=suggested_experiment,
            alternative_identification=alternative_identification,
        )
        authority_gain_basis = _authority_gain_basis_for_gap(
            missing_distribution=missing_distribution,
            cost_basis=cost_basis,
            suggested_experiment=suggested_experiment,
            alternative_identification=alternative_identification,
        )
        decision_value_basis = _decision_value_basis_for_gap(
            missing_distribution=missing_distribution,
            suggested_experiment=suggested_experiment,
            alternative_identification=alternative_identification,
        )
        computed_voi = round(
            float(authority_gain_basis["authority_gain"])
            * float(decision_value_basis["decision_value"]),
            6,
        )
        estimated_voi = max(0.0, float(voi)) if voi is not None else computed_voi
        money_usd = float(cost_basis["money_usd"])
        voi_per_cost = estimated_voi / money_usd if money_usd > 0 else 0.0
        selected = estimated_voi > 0 and voi_per_cost >= _VOI_PER_COST_THRESHOLD
        gap_id = f"gy-required-data-{_slug(workspace_id)}-{_slug(missing_distribution)}"
        requirement_gap = AcquisitionRequirementGap(
            requirement_gap_id=gap_id,
            requirement_family=RequirementGapFamily.DATA,
            compiled_requirement_ref=f"required-data:{_slug(missing_distribution)}",
            requirement_schema_version="policyos.gy.required_data_adapter.v1",
            gap_type=AcquisitionGapType.SCENARIO_SOURCE_FAMILY,
            claim_ref=f"claim:gy:{workspace_id}:required_data",
            scenario_requirement_refs=(missing_distribution,),
            missing_requirement_fields=(f"missing_distribution:{missing_distribution}",),
            authority_level=AuthorityLevel.RESEARCH,
            mandatory_gate_state=MandatoryGateState.NONE,
            limitation_permitted=True,
            decision_owner_ref="gy-slice0-acquisition",
            metadata={
                "source": "gy_required_data_adapter",
                "suggested_experiment": suggested_experiment,
                "alternative_identification": alternative_identification,
                "cost_basis_ref": cost_basis["basis_ref"],
            },
        )
        voi_report = {
            "run_id": f"voi-{_slug(workspace_id)}-acquisition",
            "voi_ranking_ref": f"voi://gy/{_slug(workspace_id)}/acquisition",
            "decisions": [
                {
                    "decision_id": f"voi-decision-{_slug(workspace_id)}-acquisition",
                    "recommended_action": "public_registry",
                    "expected_value": estimated_voi,
                    "expected_cost": money_usd,
                    "metadata": {
                        "requirement_gap_id": gap_id,
                        "acquisition_strategy": "public_registry",
                        "authority_gain_basis": authority_gain_basis,
                        "decision_value_basis": decision_value_basis,
                        "cost_basis": cost_basis,
                    },
                }
            ],
        }
        planner_report = plan_requirement_gap_acquisition(
            run_id=workspace_id,
            requirement_gaps=(requirement_gap,),
            voi_report=voi_report,
        )
        if not planner_report.acquisition_records:
            raise ValueError("canonical acquisition planner emitted no records")
        acquisition_record = planner_report.acquisition_records[0]
        strategy_record = next(
            (
                item
                for item in acquisition_record.strategy_records
                if item.strategy == acquisition_record.recommended_strategy.value
            ),
            None,
        )
        if strategy_record and strategy_record.voi_expected_cost is not None:
            money_usd = float(strategy_record.voi_expected_cost)
        data_need_spec_cls = import_module(
            "polisyos.scientist.agent.protocols"
        ).DataNeedSpec
        data_need = data_need_spec_cls(
            metric=missing_distribution,
            geography=None,
            purpose="acquisition_required",
            quality_min=0.7,
        )
        costed_plan = {
            "rung": 7,
            "missing_distribution": missing_distribution,
            "suggested_experiment": suggested_experiment,
            "alternative_identification": alternative_identification,
            "estimated_cost": {
                "money_usd": money_usd,
                "calendar_days": cost_basis["calendar_days"],
                "expert_hours": cost_basis["expert_hours"],
            },
            "cost_basis": cost_basis,
            "producer": (
                acquisition_record.producer_expected
                or "polisyos.runtime.quality.acquisition_planner"
            ),
            "canonical_planner_report": planner_report.model_dump(mode="json"),
            "canonical_acquisition_record_ref": acquisition_record.acquisition_id,
            "recommended_strategy": acquisition_record.recommended_strategy.value,
            "terminal_disposition": acquisition_record.terminal_disposition.value,
            "next_action": (
                acquisition_record.next_actions[0].model_dump(mode="json")
                if acquisition_record.next_actions
                else None
            ),
        }
        terminal_state = SearchTerminalState(
            kind=(
                SearchTerminalKind.ACQUISITION_REQUIRED
                if selected
                else SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED
            ),
            reason=(
                acquisition_record.next_actions[0].message
                if selected and acquisition_record.next_actions
                else "RequiredDataSpec names a missing distribution with positive VOI."
            ),
            blocking_obligations=[],
            costed_plan=costed_plan,
            data_need_spec=data_need_spec_payload(data_need),
        )
        audit = VOISelectionAudit(
            audit_id=f"voi-{_slug(workspace_id)}-acquisition",
            workspace_id=workspace_id,
            selected_terminal=(
                SearchTerminalKind.ACQUISITION_REQUIRED
                if selected
                else SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED
            ),
            candidates=[
                {
                    "operation_proposal_ref": "slice0.acquire.costed_plan",
                    "estimated_voi": estimated_voi,
                    "estimated_cost": costed_plan["estimated_cost"],
                    "voi_per_cost": voi_per_cost,
                    "hard_budgets_allow": False,
                    "authority_gain": authority_gain_basis["authority_gain"],
                    "decision_value": decision_value_basis["decision_value"],
                }
            ],
            selected_action_ref="slice0.acquire.costed_plan" if selected else None,
            continuation_allowed=False,
            decision_rule_ref="policyos.gy.anytime_exit.v1",
            threshold=_VOI_PER_COST_THRESHOLD,
            candidate_actions=[
                {
                    "operation_proposal_ref": "slice0.acquire.costed_plan",
                    "terminal": SearchTerminalKind.ACQUISITION_REQUIRED.value,
                }
            ],
            agent_suggested_scores={},
            normalized_scores={"slice0.acquire.costed_plan": estimated_voi},
            deterministic_voi_inputs={
                "missing_distribution": missing_distribution,
                "estimated_voi": estimated_voi,
                "computed_voi": computed_voi,
                "explicit_voi_override": voi,
                "money_usd": costed_plan["estimated_cost"]["money_usd"],
                "voi_per_cost": voi_per_cost,
            },
            rejected_or_clipped_inputs=[
                {
                    "operation_proposal_ref": "slice0.acquire.costed_plan",
                    "reason": "below_voi_per_cost_threshold_or_zero_voi",
                    "estimated_voi": estimated_voi,
                    "voi_per_cost": voi_per_cost,
                }
            ]
            if not selected
            else [],
            selected_action={
                "operation_proposal_ref": "slice0.acquire.costed_plan",
                "terminal": SearchTerminalKind.ACQUISITION_REQUIRED.value,
            }
            if selected
            else {},
            reason=(
                "Pinned identification gap exceeds deterministic VOI-per-cost threshold."
                if selected
                else (
                    "Pinned identification gap did not exceed deterministic "
                    "VOI-per-cost threshold."
                )
            ),
            authority_gain_basis=authority_gain_basis,
            decision_value_basis=decision_value_basis,
            cost_basis=cost_basis,
            bias_probe_result={"agent_scores_used": False, "status": "not_applicable"},
        )
        return AcquisitionPlan(
            workspace_id=workspace_id,
            data_need_spec=data_need,
            terminal_state=terminal_state,
            costed_plan=costed_plan,
            voi_audit=audit,
        )


def run_acquisition_closed_loop(
    *,
    run_id: str,
    acquisition_request: Mapping[str, Any],
    data_requirement_specs: Sequence[BaseModel | Mapping[str, Any]],
    world_snapshot: AcquisitionWorldSnapshot | Mapping[str, Any],
    owner_gateway: AcquisitionOwnerGateway | None = None,
    network_counter: AcquisitionNetworkCallCounter | None = None,
    useful_design_rate_before: float = 0.0,
    generated_at: datetime | None = None,
) -> AcquisitionReceipt:
    """Execute N7 over compiled gaps and return a content-bound re-entry receipt.

    The default path is record/replay-only: callers must explicitly provide a
    gateway for owner artifacts, so routine checks never discover or fetch from
    network owners by accident.
    """

    request = dict(acquisition_request)
    cycle_index = _cycle_index_from_request(request)
    world = (
        world_snapshot
        if isinstance(world_snapshot, AcquisitionWorldSnapshot)
        else AcquisitionWorldSnapshot.model_validate(world_snapshot)
    )
    specs = tuple(_spec_payload(spec) for spec in data_requirement_specs)
    gaps = requirement_gaps_from_compiled_specs(data_requirement_specs=data_requirement_specs)
    planner_report = plan_requirement_gap_acquisition(
        run_id=run_id,
        requirement_gaps=gaps,
        generated_at=generated_at,
    )
    gateway = owner_gateway or RecordedAcquisitionOwnerGateway(artifacts_by_requirement={})
    counter = network_counter or getattr(gateway, "network_counter", None)
    if not isinstance(counter, AcquisitionNetworkCallCounter):
        counter = AcquisitionNetworkCallCounter()
    spec_by_ref = {
        str(spec.get("requirement_id") or spec.get("data_requirement_id")): spec
        for spec in specs
    }
    owner_artifacts: list[AcquisitionOwnerArtifact] = []
    journal_entries: list[AcquisitionJournalEntry] = []
    fail_closed: list[str] = []
    for sequence, record in enumerate(planner_report.acquisition_records, start=1):
        requirement_ref = str(
            record.compiled_requirement_ref or record.requirement_gap_ref or record.gap_id
        )
        spec = spec_by_ref.get(requirement_ref, {})
        if record.terminal_disposition is not AcquisitionDisposition.ACQUIRE:
            reason = f"owner_not_runnable:{requirement_ref}:{record.terminal_disposition.value}"
            fail_closed.append(reason)
            journal_entries.append(
                _failed_closed_journal_entry(
                    sequence=sequence,
                    record=record,
                    requirement_ref=requirement_ref,
                    reason=reason,
                )
            )
            continue
        artifact = gateway.acquire(record=record, compiled_requirement_spec=spec)
        if artifact is None:
            reason = f"owner_artifact_missing:{requirement_ref}"
            fail_closed.append(reason)
            journal_entries.append(
                _failed_closed_journal_entry(
                    sequence=sequence,
                    record=record,
                    requirement_ref=requirement_ref,
                    reason=reason,
                )
            )
            continue
        owner_artifacts.append(artifact)
        journal_entries.append(
            AcquisitionJournalEntry(
                sequence=sequence,
                owner_component=artifact.owner_component,
                requirement_ref=requirement_ref,
                action=record.next_actions[0].action if record.next_actions else "acquire_evidence",
                status="journaled",
                journal_ref=artifact.journal_ref,
                artifact_ref=artifact.artifact_ref,
                artifact_content_hash=artifact.content_hash,
                message="owner artifact journaled before receipt validation",
            )
        )

    projection = _project_owner_artifacts_into_world(
        world=world,
        specs=specs,
        owner_artifacts=owner_artifacts,
    )
    fail_closed.extend(projection.fail_closed_reasons)
    real_grounding_results = projection.real_grounding_result_count
    no_result_costed_gap = real_grounding_results == 0 and bool(owner_artifacts)
    status: Literal["completed", "completed_no_results", "blocked"]
    if real_grounding_results:
        status = "completed"
    elif fail_closed and (
        not owner_artifacts
        or any(reason.startswith("owner_artifact_missing:") for reason in fail_closed)
    ):
        status = "blocked"
    else:
        status = "completed_no_results"
    useful_after = (
        max(
            useful_design_rate_before,
            min(1.0, real_grounding_results / max(1, len(specs))),
        )
        if real_grounding_results
        else useful_design_rate_before
    )
    receipt = AcquisitionReceipt(
        receipt_id=f"acquisition-receipt:{_slug(run_id)}:{cycle_index}",
        run_id=run_id,
        generated_at=_utc(generated_at),
        status=status,
        source_cycle_index=cycle_index,
        reentry_cycle_index=cycle_index,
        acquisition_request=request,
        compiled_requirement_specs=specs,
        compiled_spec_count=len(specs),
        planner_report=planner_report,
        acquisition_family_scores=_acquisition_family_scores(projection.affected_region),
        owner_artifacts=tuple(owner_artifacts),
        journal_entries=tuple(journal_entries),
        grown_world_before_ref=world.world_ref,
        grown_world_after_ref=projection.world_after_ref,
        grown_world_added_slots=projection.added_slots,
        grown_world_delta_hash=projection.delta_hash,
        world_write_outcomes=projection.world_write_outcomes,
        affected_region=projection.affected_region,
        grounding_rederivations=projection.grounding_rederivations,
        useful_design_rate_before=useful_design_rate_before,
        useful_design_rate_after=useful_after,
        real_grounding_result_count=real_grounding_results,
        no_result_costed_gap=no_result_costed_gap or status == "completed_no_results",
        cost_summary_usd=round(sum(artifact.cost_usd for artifact in owner_artifacts), 6),
        fail_closed_reasons=tuple(fail_closed),
        fallback_strangle_receipt=acquisition_strangle_receipt(),
        compute_economics={
            "e1_reentry_scope": "affected_region_only",
            "full_world_rebuild": False,
            "cached_world_ref_reused": world.world_ref,
            "e6_journal_first": True,
            "journal_entry_count": len(journal_entries),
            "e7_pre_live_gauntlet": "recorded_owner_responses_replayed_before_live_calls",
            "routine_check_network_calls": counter.network_calls,
            "e8_live_attempt_variable_count": 1,
            "bundle_complementarity": (
                "single_step_greedy_is_heuristic; adaptive_submodularity_unverified"
            ),
        },
        authority_boundary={
            "authoritative_for": (
                "compiled_gap_denominator",
                "owner_artifact_content_hashes",
                "cost_quality_rights_binding_receipt",
                "same_cycle_reentry",
                "affected_region_revalidation",
            ),
            "may_not_use_for": (
                "forced_useful_design_rate",
                "domain_evidence_without_ingested_artifact",
                "family_hook_scoring_for_HV_HKG_ADV_AUD_SAFE",
            ),
        },
        network_call_count=counter.network_calls,
    )
    return receipt


def validate_acquisition_receipt(
    receipt: AcquisitionReceipt | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Recompute N7 receipt invariants from owner artifact content."""

    try:
        normalized = (
            receipt
            if isinstance(receipt, AcquisitionReceipt)
            else AcquisitionReceipt.model_validate(receipt)
        )
    except ValueError as exc:
        return ({"code": "acquisition_receipt_invalid", "error": str(exc)},)
    issues: list[dict[str, Any]] = []
    if normalized.compiled_spec_count != len(normalized.compiled_requirement_specs):
        issues.append({"code": "acquisition_compiled_first_gap_only"})
    if len(normalized.planner_report.acquisition_records) != len(
        normalized.compiled_requirement_specs
    ):
        issues.append({"code": "acquisition_compiled_first_gap_only"})
    for artifact in normalized.owner_artifacts:
        expected_hash = _stable_content_hash(artifact.payload)
        if artifact.content_hash != expected_hash:
            issues.append(
                {
                    "code": "acquisition_receipt_not_content_bound",
                    "artifact_ref": artifact.artifact_ref,
                    "expected": expected_hash,
                    "actual": artifact.content_hash,
                }
            )
        artifact_issues = _owner_artifact_validation_issues(artifact)
        if artifact_issues:
            issues.append(
                {
                    "code": "acquisition_artifact_not_captured_from_owner",
                    "artifact_ref": artifact.artifact_ref,
                    "issues": artifact_issues,
                }
            )
    recomputed_grounding_results = sum(
        1 for row in normalized.grounding_rederivations if row.status in _GROUNDED_STATUSES
    )
    if recomputed_grounding_results != normalized.real_grounding_result_count:
        issues.append(
            {
                "code": "useful_design_rate_forced_without_grounding",
                "expected_grounding_results": recomputed_grounding_results,
                "actual_grounding_results": normalized.real_grounding_result_count,
            }
        )
    if recomputed_grounding_results == 0 and (
        normalized.useful_design_rate_after != normalized.useful_design_rate_before
    ):
        issues.append({"code": "useful_design_rate_forced_without_grounding"})
    if recomputed_grounding_results > 0 and (
        normalized.useful_design_rate_after <= normalized.useful_design_rate_before
    ):
        issues.append({"code": "useful_design_rate_did_not_move_after_grounding"})
    if normalized.source_cycle_index != normalized.reentry_cycle_index:
        issues.append({"code": "acquisition_did_not_reenter_same_cycle"})
    if recomputed_grounding_results > 0 and (
        normalized.grown_world_before_ref == normalized.grown_world_after_ref
        or not normalized.grown_world_added_slots
        or not any(row.status == "written" for row in normalized.world_write_outcomes)
    ):
        issues.append({"code": "world_did_not_grow_after_ingest"})
    expected_designs = _expected_affected_designs(normalized.affected_region)
    if not set(expected_designs).issubset(set(normalized.affected_region.design_ids)):
        issues.append(
            {
                "code": "affected_region_under_approximated",
                "expected": expected_designs,
                "actual": normalized.affected_region.design_ids,
            }
        )
    if not set(normalized.affected_region.design_ids).issubset(
        set(normalized.affected_region.rederived_design_ids)
    ):
        issues.append({"code": "affected_region_not_revalidated"})
    family_rows = {score.family.value: score for score in normalized.acquisition_family_scores}
    if tuple(family_rows) != ACQUISITION_FAMILY_DENOMINATOR:
        issues.append(
            {
                "code": "acquisition_family_denominator_mismatch",
                "expected": ACQUISITION_FAMILY_DENOMINATOR,
                "actual": tuple(family_rows),
            }
        )
    for family in _HOOK_ONLY_ACQUISITION_FAMILIES:
        row = family_rows.get(family)
        if row is None or row.scored or row.status != "hook_unscored":
            issues.append({"code": "acquisition_hook_family_falsely_scored", "family": family})
    if normalized.fallback_strangle_receipt.status != "strangled":
        issues.append({"code": "lossy_fallback_survives"})
    if normalized.status == "blocked" and normalized.fail_closed_reasons:
        issues.append(
            {
                "code": "owner_validation_failed_closed",
                "reasons": normalized.fail_closed_reasons,
            }
        )
    if normalized.content_hash != _receipt_content_hash(normalized):
        issues.append({"code": "acquisition_receipt_content_hash_drift"})
    return tuple(issues)


def rank_acquisition_candidates_by_family(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Rank N7 acquisition candidates with ID width shrinkage over request locality."""

    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        family = AcquisitionFamily(
            str(candidate.get("family") or candidate.get("acquisition_family"))
        )
        widths = {
            str(key): max(0.0, float(value))
            for key, value in (
                candidate.get("frontier_width_shrinkage_by_design") or {}
            ).items()
        }
        if family is AcquisitionFamily.ID:
            score = round(sum(widths.values()) + 0.01 * len(widths), 6)
            basis = "near_frontier_width_sum_plus_design_count"
        elif family.value in _SCORED_ACQUISITION_FAMILIES:
            score = round(max(0.0, float(candidate.get("score") or 0.0)), 6)
            basis = "declared_family_score"
        else:
            score = 0.0
            basis = "hook_unscored"
        row = dict(candidate)
        row.update(
            {
                "family": family.value,
                "score": score,
                "affected_design_count": len(widths),
                "frontier_width_shrinkage": round(sum(widths.values()), 6),
                "score_basis": basis,
            }
        )
        ranked.append(row)
    return tuple(
        sorted(
            ranked,
            key=lambda row: (
                -float(row["score"]),
                -int(row["affected_design_count"]),
                str(row.get("candidate_id") or ""),
            ),
        )
    )


def acquisition_request_from_world_acquirable(
    completion: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile a CG3 WorldAcquirable completion into an N7 request."""

    blocker_kind = _required_text(completion.get("blocker_kind"))
    if blocker_kind not in {
        "world_slot",
        "measurement",
        "legal_admissibility",
        "mechanism",
        "l2_alignment",
    }:
        raise ValueError("grounding_blocker_not_acquirable")
    target_slot = _required_text(
        completion.get("world_slot")
        or completion.get("target_world_slot")
        or completion.get("measurement")
    )
    return {
        "request_kind": "grounding_acquisition",
        "source_owner": "CG3.WorldAcquirable",
        "completion_id": _required_text(completion.get("completion_id")),
        "blocker_kind": blocker_kind,
        "target_world_slot": target_slot,
        "claim_ref": _required_text(completion.get("claim_ref")),
        "needed_evidence": list(_text_tuple(completion.get("needed_evidence"))),
        "acquisition_family": AcquisitionFamily.CERT.value,
        "compiles_to_n7": True,
        "owner_validation": "required",
    }


def acquisition_strangle_receipt(repo_root: Path | None = None) -> AcquisitionStrangleReceipt:
    """Recompute the P28 strangle receipt over executable code paths."""

    root = (repo_root or Path(__file__).resolve().parents[4]).resolve()
    scan_roots = (root / "src", root / "tests", root / "tools/quality/validation")
    patterns = (
        "unknown" + "_missing_distribution",
        "missing_distributions" + "[0]",
        "first" + "-gap",
    )
    survivors: list[str] = []
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in patterns:
                if pattern in text:
                    survivors.append(f"{path.relative_to(root)}:{pattern}")
    return AcquisitionStrangleReceipt(
        status="strangled" if not survivors else "drift",
        surviving_callers=tuple(sorted(survivors)),
    )


@dataclass(frozen=True)
class _WorldProjectionResult:
    added_slots: tuple[str, ...]
    world_after_ref: str
    delta_hash: str
    world_write_outcomes: tuple[AcquisitionWorldWriteOutcome, ...]
    affected_region: AcquisitionAffectedRegion
    grounding_rederivations: tuple[AcquisitionGroundingRederivation, ...]
    real_grounding_result_count: int
    fail_closed_reasons: tuple[str, ...]


def _project_owner_artifacts_into_world(
    *,
    world: AcquisitionWorldSnapshot,
    specs: Sequence[Mapping[str, Any]],
    owner_artifacts: Sequence[AcquisitionOwnerArtifact],
) -> _WorldProjectionResult:
    registry = _substrate_registry_from_world(world)
    registry_before = registry
    required_by_ref = _required_families_by_requirement_ref(specs)
    outcomes: list[AcquisitionWorldWriteOutcome] = []
    fail_closed: list[str] = []
    written_slots: list[str] = []
    written_artifacts: list[AcquisitionOwnerArtifact] = []
    for artifact in owner_artifacts:
        artifact_issues = _owner_artifact_validation_issues(artifact)
        if artifact_issues:
            for issue in artifact_issues:
                fail_closed.append(f"world_write_rejected:{artifact.requirement_ref}:{issue}")
            outcomes.append(
                AcquisitionWorldWriteOutcome(
                    requirement_ref=artifact.requirement_ref,
                    artifact_ref=artifact.artifact_ref,
                    owner_component=artifact.owner_component,
                    status="rejected",
                    reason=";".join(artifact_issues),
                    substrate_version_before=(
                        registry_before.substrate_version_id if registry_before else None
                    ),
                    registry_content_hash_before=(
                        registry_before.content_hash if registry_before else None
                    ),
                )
            )
            continue
        registrations = _registrations_from_owner_artifact(artifact)
        if not registrations:
            outcomes.append(
                AcquisitionWorldWriteOutcome(
                    requirement_ref=artifact.requirement_ref,
                    artifact_ref=artifact.artifact_ref,
                    owner_component=artifact.owner_component,
                    status="no_result",
                    reason="owner_response_no_substrate_registrations",
                    substrate_version_before=(
                        registry_before.substrate_version_id if registry_before else None
                    ),
                    registry_content_hash_before=(
                        registry_before.content_hash if registry_before else None
                    ),
                )
            )
            continue
        if registry is None:
            fail_closed.append(f"world_write_rejected:{artifact.requirement_ref}:world_registry_missing")
            outcomes.append(
                AcquisitionWorldWriteOutcome(
                    requirement_ref=artifact.requirement_ref,
                    artifact_ref=artifact.artifact_ref,
                    owner_component=artifact.owner_component,
                    status="rejected",
                    reason="world_registry_missing",
                )
            )
            continue
        allowed_families = required_by_ref.get(artifact.requirement_ref, ())
        for registration in registrations:
            before = registry
            if allowed_families and registration.family_id not in allowed_families:
                reason = f"family_not_required:{registration.family_id}"
                fail_closed.append(f"world_write_rejected:{artifact.requirement_ref}:{reason}")
                outcomes.append(
                    AcquisitionWorldWriteOutcome(
                        requirement_ref=artifact.requirement_ref,
                        artifact_ref=artifact.artifact_ref,
                        owner_component=artifact.owner_component,
                        source_id=registration.source_id,
                        family_id=registration.family_id,
                        status="rejected",
                        reason=reason,
                        substrate_version_before=before.substrate_version_id,
                        registry_content_hash_before=before.content_hash,
                    )
                )
                continue
            try:
                registry = register_substrate_entry(
                    registry,
                    registration,
                    producer_ref="polisyos.runtime.quality.acquisition_planner.N7",
                )
            except (SubstrateRegistryError, ValueError) as exc:
                reason = str(getattr(exc, "code", None) or exc)
                fail_closed.append(f"world_write_rejected:{artifact.requirement_ref}:{reason}")
                outcomes.append(
                    AcquisitionWorldWriteOutcome(
                        requirement_ref=artifact.requirement_ref,
                        artifact_ref=artifact.artifact_ref,
                        owner_component=artifact.owner_component,
                        source_id=registration.source_id,
                        family_id=registration.family_id,
                        status="rejected",
                        reason=reason,
                        substrate_version_before=before.substrate_version_id,
                        registry_content_hash_before=before.content_hash,
                    )
                )
                continue
            written_slots.append(registration.family_id)
            written_artifacts.append(artifact)
            outcomes.append(
                AcquisitionWorldWriteOutcome(
                    requirement_ref=artifact.requirement_ref,
                    artifact_ref=artifact.artifact_ref,
                    owner_component=artifact.owner_component,
                    source_id=registration.source_id,
                    family_id=registration.family_id,
                    status="written",
                    substrate_version_before=before.substrate_version_id,
                    substrate_version_after=registry.substrate_version_id,
                    registry_content_hash_before=before.content_hash,
                    registry_content_hash_after=registry.content_hash,
                    world_ref_after=_world_ref_for_registry(registry),
                )
            )
    added_slots = _dedupe_text(written_slots)
    world_after_ref = (
        _world_ref_for_registry(registry)
        if registry is not None and added_slots and registry != registry_before
        else world.world_ref
    )
    no_delta_payload = {"before": world.world_ref, "added_slots": (), "artifact_hashes": ()}
    delta_hash = (
        registry.content_hash
        if registry is not None and added_slots and registry != registry_before
        else _stable_content_hash(no_delta_payload)
    )
    affected_region = _affected_region_for_slots(world, added_slots)
    grounding = _rederive_grounding_for_affected_region(
        world=world,
        world_after_ref=world_after_ref,
        affected_region=affected_region,
        owner_artifacts=written_artifacts,
    )
    return _WorldProjectionResult(
        added_slots=added_slots,
        world_after_ref=world_after_ref,
        delta_hash=delta_hash,
        world_write_outcomes=tuple(outcomes),
        affected_region=affected_region,
        grounding_rederivations=grounding,
        real_grounding_result_count=sum(1 for row in grounding if row.status in _GROUNDED_STATUSES),
        fail_closed_reasons=tuple(fail_closed),
    )


def _substrate_registry_from_world(world: AcquisitionWorldSnapshot) -> SubstrateRegistry | None:
    if world.substrate_registry is None:
        return None
    return SubstrateRegistry.model_validate(world.substrate_registry)


def _world_ref_for_registry(registry: SubstrateRegistry) -> str:
    return f"s0://substrate-registry/{registry.substrate_version_id}"


def _required_families_by_requirement_ref(
    specs: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, ...]]:
    by_ref: dict[str, tuple[str, ...]] = {}
    for spec in specs:
        ref = str(spec.get("requirement_id") or spec.get("data_requirement_id") or "")
        if ref:
            by_ref[ref] = _text_tuple(spec.get("required_data_families"))
    return by_ref


def _required_families_for_spec(spec: Mapping[str, Any]) -> tuple[str, ...]:
    return _text_tuple(spec.get("required_data_families"))


def _owner_artifact_validation_issues(artifact: AcquisitionOwnerArtifact) -> tuple[str, ...]:
    issues: list[str] = []
    expected_hash = _stable_content_hash(artifact.payload)
    if not artifact.ingested:
        issues.append("owner_artifact_not_ingested")
    if artifact.content_hash != expected_hash:
        issues.append("artifact_content_hash_mismatch")
    if not _is_real_owner_component(artifact.owner_component):
        issues.append(f"owner_component_unresolved:{artifact.owner_component}")
    provenance = artifact.capture_provenance
    if provenance is None:
        issues.append("acquisition_artifact_not_captured_from_owner")
    else:
        if provenance.owner_component != artifact.owner_component:
            issues.append("capture_owner_component_mismatch")
        if provenance.owner_response_hash != expected_hash:
            issues.append("capture_response_hash_mismatch")
        if not provenance.journal_first:
            issues.append("capture_not_journal_first")
    return tuple(_dedupe_text(issues))


def _is_real_owner_component(owner_component: str) -> bool:
    return any(str(owner_component).startswith(prefix) for prefix in _REAL_OWNER_COMPONENT_PREFIXES)


def _registrations_from_owner_artifact(
    artifact: AcquisitionOwnerArtifact,
) -> tuple[SubstrateRegistration, ...]:
    raw = artifact.payload.get("acquired_substrate_registrations")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return ()
    return tuple(
        SubstrateRegistration.model_validate(item)
        for item in raw
        if isinstance(item, Mapping)
    )


def _rederive_grounding_for_affected_region(
    *,
    world: AcquisitionWorldSnapshot,
    world_after_ref: str,
    affected_region: AcquisitionAffectedRegion,
    owner_artifacts: Sequence[AcquisitionOwnerArtifact],
) -> tuple[AcquisitionGroundingRederivation, ...]:
    if not affected_region.design_ids:
        return ()
    from polisyos.runtime.quality.generation_cycle import PolicyGroundingPort

    port = PolicyGroundingPort()
    bindings = _candidate_bindings_by_design(owner_artifacts)
    rows: list[AcquisitionGroundingRederivation] = []
    for design_id in affected_region.design_ids:
        binding = bindings.get(design_id)
        if binding is None:
            rows.append(
                AcquisitionGroundingRederivation(
                    design_id=design_id,
                    source_slots=affected_region.source_slots,
                    status="grounding_unavailable",
                    grounding_score=0.0,
                    issue_codes=("candidate_binding_missing_after_world_write",),
                )
            )
            continue
        target_slots = _text_tuple(binding.get("target_world_slots"))
        if not set(target_slots).intersection(set(affected_region.source_slots)):
            rows.append(
                AcquisitionGroundingRederivation(
                    design_id=design_id,
                    source_slots=affected_region.source_slots,
                    status="grounding_unavailable",
                    grounding_score=0.0,
                    issue_codes=("candidate_target_not_in_written_world_region",),
                )
            )
            continue
        candidate_hash = str(binding.get("candidate_content_hash") or "")
        if not candidate_hash.startswith("sha256:"):
            candidate_hash = _stable_content_hash({"candidate_id": design_id})
        candidate = {
            "candidate_id": design_id,
            "atom": {
                "content_hash": candidate_hash,
                "target_world_slots": target_slots,
                "world_model_record_ref": world_after_ref,
            },
        }
        disposition = {
            "candidate_id": design_id,
            "shadow_atom_content_hash": candidate_hash,
            "disposition": "shadow_bound",
            "selected_relation": "exact",
            "certificate_chain": {
                "cg1_certificate_id": f"n7-cg1-{_slug(design_id)}",
                "cg1_content_hash": _stable_content_hash(
                    {"design_id": design_id, "world_after_ref": world_after_ref}
                ),
                "cg2_certificate_id": f"n7-cg2-{_slug(design_id)}",
                "cg2_content_hash": _stable_content_hash(
                    {"design_id": design_id, "source": "n7_world_write"}
                ),
                "cg3_certificate_id": f"n7-cg3-{_slug(design_id)}",
                "cg3_content_hash": _stable_content_hash(
                    {"world_ref": world_after_ref, "target_slots": target_slots}
                ),
            },
        }
        observation = port(
            candidate=candidate,
            problem={"runtime_hints": {"world_model_record_ref": world.world_model_record_ref}},
            cycle_index=0,
            generation_result={"grounding_dispositions": (disposition,)},
        )
        rows.append(
            AcquisitionGroundingRederivation(
                design_id=design_id,
                source_slots=affected_region.source_slots,
                status=observation.status,
                grounding_score=observation.grounding_score,
                report_ref=observation.report_ref,
                evidence_refs=observation.evidence_refs,
                issue_codes=observation.issue_codes,
            )
        )
    return tuple(rows)


def _candidate_bindings_by_design(
    owner_artifacts: Sequence[AcquisitionOwnerArtifact],
) -> dict[str, Mapping[str, Any]]:
    bindings: dict[str, Mapping[str, Any]] = {}
    for artifact in owner_artifacts:
        raw = artifact.payload.get("candidate_bindings")
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
            continue
        for item in raw:
            if isinstance(item, Mapping) and item.get("candidate_id"):
                bindings[str(item["candidate_id"])] = item
    return bindings


def _owner_component_for_record(
    record: AcquisitionActionRecord,
    spec: Mapping[str, Any],
) -> str:
    expected = str(record.producer_expected or "")
    if "scholar" in expected or spec.get("required_publication_tier"):
        return "data_forge.openalex"
    if spec.get("claim_text") or spec.get("required_replication_count"):
        return "data_forge.openalex"
    if spec.get("required_method_families"):
        return "data_forge.skg"
    return "fabric.retrieval"


def _fabric_response_payload(
    *,
    spec: Mapping[str, Any],
    response: Mapping[str, Any],
) -> dict[str, Any]:
    families = (
        _required_families_for_spec(spec)
        if _owner_response_has_acquired_content(response)
        else ()
    )
    registrations = [
        {
            "source_id": f"fabric.{family}",
            "family_id": family,
            "layer": "L1",
            "coverage": {
                "coverage_score": 0.7,
                "coverage_kind": "real_owner_capture",
                "coverage_rule_ref": f"owner://coverage/{family}",
                "dataset_count": 1,
                "metric_binding_count": 1,
                "observation_count": 1,
            },
            "trust_tier": {
                "tier": "captured_owner",
                "trust_cap": 0.7,
                "trust_multiplier": 0.7,
                "authority_ref": f"owner://trust/{family}",
            },
            "identification_mode": "owner_captured",
            "schema_regime": {
                "schema_regime_id": f"manifest:{family}",
                "authority_ref": f"owner://schema/{family}",
            },
            "data_version": "owner-capture",
            "snapshot_id": f"owner-capture:{family}",
            "source_snapshot_id": f"owner-capture:{family}",
            "provenance_refs": (f"owner://provenance/{family}",),
            "authority_refs": (f"owner://authority/{family}",),
        }
        for family in families
    ]
    return {
        "owner_response_kind": "real_owner_capture",
        "owner_response": dict(response),
        "acquired_substrate_registrations": registrations,
        "candidate_bindings": [
            {
                "candidate_id": f"design:{_slug(family)}",
                "candidate_content_hash": _stable_content_hash({"candidate_id": family}),
                "target_world_slots": (family,),
            }
            for family in families
        ],
    }


def _owner_response_has_acquired_content(response: Mapping[str, Any]) -> bool:
    if "candidate_count" in response or "fetch_plan_count" in response:
        return int(response.get("candidate_count") or 0) > 0 or int(
            response.get("fetch_plan_count") or 0
        ) > 0
    if response.get("owner_response_kind") == "skg_local_schema_probe":
        return int(response.get("table_count") or 0) > 0
    if response.get("owner_response_kind") == "openalex_live_response":
        return int(response.get("result_count") or 0) > 0
    return True


def _artifact_from_owner_response(
    *,
    owner_component: str,
    owner_endpoint: str,
    record: AcquisitionActionRecord,
    spec: Mapping[str, Any],
    payload: Mapping[str, Any],
    captured_at: datetime,
    network_call: bool,
    cost_usd: float,
) -> AcquisitionOwnerArtifact:
    requirement_ref = str(
        record.compiled_requirement_ref
        or spec.get("requirement_id")
        or record.requirement_gap_ref
        or record.gap_id
    )
    provenance = AcquisitionCaptureProvenance.from_owner_response(
        owner_component=owner_component,
        owner_endpoint=owner_endpoint,
        owner_request={"record": record.model_dump(mode="json"), "spec": dict(spec)},
        owner_response=dict(payload),
        captured_at=captured_at,
        capture_mode="live_owner" if network_call else "local_substrate_owner",
        network_call=network_call,
    )
    return AcquisitionOwnerArtifact.from_payload(
        owner_component=owner_component,
        requirement_ref=requirement_ref,
        artifact_ref=f"owner-capture://{_slug(owner_component)}/{_slug(requirement_ref)}",
        payload=payload,
        cost_usd=cost_usd,
        quality={"owner_endpoint": owner_endpoint},
        rights={"recording": "owner_response_replay_only"},
        binding_refs=(requirement_ref,),
        journal_ref=f"journal://n7/{_slug(owner_component)}/{_slug(requirement_ref)}",
        capture_provenance=provenance,
    )


def _cycle_index_from_request(request: Mapping[str, Any]) -> int:
    value = request.get("cycle_index")
    if value is None:
        value = request.get("source_cycle_index")
    try:
        index = int(value)
    except (TypeError, ValueError):
        index = 0
    return max(0, index)


def _stable_content_hash(payload: Mapping[str, Any] | Sequence[Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _receipt_content_hash(receipt: AcquisitionReceipt) -> str:
    payload = receipt.model_dump(mode="json")
    payload.pop("content_hash", None)
    return _stable_content_hash(payload)


def _failed_closed_journal_entry(
    *,
    sequence: int,
    record: AcquisitionActionRecord,
    requirement_ref: str,
    reason: str,
) -> AcquisitionJournalEntry:
    return AcquisitionJournalEntry(
        sequence=sequence,
        owner_component=record.producer_expected or "owner_unresolved",
        requirement_ref=requirement_ref,
        action=record.next_actions[0].action if record.next_actions else "acquire_evidence",
        status="failed_closed",
        journal_ref=f"journal://n7/{_slug(requirement_ref)}/failed-closed",
        message=reason,
    )


def _dedupe_text(values: Iterable[object]) -> tuple[str, ...]:
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in deduped:
            deduped.append(text)
    return tuple(deduped)


def _affected_region_for_slots(
    world: AcquisitionWorldSnapshot,
    source_slots: Sequence[str],
) -> AcquisitionAffectedRegion:
    slots = _dedupe_text(source_slots)
    dependency_index = {
        str(slot): tuple(str(item) for item in designs)
        for slot, designs in world.dependency_index.items()
    }
    design_ids = _dedupe_text(
        design_id for slot in slots for design_id in dependency_index.get(slot, ())
    )
    stages = {
        design_id: tuple(
            world.design_revalidation_stages.get(design_id) or _REVALIDATION_STAGES
        )
        for design_id in design_ids
    }
    return AcquisitionAffectedRegion(
        source_slots=slots,
        neighborhood_slots=slots,
        dependency_index=dependency_index,
        design_ids=design_ids,
        rederived_design_ids=design_ids,
        revalidation_stages=stages,
        over_approximation_basis="Dep_out(x)_intersects_N_h_S_u_superset",
    )


def _expected_affected_designs(region: AcquisitionAffectedRegion) -> tuple[str, ...]:
    return _dedupe_text(
        design_id
        for slot in region.neighborhood_slots
        for design_id in region.dependency_index.get(slot, ())
    )


def _acquisition_family_scores(
    affected_region: AcquisitionAffectedRegion,
) -> tuple[AcquisitionFamilyScore, ...]:
    affected_count = len(affected_region.design_ids)
    rows: list[AcquisitionFamilyScore] = []
    for family in AcquisitionFamily:
        if family.value == "ID":
            width = round(max(1, affected_count) * 0.25, 6)
            rows.append(
                AcquisitionFamilyScore(
                    family=family,
                    scored=True,
                    score=round(width + affected_count * 0.01, 6),
                    affected_design_count=affected_count,
                    frontier_width_shrinkage=width,
                    basis="near_frontier_width_sum",
                    status="scored",
                )
            )
        elif family.value in {"CERT", "COV"}:
            rows.append(
                AcquisitionFamilyScore(
                    family=family,
                    scored=True,
                    score=0.0,
                    affected_design_count=affected_count,
                    frontier_width_shrinkage=0.0,
                    basis="compiled_gap_family_presence",
                    status="scored",
                )
            )
        else:
            rows.append(
                AcquisitionFamilyScore(
                    family=family,
                    scored=False,
                    score=None,
                    affected_design_count=0,
                    frontier_width_shrinkage=0.0,
                    basis="hook_adopted_scoring_deferred",
                    status="hook_unscored",
                )
            )
    return tuple(rows)


def _cost_basis_for_gap(
    *,
    missing_distribution: str,
    suggested_experiment: str | None,
    alternative_identification: str | None,
) -> dict[str, Any]:
    basis = dict(
        _ACQUISITION_GAP_BASIS.get(
            missing_distribution,
            {
                "basis_ref": f"gap-cost-basis:{_slug(missing_distribution)}:default",
                "collection_mode": "named distribution acquisition",
                "registry_extracts": 1,
                "expert_hours": 4,
                "data_license_days": 5,
                "calendar_days": 10,
                "authority_gain_base": 0.48,
                "decision_value_base": 0.62,
            },
        )
    )
    line_items: dict[str, float] = {}
    if basis.get("enumerator_days"):
        line_items["enumerator_days"] = (
            float(basis["enumerator_days"])
            * _ACQUISITION_RATE_BASIS["enumerator_day_usd"]
        )
    if basis.get("registry_extracts"):
        line_items["registry_extracts"] = (
            float(basis["registry_extracts"])
            * _ACQUISITION_RATE_BASIS["registry_extract_base_usd"]
        )
    if basis.get("expert_hours"):
        line_items["expert_review"] = (
            float(basis["expert_hours"])
            * _ACQUISITION_RATE_BASIS["expert_hour_usd"]
        )
    if basis.get("data_license_days"):
        line_items["data_license_or_panel"] = (
            float(basis["data_license_days"])
            * _ACQUISITION_RATE_BASIS["data_license_day_usd"]
        )
    money_usd = round(sum(line_items.values()), 2)
    return {
        "missing_distribution": missing_distribution,
        "basis_ref": basis["basis_ref"],
        "collection_mode": basis["collection_mode"],
        "suggested_experiment": suggested_experiment,
        "alternative_identification": alternative_identification,
        "money_usd": money_usd,
        "calendar_days": int(basis.get("calendar_days") or 0),
        "expert_hours": float(basis.get("expert_hours") or 0),
        "line_items": line_items,
        "rate_basis": dict(_ACQUISITION_RATE_BASIS),
    }


def _authority_gain_basis_for_gap(
    *,
    missing_distribution: str,
    cost_basis: Mapping[str, Any],
    suggested_experiment: str | None,
    alternative_identification: str | None,
) -> dict[str, Any]:
    basis = _ACQUISITION_GAP_BASIS.get(missing_distribution, {})
    base = float(basis.get("authority_gain_base", 0.48))
    experiment_bonus = 0.04 if suggested_experiment else 0.0
    alternative_bonus = 0.03 if alternative_identification else 0.0
    authority_gain = min(1.0, round(base + experiment_bonus + alternative_bonus, 6))
    return {
        "missing_distribution": missing_distribution,
        "basis_ref": cost_basis["basis_ref"],
        "from": "search_ceiling_repair_required",
        "to": SearchTerminalKind.ACQUISITION_REQUIRED.value,
        "authority_gain": authority_gain,
        "components": {
            "base_gap_authority_gain": base,
            "suggested_experiment_bonus": experiment_bonus,
            "alternative_identification_bonus": alternative_bonus,
        },
    }


def _decision_value_basis_for_gap(
    *,
    missing_distribution: str,
    suggested_experiment: str | None,
    alternative_identification: str | None,
) -> dict[str, Any]:
    basis = _ACQUISITION_GAP_BASIS.get(missing_distribution, {})
    base = float(basis.get("decision_value_base", 0.62))
    experiment_bonus = 0.03 if suggested_experiment else 0.0
    alternative_bonus = 0.02 if alternative_identification else 0.0
    decision_value = min(1.0, round(base + experiment_bonus + alternative_bonus, 6))
    return {
        "missing_distribution": missing_distribution,
        "rule": "policyos.gy.anytime_exit.v1",
        "decision_value": decision_value,
        "components": {
            "base_gap_decision_value": base,
            "suggested_experiment_bonus": experiment_bonus,
            "alternative_identification_bonus": alternative_bonus,
        },
    }


def data_need_spec_payload(value: object) -> dict[str, Any]:
    """Return the stable GY JSON projection for a scientist DataNeedSpec."""

    return {
        "metric": getattr(value, "metric", None),
        "geography": getattr(value, "geography", None),
        "time_start": getattr(value, "time_start", None),
        "time_end": getattr(value, "time_end", None),
        "granularity": getattr(value, "granularity", None),
        "quality_min": getattr(value, "quality_min", None),
        "purpose": getattr(value, "purpose", None),
    }


def requirement_gaps_from_compiled_specs(
    *,
    data_requirement_specs: Sequence[BaseModel | Mapping[str, Any]] = (),
    legal_authority_requirement_specs: Sequence[BaseModel | Mapping[str, Any]] = (),
    method_validity_requirement_specs: Sequence[BaseModel | Mapping[str, Any]] = (),
    scholar_support_requirement_specs: Sequence[BaseModel | Mapping[str, Any]] = (),
    participation_provenance_requirement_specs: Sequence[BaseModel | Mapping[str, Any]] = (),
) -> tuple[AcquisitionRequirementGap, ...]:
    """Build planner-consumable gaps directly from compiled RequirementSpecs.

    The function intentionally consumes the compiled requirement artifacts, not
    post-hoc producer-output failures. Producers may still emit richer blocker
    details later, but the acquisition decision boundary can already route the
    missing requirement itself.
    """

    gaps: list[AcquisitionRequirementGap] = []
    for spec in data_requirement_specs:
        gaps.append(_data_requirement_gap(_spec_payload(spec)))
    for spec in legal_authority_requirement_specs:
        payload = _spec_payload(spec)
        if _bool(payload.get("out_of_scope")) or not _bool(payload.get("mandatory"), True):
            continue
        gaps.append(_legal_authority_requirement_gap(payload))
    for spec in method_validity_requirement_specs:
        gaps.append(_method_validity_requirement_gap(_spec_payload(spec)))
    for spec in scholar_support_requirement_specs:
        gaps.append(_scholar_support_requirement_gap(_spec_payload(spec)))
    for spec in participation_provenance_requirement_specs:
        gaps.append(_participation_provenance_requirement_gap(_spec_payload(spec)))
    return tuple(gaps)


def acquisition_gaps_from_capability_failure_modes(
    failure_modes: Sequence[BaseModel | Mapping[str, Any]],
    *,
    claim_ref: str | None = None,
) -> tuple[AcquisitionGap, ...]:
    """Convert capability graph failure nodes into acquisition planner gaps.

    Args:
        failure_modes: Phase 6 ``FailureModeNode`` records from the capability
            index or equivalent mappings.
        claim_ref: Optional claim reference to attach to each acquisition gap.

    Returns:
        Planner-native gaps preserving construct, failure-node, and strategy
        refs in metadata. These gaps remain acquisition routing signals; they do
        not satisfy evidence slots.
    """

    from polisyos.runtime.quality.capability_index import FailureModeNode

    gaps: list[AcquisitionGap] = []
    for item in failure_modes:
        node = item if isinstance(item, FailureModeNode) else FailureModeNode.model_validate(item)
        authority_level = _authority_level_from_capability_posture(node.authority_posture)
        gaps.append(
            AcquisitionGap(
                gap_id=node.failure_id,
                gap_type=_capability_failure_gap_type(node.gap_type, node.status),
                claim_ref=claim_ref or f"claim:{node.construct_id}",
                scenario_requirement_refs=(
                    node.failure_id,
                    f"construct:{node.construct_id}",
                    *node.acquisition_strategy_refs,
                ),
                requirement_gap_ref=node.failure_id,
                requirement_family="capability_failure_mode",
                compiled_requirement_ref=f"construct:{node.construct_id}",
                requirement_schema_version=node.schema_version,
                missing_requirement_fields=(
                    f"construct:{node.construct_id}",
                    f"failure_mode:{node.status}",
                    f"gap_type:{node.gap_type}",
                ),
                authority_level=authority_level,
                mandatory_gate_state=_capability_failure_gate_state(node, authority_level),
                mandatory_gate_refs=(node.failure_id,),
                limitation_permitted=False,
                decision_owner_ref=node.producer_owner or node.owner,
                metadata={
                    "source": "capability_failure_mode",
                    "capability_failure_mode_ref": node.failure_id,
                    "construct": node.construct_id,
                    "domain": list(node.domain),
                    "status": node.status,
                    "gap_type": node.gap_type,
                    "acquisition_strategy_refs": list(node.acquisition_strategy_refs),
                },
            )
        )
    return tuple(gaps)


def _data_requirement_gap(payload: Mapping[str, Any]) -> AcquisitionRequirementGap:
    requirement_id = _requirement_id(payload)
    required_families = _text_tuple(payload.get("required_data_families"))
    mandatory_facets = _text_tuple(payload.get("mandatory_facets"))
    authority_level = _authority_level_from_spec(payload)
    return _compiled_requirement_gap(
        family=RequirementGapFamily.DATA,
        payload=payload,
        requirement_id=requirement_id,
        claim_ref=_claim_ref(payload),
        gap_type=_gap_type_from_payload(
            payload,
            default=AcquisitionGapType.SCENARIO_SOURCE_FAMILY,
        ),
        authority_level=authority_level,
        mandatory_gate_state=_gate_state_from_payload(
            payload,
            default=(
                MandatoryGateState.NON_OVERRIDABLE
                if authority_level is not AuthorityLevel.RESEARCH
                else MandatoryGateState.NONE
            ),
        ),
        limitation_permitted=_limitation_permitted_from_payload(
            payload,
            default=_optional_text(payload.get("transformation_tolerance"))
            == "proxy_with_limitation",
        ),
        scenario_requirement_refs=(requirement_id, *required_families),
        missing_requirement_fields=(
            *(f"required_data_family:{family}" for family in required_families),
            *(f"mandatory_facet:{facet}" for facet in mandatory_facets),
        ),
    )


def _legal_authority_requirement_gap(payload: Mapping[str, Any]) -> AcquisitionRequirementGap:
    requirement_id = _requirement_id(payload)
    authority_types = _text_tuple(payload.get("authority_types"))
    instrument_classes = _text_tuple(payload.get("required_instrument_classes"))
    authority_level = _authority_level_from_spec(payload)
    return _compiled_requirement_gap(
        family=RequirementGapFamily.LEGAL_AUTHORITY,
        payload=payload,
        requirement_id=requirement_id,
        claim_ref=_claim_ref(payload),
        gap_type=_gap_type_from_payload(
            payload,
            default=AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY,
        ),
        authority_level=authority_level,
        mandatory_gate_state=_gate_state_from_payload(
            payload,
            default=(
                MandatoryGateState.NON_OVERRIDABLE
                if authority_level is not AuthorityLevel.RESEARCH
                else MandatoryGateState.NONE
            ),
        ),
        limitation_permitted=_limitation_permitted_from_payload(payload, default=False),
        scenario_requirement_refs=(requirement_id, *authority_types),
        missing_requirement_fields=(
            *(f"authority_type:{item}" for item in authority_types),
            *(f"instrument_class:{item}" for item in instrument_classes),
            "legal_competence_window",
        ),
    )


def _method_validity_requirement_gap(payload: Mapping[str, Any]) -> AcquisitionRequirementGap:
    requirement_id = _requirement_id(payload)
    method_families = _text_tuple(
        payload.get("required_method_families") or payload.get("method_expectations")
    )
    assumptions = tuple(
        _optional_text(item.get("assumption_id"))
        for item in _mapping_rows(payload.get("assumption_validation_needs"))
    )
    authority_level = _authority_level_from_spec(payload)
    requires_runtime_gate = _bool(payload.get("requires_runtime_assumption_gates"), True)
    return _compiled_requirement_gap(
        family=RequirementGapFamily.METHOD_VALIDITY,
        payload=payload,
        requirement_id=requirement_id,
        claim_ref=_claim_ref(payload),
        gap_type=_gap_type_from_payload(
            payload,
            default=AcquisitionGapType.METHOD_OBLIGATION,
        ),
        authority_level=authority_level,
        mandatory_gate_state=_gate_state_from_payload(
            payload,
            default=(
                MandatoryGateState.NON_OVERRIDABLE
                if authority_level is not AuthorityLevel.RESEARCH and requires_runtime_gate
                else MandatoryGateState.NONE
            ),
        ),
        limitation_permitted=_limitation_permitted_from_payload(
            payload,
            default=not _bool(payload.get("requires_method_output"), True),
        ),
        scenario_requirement_refs=(requirement_id, *method_families),
        missing_requirement_fields=(
            *(f"method_family:{family}" for family in method_families),
            *(f"assumption_gate:{item}" for item in assumptions if item),
            *(
                ("method_output_ref",)
                if _bool(payload.get("requires_method_output"), True)
                else ()
            ),
            *(
                ("uncertainty_envelope_ref",)
                if _bool(payload.get("requires_uncertainty_envelope"), True)
                else ()
            ),
        ),
    )


def _scholar_support_requirement_gap(payload: Mapping[str, Any]) -> AcquisitionRequirementGap:
    requirement_id = _requirement_id(payload)
    authority_level = _authority_level_from_spec(payload)
    publication_tier = _optional_text(payload.get("required_publication_tier"))
    mandatory_default = (
        MandatoryGateState.NON_OVERRIDABLE
        if _bool(_metadata(payload).get("scholar_support_mandatory"), False)
        and authority_level is not AuthorityLevel.RESEARCH
        else MandatoryGateState.NONE
    )
    publication_tier_fields = (
        (f"publication_tier:{publication_tier}",) if publication_tier else ()
    )
    return _compiled_requirement_gap(
        family=RequirementGapFamily.SCHOLAR_SUPPORT,
        payload=payload,
        requirement_id=requirement_id,
        claim_ref=_claim_ref(payload),
        gap_type=_gap_type_from_payload(
            payload,
            default=AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT,
        ),
        authority_level=authority_level,
        mandatory_gate_state=_gate_state_from_payload(payload, default=mandatory_default),
        limitation_permitted=_limitation_permitted_from_payload(payload, default=False),
        scenario_requirement_refs=(
            requirement_id,
            *publication_tier_fields,
        ),
        missing_requirement_fields=(
            *publication_tier_fields,
            f"replication_count:{_int(payload.get('required_replication_count'))}",
            f"independence_breadth:{_int(payload.get('required_independence_breadth'))}",
        ),
    )


def _participation_provenance_requirement_gap(
    payload: Mapping[str, Any],
) -> AcquisitionRequirementGap:
    requirement_id = _requirement_id(payload)
    authority_level = _authority_level_from_spec(payload)
    required_modes = _text_tuple(payload.get("required_modes"))
    requested_use = _optional_text(payload.get("claim_use_requested")) or ""
    mandatory_default = (
        MandatoryGateState.NON_OVERRIDABLE
        if authority_level is not AuthorityLevel.RESEARCH
        and requested_use in {"prevalence", "legitimacy", "participation_legitimacy"}
        else MandatoryGateState.NONE
    )
    return _compiled_requirement_gap(
        family=RequirementGapFamily.PARTICIPATION_PROVENANCE,
        payload=payload,
        requirement_id=requirement_id,
        claim_ref=_claim_ref(payload),
        gap_type=_gap_type_from_payload(
            payload,
            default=AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM,
        ),
        authority_level=authority_level,
        mandatory_gate_state=_gate_state_from_payload(payload, default=mandatory_default),
        limitation_permitted=_limitation_permitted_from_payload(
            payload,
            default=requested_use not in {"prevalence", "legitimacy"},
        ),
        scenario_requirement_refs=(requirement_id, *required_modes),
        missing_requirement_fields=(
            *(f"required_mode:{mode}" for mode in required_modes),
            f"sampling_frame:{_optional_text(payload.get('required_sampling_frame')) or 'missing'}",
            "representativeness_class",
            "consent_redaction",
            "dissent_handling",
            "sponsor_disclosure",
        ),
    )


def _compiled_requirement_gap(
    *,
    family: RequirementGapFamily,
    payload: Mapping[str, Any],
    requirement_id: str,
    claim_ref: str,
    gap_type: AcquisitionGapType,
    authority_level: AuthorityLevel,
    mandatory_gate_state: MandatoryGateState,
    limitation_permitted: bool,
    scenario_requirement_refs: Sequence[str],
    missing_requirement_fields: Sequence[str],
) -> AcquisitionRequirementGap:
    metadata = _metadata(payload)
    return AcquisitionRequirementGap(
        requirement_gap_id=_requirement_gap_id(family=family, requirement_id=requirement_id),
        requirement_family=family,
        compiled_requirement_ref=requirement_id,
        requirement_schema_version=_optional_text(payload.get("schema_version")),
        gap_type=gap_type,
        claim_ref=claim_ref,
        scenario_requirement_refs=_text_tuple(scenario_requirement_refs),
        missing_requirement_fields=_text_tuple(missing_requirement_fields),
        authority_level=authority_level,
        mandatory_gate_state=mandatory_gate_state,
        mandatory_gate_refs=_text_tuple(metadata.get("mandatory_gate_refs")),
        limitation_permitted=limitation_permitted,
        decision_owner_ref=_optional_text(
            metadata.get("decision_owner_ref") or metadata.get("decision_owner")
        ),
        producer_output_ref=_optional_text(metadata.get("producer_output_ref")),
        calibration_feedback_ref=_optional_text(metadata.get("calibration_feedback_ref")),
        metadata={
            "compiled_requirement_schema_version": _optional_text(payload.get("schema_version")),
            "requirement_family": family.value,
            "requirement_rule_version": _optional_text(
                payload.get("rule_version_ref") or payload.get("rule_version")
            ),
        },
    )


def acquisition_report_inputs(report: AcquisitionPlannerReport) -> list[artifacts.InputRef]:
    """Build manifest lineage inputs for a persisted acquisition planner report."""

    inputs: list[artifacts.InputRef] = []
    seen: set[str] = set()
    for record in report.acquisition_records:
        for role, ref in (
            ("voi_ranking", record.voi_ranking_ref),
            ("producer_output", record.producer_output_ref),
            ("calibration_feedback", record.calibration_feedback_ref),
        ):
            if not ref or ref in seen:
                continue
            artifact_id = _artifact_id(ref)
            if artifact_id is None:
                continue
            seen.add(ref)
            inputs.append(artifacts.InputRef(artifact_id=artifact_id, role=role))
    return inputs


def persist_acquisition_planner_report(
    store: Any,
    report: AcquisitionPlannerReport,
    *,
    inputs: list[artifacts.InputRef] | None = None,
) -> artifacts.ArtifactRef:
    """Persist an acquisition planner report as a first-class CAS artifact."""

    return store.put_json(
        report,
        artifacts.PutOptions(
            kind=ACQUISITION_PLANNER_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=ACQUISITION_PLANNER_SCHEMA_NAME,
                version=ACQUISITION_PLANNER_SCHEMA_VERSION_SHORT,
            ),
            inputs=list(inputs) if inputs is not None else acquisition_report_inputs(report),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def load_acquisition_planner_report(
    store: Any,
    ref: artifacts.ArtifactRef,
) -> AcquisitionPlannerReport:
    """Load a persisted acquisition planner report from CAS."""

    payload = canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return AcquisitionPlannerReport.model_validate(payload)


def acquisition_planner_reports_from_quality_evidence(
    quality_evidence: Mapping[str, Any],
) -> tuple[AcquisitionPlannerReport, ...]:
    """Extract acquisition planner reports from known runtime quality surfaces."""

    reports: list[AcquisitionPlannerReport] = []
    for payload in _iter_report_payloads(quality_evidence):
        try:
            reports.append(AcquisitionPlannerReport.model_validate(payload))
        except Exception as exc:
            _LOGGER.debug("Skipping invalid acquisition planner report payload: %s", exc)
            continue
    return tuple(reports)


def acquisition_report_deficit_records(
    report: AcquisitionPlannerReport | Mapping[str, Any],
    *,
    ttl_expires_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Project terminal acquisition dispositions into status-deficit records."""

    normalized = (
        report
        if isinstance(report, AcquisitionPlannerReport)
        else AcquisitionPlannerReport.model_validate(report)
    )
    expires_at = _utc(ttl_expires_at) if ttl_expires_at else _utc() + timedelta(
        seconds=DEFAULT_ACQUISITION_TTL_SECONDS
    )
    rows: list[dict[str, Any]] = []
    for record in normalized.acquisition_records:
        deficit_id = _terminal_deficit_id(record)
        disposition = _deficit_disposition(record.terminal_disposition)
        if deficit_id is None or disposition is None:
            continue
        rows.append(
            {
                "deficit_id": deficit_id,
                "deficit_family": "evidence_acquisition",
                "deficit_code": record.terminal_disposition.value,
                "claim_ids": [record.claim_ref],
                "authority_level": record.authority_level.value,
                "audience_scope": _audience_scope(record),
                "disposition": disposition,
                "support_cap": _support_cap(record.terminal_disposition),
                "readiness_cap": _readiness_cap(record.terminal_disposition),
                "max_audience": _max_audience(record.terminal_disposition),
                "owner": record.decision_owner_ref or record.decision_owner,
                "ttl_expires_at": expires_at.isoformat(),
                "runtime_event_ref": record.runtime_event_ref,
                "evidence_ref": record.evidence_ref,
                "public_limitation_note": _public_limitation_note(record),
                "review_refs": [record.decision_owner_ref] if record.decision_owner_ref else [],
            }
        )
    return rows


def acquisition_planner_scorecard_gates(
    report_or_quality_evidence: AcquisitionPlannerReport | Mapping[str, Any] | None,
    *,
    canary_kind: str,
) -> list[dict[str, Any]]:
    """Project acquisition records into scorecard-readable gates."""

    reports = _coerce_reports(report_or_quality_evidence)
    gates: list[dict[str, Any]] = []
    for report in reports:
        for record in report.acquisition_records:
            gates.append(_scorecard_gate(record, canary_kind=canary_kind))
    return gates


def _plan_gap(
    *,
    run_id: str,
    gap: AcquisitionGap,
    ranked: Sequence[_RankedVOI],
    ranking_ref: str | None,
) -> AcquisitionActionRecord:
    eligible = tuple(_eligible_strategies(gap))
    eligible_values = {strategy.value for strategy in eligible}
    ranked_records = _ranked_strategy_records(
        gap=gap,
        eligible_values=eligible_values,
        ranked=ranked,
    )
    recommended = _recommended_strategy(gap=gap, eligible=eligible, ranked_records=ranked_records)
    disposition = _disposition_for_strategy(recommended)
    ineligible = tuple(_ineligible_strategy_values(eligible_values, ranked))
    ineligible_records = tuple(
        record for record in ranked_records if not record.eligible
    ) or tuple(
        AcquisitionStrategyRecord(
            strategy=strategy,
            eligible=False,
            eligibility_reason=_ineligibility_reason(
                strategy=strategy,
                gap=gap,
                eligible_values=eligible_values,
            ),
            mandatory_gate_state=gap.mandatory_gate_state,
        )
        for strategy in ineligible
    )
    strategy_records = _ordered_strategy_records(
        recommended=recommended,
        eligible=eligible,
        ranked_records=ranked_records,
        mandatory_gate_state=gap.mandatory_gate_state,
    )
    next_action = _next_action(gap=gap, strategy=recommended, disposition=disposition)
    record = AcquisitionActionRecord(
        acquisition_id=f"acquisition:{run_id}:{gap.gap_id}",
        gap_id=gap.gap_id,
        gap_type=gap.gap_type,
        claim_ref=gap.claim_ref,
        scenario_requirement_refs=gap.scenario_requirement_refs,
        requirement_gap_ref=gap.requirement_gap_ref,
        requirement_family=gap.requirement_family,
        compiled_requirement_ref=gap.compiled_requirement_ref,
        requirement_schema_version=gap.requirement_schema_version,
        missing_requirement_fields=gap.missing_requirement_fields,
        authority_level=gap.authority_level,
        mandatory_gate_state=gap.mandatory_gate_state,
        mandatory_gate_refs=gap.mandatory_gate_refs,
        eligible_strategies=eligible,
        ineligible_strategies=ineligible,
        strategy_records=strategy_records,
        ineligible_strategy_records=ineligible_records,
        voi_ranking_ref=ranking_ref,
        recommended_strategy=recommended,
        decision_owner=_decision_owner(gap, disposition),
        decision_owner_ref=gap.decision_owner_ref,
        commit_authority=_commit_authority(gap, disposition),
        terminal_disposition=disposition,
        limitation_ref=_limitation_ref(gap, disposition),
        accepted_deficit_ref=_accepted_deficit_ref(gap, disposition),
        blocker_ref=_blocker_ref(gap, disposition),
        producer_expected=_producer_expected(recommended),
        producer_output_ref=gap.producer_output_ref,
        calibration_feedback_ref=(
            gap.calibration_feedback_ref or f"calibration_feedback:{gap.gap_id}"
        ),
        public_projection_effect=_public_projection_effect(disposition),
        next_actions=(next_action,),
        status=_record_status(disposition),
        runtime_event_ref=f"event://runtime/acquisition/{_slug(run_id)}/{_slug(gap.gap_id)}",
        evidence_ref=f"quality_evidence/acquisition_planner/{_slug(gap.gap_id)}.json",
        authority_boundary=_authority_boundary(),
    )
    return record


def _eligible_strategies(gap: AcquisitionGap) -> tuple[AcquisitionStrategy, ...]:
    if gap.mandatory_gate_state is MandatoryGateState.NON_OVERRIDABLE:
        values = (
            *_required_remediation_strategies(gap.gap_type),
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        )
        return _dedupe_strategies(values)
    if gap.mandatory_gate_state is MandatoryGateState.OVERRIDABLE_BY_GOVERNED_COMMIT:
        return _filter_limitation_permission(gap, _overridable_gate_strategies(gap.gap_type))
    if gap.authority_level is AuthorityLevel.RESEARCH:
        return _filter_limitation_permission(gap, _research_no_gate_strategies(gap.gap_type))
    return _filter_limitation_permission(gap, _governed_no_gate_strategies(gap.gap_type))


def _research_no_gate_strategies(
    gap_type: AcquisitionGapType,
) -> tuple[AcquisitionStrategy, ...]:
    matrix = {
        AcquisitionGapType.LEGAL_CORPUS_COVERAGE: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.RERUN,
        ),
        AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.SCENARIO_SOURCE_FAMILY: (
            AcquisitionStrategy.PUBLIC_REGISTRY,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.DATA_SNAPSHOT_RELEASE: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.FACET: (
            AcquisitionStrategy.PUBLIC_REGISTRY,
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.METHOD_OBLIGATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.RERUN,
        ),
        AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM: (
            AcquisitionStrategy.CONSULTATION,
            AcquisitionStrategy.SURVEY,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.COUNTEREVIDENCE_REBUTTAL: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.PUBLIC_REGISTRY,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.COST_SLA_RUNTIME_DEGRADATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
    }
    return matrix[gap_type]


def _governed_no_gate_strategies(
    gap_type: AcquisitionGapType,
) -> tuple[AcquisitionStrategy, ...]:
    matrix = {
        AcquisitionGapType.LEGAL_CORPUS_COVERAGE: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.RERUN,
        ),
        AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
        ),
        AcquisitionGapType.SCENARIO_SOURCE_FAMILY: (
            AcquisitionStrategy.PUBLIC_REGISTRY,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
        ),
        AcquisitionGapType.DATA_SNAPSHOT_RELEASE: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.AGENCY_REQUEST,
        ),
        AcquisitionGapType.FACET: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
        ),
        AcquisitionGapType.METHOD_OBLIGATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.METHOD_REMEDIATION,
        ),
        AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM: (
            AcquisitionStrategy.CONSULTATION,
            AcquisitionStrategy.SURVEY,
            AcquisitionStrategy.AGENCY_REQUEST,
        ),
        AcquisitionGapType.COUNTEREVIDENCE_REBUTTAL: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
        ),
        AcquisitionGapType.COST_SLA_RUNTIME_DEGRADATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
    }
    return matrix[gap_type]


def _overridable_gate_strategies(
    gap_type: AcquisitionGapType,
) -> tuple[AcquisitionStrategy, ...]:
    matrix = {
        AcquisitionGapType.LEGAL_CORPUS_COVERAGE: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.SCENARIO_SOURCE_FAMILY: (
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.DATA_SNAPSHOT_RELEASE: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.FACET: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.METHOD_OBLIGATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.METHOD_REMEDIATION,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM: (
            AcquisitionStrategy.CONSULTATION,
            AcquisitionStrategy.SURVEY,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.COUNTEREVIDENCE_REBUTTAL: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
        ),
        AcquisitionGapType.COST_SLA_RUNTIME_DEGRADATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
    }
    return matrix[gap_type]


def _required_remediation_strategies(
    gap_type: AcquisitionGapType,
) -> tuple[AcquisitionStrategy, ...]:
    matrix = {
        AcquisitionGapType.LEGAL_CORPUS_COVERAGE: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
        ),
        AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
        ),
        AcquisitionGapType.SCENARIO_SOURCE_FAMILY: (
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
        ),
        AcquisitionGapType.DATA_SNAPSHOT_RELEASE: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.RERUN,
        ),
        AcquisitionGapType.FACET: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
        ),
        AcquisitionGapType.METHOD_OBLIGATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.METHOD_REMEDIATION,
        ),
        AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
        ),
        AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM: (
            AcquisitionStrategy.CONSULTATION,
            AcquisitionStrategy.SURVEY,
        ),
        AcquisitionGapType.COUNTEREVIDENCE_REBUTTAL: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.RERUN,
        ),
        AcquisitionGapType.COST_SLA_RUNTIME_DEGRADATION: (
            AcquisitionStrategy.RERUN,
        ),
    }
    return matrix[gap_type]


def _filter_limitation_permission(
    gap: AcquisitionGap,
    strategies: Sequence[AcquisitionStrategy],
) -> tuple[AcquisitionStrategy, ...]:
    filtered: list[AcquisitionStrategy] = []
    for strategy in strategies:
        if strategy is AcquisitionStrategy.PUBLISH_WITH_LIMITATION and not gap.limitation_permitted:
            continue
        filtered.append(strategy)
    return _dedupe_strategies(filtered)


def _ranked_voi_by_gap(
    voi_report: BaseModel | Mapping[str, Any] | None,
) -> dict[str, tuple[_RankedVOI, ...]]:
    payload = _model_or_mapping(voi_report)
    if not payload:
        return {}
    rows = _rows(payload.get("decisions"))
    ranked: list[_RankedVOI] = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        strategy = (
            _strategy_key(metadata.get("acquisition_strategy"))
            or _strategy_key(metadata.get("strategy"))
            or _strategy_key(row.get("recommended_action"))
        )
        if not strategy:
            continue
        ranked.append(
            _RankedVOI(
                gap_id=_optional_text(
                    metadata.get("requirement_gap_id")
                    or metadata.get("gap_id")
                    or row.get("requirement_gap_id")
                    or row.get("gap_id")
                ),
                strategy=strategy,
                decision_ref=_required_text(row.get("decision_id")),
                expected_value=_float(row.get("expected_value")),
                expected_cost=max(0.0, _float(row.get("expected_cost"))),
            )
        )
    grouped: dict[str, list[_RankedVOI]] = {}
    wildcard: list[_RankedVOI] = []
    for item in ranked:
        if item.gap_id:
            grouped.setdefault(item.gap_id, []).append(item)
        else:
            wildcard.append(item)
    result: dict[str, tuple[_RankedVOI, ...]] = {}
    for gap_id, items in grouped.items():
        result[gap_id] = tuple(sorted(items, key=_rank_sort_key))
    if wildcard:
        result["*"] = tuple(sorted(wildcard, key=_rank_sort_key))
    return result


def _ranked_strategy_records(
    *,
    gap: AcquisitionGap,
    eligible_values: set[str],
    ranked: Sequence[_RankedVOI],
) -> tuple[AcquisitionStrategyRecord, ...]:
    records: list[AcquisitionStrategyRecord] = []
    for index, item in enumerate(sorted(ranked, key=_rank_sort_key), start=1):
        eligible = item.strategy in eligible_values
        records.append(
            AcquisitionStrategyRecord(
                strategy=item.strategy,
                eligible=eligible,
                eligibility_reason=(
                    "eligible_after_gap_authority_gate_matrix"
                    if eligible
                    else _ineligibility_reason(
                        strategy=item.strategy,
                        gap=gap,
                        eligible_values=eligible_values,
                    )
                ),
                mandatory_gate_state=gap.mandatory_gate_state,
                voi_decision_ref=item.decision_ref,
                voi_rank=index,
                voi_expected_value=item.expected_value,
                voi_expected_cost=item.expected_cost,
                next_action=_action_for_strategy_key(item.strategy) if eligible else None,
            )
        )
    return tuple(records)


def _recommended_strategy(
    *,
    gap: AcquisitionGap,
    eligible: Sequence[AcquisitionStrategy],
    ranked_records: Sequence[AcquisitionStrategyRecord],
) -> AcquisitionStrategy:
    ranked_eligible = [
        AcquisitionStrategy(record.strategy)
        for record in ranked_records
        if record.eligible and record.strategy in {strategy.value for strategy in eligible}
    ]
    if gap.mandatory_gate_state is MandatoryGateState.NON_OVERRIDABLE:
        remediations = set(_required_remediation_strategies(gap.gap_type))
        for strategy in ranked_eligible:
            if strategy in remediations:
                return strategy
        if not ranked_records:
            for strategy in _default_priority(gap.gap_type):
                if strategy in remediations:
                    return strategy
        return AcquisitionStrategy.CLOSEOUT_BLOCK
    if ranked_eligible:
        return ranked_eligible[0]
    for strategy in _default_priority(gap.gap_type):
        if strategy in eligible:
            return strategy
    return AcquisitionStrategy.CLOSEOUT_BLOCK


def _default_priority(gap_type: AcquisitionGapType) -> tuple[AcquisitionStrategy, ...]:
    base = {
        AcquisitionGapType.LEGAL_CORPUS_COVERAGE: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY: (
            AcquisitionStrategy.LEGAL_CORPUS_EXPANSION,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.SCENARIO_SOURCE_FAMILY: (
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
            AcquisitionStrategy.PUBLIC_REGISTRY,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.DATA_SNAPSHOT_RELEASE: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.FACET: (
            AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD,
            AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.METHOD_OBLIGATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.METHOD_REMEDIATION,
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM: (
            AcquisitionStrategy.CONSULTATION,
            AcquisitionStrategy.SURVEY,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.COUNTEREVIDENCE_REBUTTAL: (
            AcquisitionStrategy.ACADEMIC_RETRIEVAL,
            AcquisitionStrategy.AGENCY_REQUEST,
            AcquisitionStrategy.PUBLIC_REGISTRY,
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
        AcquisitionGapType.COST_SLA_RUNTIME_DEGRADATION: (
            AcquisitionStrategy.RERUN,
            AcquisitionStrategy.PUBLISH_WITH_LIMITATION,
            AcquisitionStrategy.ACCEPTED_DEFICIT,
            AcquisitionStrategy.CLOSEOUT_BLOCK,
        ),
    }
    return base[gap_type]


def _ordered_strategy_records(
    *,
    recommended: AcquisitionStrategy,
    eligible: Sequence[AcquisitionStrategy],
    ranked_records: Sequence[AcquisitionStrategyRecord],
    mandatory_gate_state: MandatoryGateState,
) -> tuple[AcquisitionStrategyRecord, ...]:
    by_strategy = {record.strategy: record for record in ranked_records if record.eligible}
    rows: list[AcquisitionStrategyRecord] = []
    for strategy in (recommended, *eligible):
        if strategy.value in {row.strategy for row in rows}:
            continue
        rows.append(
            by_strategy.get(strategy.value)
            or AcquisitionStrategyRecord(
                strategy=strategy.value,
                eligible=True,
                eligibility_reason="eligible_after_gap_authority_gate_matrix",
                mandatory_gate_state=mandatory_gate_state,
                next_action=_action_for_strategy(strategy),
            )
        )
    return tuple(rows)


def _ineligible_strategy_values(
    eligible_values: set[str],
    ranked: Sequence[_RankedVOI],
) -> list[str]:
    values = {
        strategy.value for strategy in AcquisitionStrategy if strategy.value not in eligible_values
    }
    values.update(item.strategy for item in ranked if item.strategy not in eligible_values)
    return sorted(values)


def _ineligibility_reason(
    *,
    strategy: str,
    gap: AcquisitionGap,
    eligible_values: set[str],
) -> str:
    if strategy not in {item.value for item in AcquisitionStrategy}:
        return "strategy_not_in_adr_0166_taxonomy"
    if gap.mandatory_gate_state is MandatoryGateState.NON_OVERRIDABLE:
        return "non_overridable_mandatory_gate_dominates_voi"
    if (
        strategy == AcquisitionStrategy.PUBLISH_WITH_LIMITATION.value
        and not gap.limitation_permitted
    ):
        return "authority_profile_does_not_permit_public_limitation"
    if strategy not in eligible_values:
        return "strategy_not_eligible_for_gap_authority_gate_matrix"
    return "eligible"


def _dedupe_strategies(
    strategies: Iterable[AcquisitionStrategy],
) -> tuple[AcquisitionStrategy, ...]:
    deduped: list[AcquisitionStrategy] = []
    for strategy in strategies:
        if strategy not in deduped:
            deduped.append(strategy)
    return tuple(deduped)


def _disposition_for_strategy(strategy: AcquisitionStrategy) -> AcquisitionDisposition:
    if strategy is AcquisitionStrategy.CLOSEOUT_BLOCK:
        return AcquisitionDisposition.CLOSEOUT_BLOCK
    if strategy is AcquisitionStrategy.ACCEPTED_DEFICIT:
        return AcquisitionDisposition.ACCEPTED_DEFICIT
    if strategy is AcquisitionStrategy.PUBLISH_WITH_LIMITATION:
        return AcquisitionDisposition.PUBLISH_WITH_LIMITATION
    if strategy is AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY:
        return AcquisitionDisposition.PROXY_WITH_LIMITATION
    if strategy is AcquisitionStrategy.RERUN:
        return AcquisitionDisposition.RERUN
    return AcquisitionDisposition.ACQUIRE


def _next_action(
    *,
    gap: AcquisitionGap,
    strategy: AcquisitionStrategy,
    disposition: AcquisitionDisposition,
) -> AcquisitionNextAction:
    owner = gap.decision_owner_ref or _decision_owner(gap, disposition)
    return AcquisitionNextAction(
        action=_action_for_strategy(strategy),
        strategy=strategy.value,
        owner=owner,
        message=_next_action_message(gap=gap, strategy=strategy, disposition=disposition),
        producer_expected=_producer_expected(strategy),
        commit_required=_commit_required(disposition),
        blocks_closeout=disposition is AcquisitionDisposition.CLOSEOUT_BLOCK,
        evidence_ref=f"quality_evidence/acquisition_planner/{_slug(gap.gap_id)}.json",
    )


def _action_for_strategy(strategy: AcquisitionStrategy) -> str:
    return _action_for_strategy_key(strategy.value)


def _action_for_strategy_key(strategy: str) -> str:
    actions = {
        AcquisitionStrategy.CLOSEOUT_BLOCK.value: "block_closeout",
        AcquisitionStrategy.ACCEPTED_DEFICIT.value: "accept_deficit",
        AcquisitionStrategy.PUBLISH_WITH_LIMITATION.value: "record_public_limitation",
        AcquisitionStrategy.PROXY_WITH_DEGRADED_AUTHORITY.value: "proxy_with_limitation",
        AcquisitionStrategy.RERUN.value: "rerun",
        AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION.value: "remediate_source_contract",
        AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD.value: "build_production_snapshot",
        AcquisitionStrategy.METHOD_REMEDIATION.value: "remediate_method_obligation",
    }
    return actions.get(strategy, "acquire_evidence")


def _next_action_message(
    *,
    gap: AcquisitionGap,
    strategy: AcquisitionStrategy,
    disposition: AcquisitionDisposition,
) -> str:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return (
            f"Block closeout for {gap.claim_ref}; non-overridable acquisition "
            "gap cannot be bypassed by VOI ranking."
        )
    if disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return f"Record accepted evidence deficit for {gap.claim_ref}."
    if disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return (
            f"Require governed owner commit and visible limitation before {gap.claim_ref} "
            "can use proxy or limited publication."
        )
    if disposition is AcquisitionDisposition.RERUN:
        return f"Rerun required producer path for {gap.claim_ref}."
    return f"Acquire or remediate evidence via {strategy.value} for {gap.claim_ref}."


def _decision_owner(gap: AcquisitionGap, disposition: AcquisitionDisposition) -> str:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "automatic_closeout_block"
    if disposition in {
        AcquisitionDisposition.ACCEPTED_DEFICIT,
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        if gap.authority_level is AuthorityLevel.RESEARCH:
            return "researcher_or_review_owner"
        if gap.authority_level is AuthorityLevel.PRODUCTION:
            return "production_governance_human_decision_owner"
        return "governed_human_decision_owner"
    if gap.authority_level is AuthorityLevel.RESEARCH:
        return "runtime_planner"
    if gap.authority_level is AuthorityLevel.PRODUCTION:
        return "production_governance_owner"
    return "governed_workflow_owner"


def _commit_authority(gap: AcquisitionGap, disposition: AcquisitionDisposition) -> str:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "automatic_block"
    if disposition in {
        AcquisitionDisposition.ACCEPTED_DEFICIT,
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        if gap.authority_level is AuthorityLevel.RESEARCH:
            return "researcher_commit_required"
        return "human_governed_commit_required"
    return "advisory_recommendation_only"


def _commit_required(disposition: AcquisitionDisposition) -> bool:
    return disposition in {
        AcquisitionDisposition.ACCEPTED_DEFICIT,
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }


def _producer_expected(strategy: AcquisitionStrategy) -> str | None:
    producers = {
        AcquisitionStrategy.PUBLIC_REGISTRY: "fabric.public_registry",
        AcquisitionStrategy.AGENCY_REQUEST: "fabric.agency_request",
        AcquisitionStrategy.SURVEY: "scientist.participation.survey",
        AcquisitionStrategy.CONSULTATION: "scientist.participation.consultation",
        AcquisitionStrategy.LEGAL_CORPUS_EXPANSION: "lex.normpack",
        AcquisitionStrategy.ACADEMIC_RETRIEVAL: "scholar.search",
        AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD: "data_forge.snapshot",
        AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION: "fabric.source_contract",
        AcquisitionStrategy.METHOD_REMEDIATION: "foundry.method",
        AcquisitionStrategy.RERUN: "scientist.orchestration.rerun",
    }
    return producers.get(strategy)


def _limitation_ref(gap: AcquisitionGap, disposition: AcquisitionDisposition) -> str | None:
    if disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return f"limitation:{gap.gap_id}"
    return None


def _accepted_deficit_ref(
    gap: AcquisitionGap,
    disposition: AcquisitionDisposition,
) -> str | None:
    if disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return f"accepted_deficit:{gap.gap_id}"
    return None


def _blocker_ref(gap: AcquisitionGap, disposition: AcquisitionDisposition) -> str | None:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return f"blocker:{gap.gap_id}:closeout_block"
    return None


def _record_status(disposition: AcquisitionDisposition) -> Literal["ready", "limited", "blocked"]:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "blocked"
    if disposition in {
        AcquisitionDisposition.ACCEPTED_DEFICIT,
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return "limited"
    return "ready"


def _public_projection_effect(disposition: AcquisitionDisposition) -> str:
    effects = {
        AcquisitionDisposition.CLOSEOUT_BLOCK: "publication_and_closeout_blocked",
        AcquisitionDisposition.ACCEPTED_DEFICIT: "missing_evidence_explicit",
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION: "public_limitation_required",
        AcquisitionDisposition.PROXY_WITH_LIMITATION: "public_proxy_limitation_required",
        AcquisitionDisposition.RERUN: "pending_rerun_before_publication_change",
        AcquisitionDisposition.ACQUIRE: "no_public_effect_until_producer_output",
    }
    return effects[disposition]


def _terminal_deficit_id(record: AcquisitionActionRecord) -> str | None:
    return record.blocker_ref or record.limitation_ref or record.accepted_deficit_ref


def _deficit_disposition(disposition: AcquisitionDisposition) -> str | None:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "hard_block"
    if disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return "publish_with_limitation"
    if disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return "accepted_deficit"
    return None


def _support_cap(disposition: AcquisitionDisposition) -> str | None:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "blocked"
    if disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return "proxy_with_limitation"
    if disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return "context_only"
    return None


def _readiness_cap(disposition: AcquisitionDisposition) -> str | None:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "blocked"
    if disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return "external_briefing"
    if disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return "analyst_advisory"
    return None


def _max_audience(disposition: AcquisitionDisposition) -> str | None:
    if disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "none"
    if disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return "public_with_limitation"
    if disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return "internal_or_research"
    return None


def _audience_scope(record: AcquisitionActionRecord) -> str:
    if record.authority_level is AuthorityLevel.RESEARCH:
        return "research"
    if record.terminal_disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return "public_with_limitation"
    if record.terminal_disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return "blocked"
    return "runtime"


def _public_limitation_note(record: AcquisitionActionRecord) -> str | None:
    if record.terminal_disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return (
            "Publication requires an externally visible limitation; the acquisition "
            "record is routing evidence, not domain evidence."
        )
    if record.terminal_disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return "Missing evidence must remain explicit wherever this claim is summarized."
    return None


def _scorecard_gate(
    record: AcquisitionActionRecord,
    *,
    canary_kind: str,
) -> dict[str, Any]:
    serious = _normalized(canary_kind) in _SERIOUS_AUTHORITY_LEVELS
    if record.terminal_disposition is AcquisitionDisposition.CLOSEOUT_BLOCK:
        return _gate(
            record=record,
            status="fail",
            blocking=True,
            code="acquisition_planner_closeout_block",
            message=(
                "Acquisition planner emitted a closeout block; VOI ranking cannot "
                "route around a non-overridable or authority-blocking gap."
            ),
            closeout_effect="closeout_blocked",
        )
    if record.terminal_disposition in {
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION,
        AcquisitionDisposition.PROXY_WITH_LIMITATION,
    }:
        return _gate(
            record=record,
            status="warn" if serious else "pass",
            blocking=False,
            code="acquisition_planner_limitation_requires_commit",
            message=(
                "Acquisition planner recommends proxy or publication limitation; "
                "governed owner commit and visible limitation are required."
            ),
            closeout_effect="limited_closeout",
        )
    if record.terminal_disposition is AcquisitionDisposition.ACCEPTED_DEFICIT:
        return _gate(
            record=record,
            status="pass",
            blocking=False,
            code="acquisition_planner_accepted_deficit_recorded",
            message="Acquisition planner recorded an explicit accepted deficit.",
            closeout_effect="accepted_deficit",
        )
    return _gate(
        record=record,
        status="pass",
        blocking=False,
        code="acquisition_planner_next_action_recorded",
        message="Acquisition planner recorded an eligible next action.",
        closeout_effect="pending_acquisition",
    )


def _gate(
    *,
    record: AcquisitionActionRecord,
    status: Literal["pass", "warn", "fail"],
    blocking: bool,
    code: str,
    message: str,
    closeout_effect: str,
) -> dict[str, Any]:
    return {
        "name": "policy_design_acquisition_planner",
        "stage": "runtime",
        "code": code,
        "status": status,
        "layer": ACQUISITION_PLANNER_GATE_LAYER,
        "phase": ACQUISITION_PLANNER_GATE_PHASE,
        "message": message,
        "evidence_ref": record.evidence_ref,
        "next_action": record.next_actions[0].message if record.next_actions else None,
        "blocking": blocking,
        "claim_ref": record.claim_ref,
        "gap_id": record.gap_id,
        "recommended_strategy": record.recommended_strategy.value,
        "terminal_disposition": record.terminal_disposition.value,
        "closeout_effect": closeout_effect,
        "publication_effect": record.public_projection_effect,
        "owner": record.decision_owner_ref or record.decision_owner,
    }


def _coerce_reports(
    value: AcquisitionPlannerReport | Mapping[str, Any] | None,
) -> tuple[AcquisitionPlannerReport, ...]:
    if value is None:
        return ()
    if isinstance(value, AcquisitionPlannerReport):
        return (value,)
    if not isinstance(value, Mapping):
        return ()
    if "acquisition_records" in value:
        try:
            return (AcquisitionPlannerReport.model_validate(value),)
        except Exception:
            return ()
    return acquisition_planner_reports_from_quality_evidence(value)


def _iter_report_payloads(value: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for key in _REPORT_KEYS:
        payload = value.get(key)
        if isinstance(payload, Mapping):
            yield payload
        elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
            for item in payload:
                if isinstance(item, Mapping):
                    yield item
    case = value.get("policy_design_case")
    if isinstance(case, Mapping):
        yield from _iter_report_payloads(case)


def _report_summary(records: Sequence[AcquisitionActionRecord]) -> dict[str, int]:
    return {
        "record_count": len(records),
        "eligible_strategy_count": sum(len(record.eligible_strategies) for record in records),
        "ineligible_strategy_count": sum(len(record.ineligible_strategies) for record in records),
        "limited": sum(1 for record in records if record.status == "limited"),
        "blocked": sum(1 for record in records if record.status == "blocked"),
        "accepted_deficit": sum(
            1
            for record in records
            if record.terminal_disposition is AcquisitionDisposition.ACCEPTED_DEFICIT
        ),
        "acquire": sum(
            1 for record in records if record.terminal_disposition is AcquisitionDisposition.ACQUIRE
        ),
        "rerun": sum(
            1 for record in records if record.terminal_disposition is AcquisitionDisposition.RERUN
        ),
    }


def _voi_ranking_ref(voi_report: BaseModel | Mapping[str, Any] | None) -> str | None:
    payload = _model_or_mapping(voi_report)
    if not payload:
        return None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
    explicit = _optional_text(
        metadata.get("artifact_ref")
        or metadata.get("voi_ranking_ref")
        or payload.get("voi_ranking_ref")
        or payload.get("artifact_ref")
    )
    if explicit:
        return explicit
    run_id = _optional_text(payload.get("run_id"))
    return f"voi://{run_id}" if run_id else None


def _model_or_mapping(value: BaseModel | Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _spec_payload(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("compiled requirement specs must be mappings or Pydantic models")


def _metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _requirement_id(payload: Mapping[str, Any]) -> str:
    return _required_text(
        payload.get("requirement_id")
        or payload.get("data_requirement_id")
        or payload.get("method_requirement_ref")
        or payload.get("legal_requirement_ref")
    )


def _claim_ref(payload: Mapping[str, Any]) -> str:
    return _required_text(payload.get("claim_ref") or payload.get("claim_id"))


def _authority_level_from_spec(payload: Mapping[str, Any]) -> AuthorityLevel:
    metadata = _metadata(payload)
    tokens = [
        metadata.get("authority_level"),
        payload.get("authority_level"),
        payload.get("authority_profile_ref"),
        payload.get("authority_profile"),
        payload.get("authority_profile_refs"),
    ]
    for token in _flatten_text(tokens):
        normalized = _normalized(token)
        if any(
            marker in normalized
            for marker in ("production", "publishable", "regulated")
        ):
            return AuthorityLevel.PRODUCTION
        if any(marker in normalized for marker in ("governed", "official", "serious")):
            return AuthorityLevel.GOVERNED
    return AuthorityLevel.RESEARCH


def _gap_type_from_payload(
    payload: Mapping[str, Any],
    *,
    default: AcquisitionGapType,
) -> AcquisitionGapType:
    metadata = _metadata(payload)
    value = (
        metadata.get("acquisition_gap_type")
        or metadata.get("gap_type")
        or payload.get("acquisition_gap_type")
        or payload.get("gap_type")
    )
    if value is None:
        return default
    return AcquisitionGapType(_strategy_key(value) or str(value))


def _gate_state_from_payload(
    payload: Mapping[str, Any],
    *,
    default: MandatoryGateState,
) -> MandatoryGateState:
    metadata = _metadata(payload)
    value = (
        metadata.get("mandatory_gate_state")
        or metadata.get("acquisition_mandatory_gate_state")
        or payload.get("mandatory_gate_state")
        or payload.get("acquisition_mandatory_gate_state")
    )
    if value is None:
        return default
    return MandatoryGateState(_strategy_key(value) or str(value))


def _limitation_permitted_from_payload(
    payload: Mapping[str, Any],
    *,
    default: bool,
) -> bool:
    metadata = _metadata(payload)
    value = (
        metadata.get("limitation_permitted")
        if "limitation_permitted" in metadata
        else payload.get("limitation_permitted")
        if "limitation_permitted" in payload
        else None
    )
    return _bool(value, default)


def _requirement_gap_id(
    *,
    family: RequirementGapFamily,
    requirement_id: str,
) -> str:
    return f"requirement-gap:{family.value}:{requirement_id}"


def _artifact_id(value: str) -> str | None:
    text = str(value).strip()
    if text.startswith("sha256:"):
        return text
    if text.startswith("cas://sha256:"):
        return text.removeprefix("cas://")
    return None


def _rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _authority_boundary() -> dict[str, tuple[str, ...]]:
    return {
        "authoritative_for": (
            "gap_detected",
            "eligible_strategies",
            "ineligible_strategies",
            "voi_ranking_considered",
            "decision_owner",
            "terminal_disposition",
            "producer_expected",
            "calibration_feedback_target",
        ),
        "may_not_use_for": (
            "legal_authority",
            "source_family_satisfaction",
            "data_quality",
            "method_validity",
            "participation_representativeness",
            "claim_support",
            "closeout_pass",
        ),
    }


def _rank_sort_key(item: _RankedVOI) -> tuple[float, float, str]:
    return (-item.expected_value, item.expected_cost, item.strategy)


def _strategy_key(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    return text.casefold().replace("-", "_").replace(" ", "_")


def _required_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("required text value cannot be blank")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _flatten_text(values: Iterable[object]) -> tuple[str, ...]:
    flattened: list[str] = []
    for value in values:
        flattened.extend(_text_tuple(value))
    return tuple(flattened)


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = tuple(str(item) for item in value)
    else:
        values = (str(value),)
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _slug(value: object) -> str:
    text = str(value or "").strip().casefold()
    chars = [char if char.isalnum() else "-" for char in text]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug or "unknown"


def _normalized(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _authority_level_from_capability_posture(value: object) -> AuthorityLevel:
    normalized = _normalized(value)
    if normalized == "production":
        return AuthorityLevel.PRODUCTION
    if normalized in {"governed", "governed_pilot", "serious_runtime"}:
        return AuthorityLevel.GOVERNED
    return AuthorityLevel.RESEARCH


def _capability_failure_gap_type(gap_type: str, status: str) -> AcquisitionGapType:
    normalized_gap = _normalized(gap_type)
    normalized_status = _normalized(status)
    if normalized_gap in {"construct_gap", "source_gap", "acquisition_gap"}:
        return AcquisitionGapType.SCENARIO_SOURCE_FAMILY
    if normalized_gap == "legal_authority_gap":
        return AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY
    if normalized_gap in {"freshness_gap", "sample_size_gap", "rights_gap"}:
        return AcquisitionGapType.DATA_SNAPSHOT_RELEASE
    if normalized_gap == "construct_validity_gap":
        return AcquisitionGapType.FACET
    if normalized_status == "blocked_rights_boundary":
        return AcquisitionGapType.DATA_SNAPSHOT_RELEASE
    if normalized_status == "blocked_authority_boundary":
        return AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY
    return AcquisitionGapType.SCENARIO_SOURCE_FAMILY


def _capability_failure_gate_state(
    node: object,
    authority_level: AuthorityLevel,
) -> MandatoryGateState:
    if authority_level is AuthorityLevel.RESEARCH:
        return MandatoryGateState.NONE
    if str(getattr(node, "severity", "")).startswith("blocking"):
        return MandatoryGateState.NON_OVERRIDABLE
    return MandatoryGateState.OVERRIDABLE_BY_GOVERNED_COMMIT


__all__ = [
    "ACQUISITION_FAMILY_DENOMINATOR",
    "ACQUISITION_PLANNER_GATE_LAYER",
    "ACQUISITION_PLANNER_GATE_PHASE",
    "ACQUISITION_PLANNER_KIND",
    "ACQUISITION_PLANNER_REPORT_KEY",
    "ACQUISITION_PLANNER_SCHEMA_NAME",
    "ACQUISITION_PLANNER_SCHEMA_VERSION",
    "ACQUISITION_RECEIPT_KIND",
    "ACQUISITION_RECEIPT_SCHEMA_VERSION",
    "AcquisitionActionRecord",
    "AcquisitionAffectedRegion",
    "AcquisitionCaptureProvenance",
    "AcquisitionDisposition",
    "AcquisitionFamily",
    "AcquisitionFamilyScore",
    "AcquisitionGap",
    "AcquisitionGapType",
    "AcquisitionGroundingRederivation",
    "AcquisitionJournalEntry",
    "AcquisitionNetworkCallCounter",
    "AcquisitionNextAction",
    "AcquisitionOwnerArtifact",
    "AcquisitionOwnerGateway",
    "AcquisitionPlan",
    "AcquisitionPlanner",
    "AcquisitionPlannerReport",
    "AcquisitionReceipt",
    "AcquisitionRequirementGap",
    "AcquisitionStrangleReceipt",
    "AcquisitionStrategy",
    "AcquisitionStrategyRecord",
    "AcquisitionWorldSnapshot",
    "AcquisitionWorldWriteOutcome",
    "AuthorityLevel",
    "MandatoryGateState",
    "RealAcquisitionOwnerGateway",
    "RecordedAcquisitionOwnerGateway",
    "RequiredDataGap",
    "RequirementGapFamily",
    "acquisition_gaps_from_capability_failure_modes",
    "acquisition_planner_reports_from_quality_evidence",
    "acquisition_planner_scorecard_gates",
    "acquisition_report_deficit_records",
    "acquisition_report_inputs",
    "acquisition_request_from_world_acquirable",
    "acquisition_strangle_receipt",
    "data_need_spec_payload",
    "load_acquisition_planner_report",
    "persist_acquisition_planner_report",
    "plan_evidence_acquisition",
    "plan_requirement_gap_acquisition",
    "rank_acquisition_candidates_by_family",
    "requirement_gaps_from_compiled_specs",
    "run_acquisition_closed_loop",
    "validate_acquisition_receipt",
]
