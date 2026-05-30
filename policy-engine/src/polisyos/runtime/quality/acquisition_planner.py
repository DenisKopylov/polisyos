"""Evidence acquisition decision-boundary planner.

The planner implements ADR-0166 as a runtime routing artifact: evidence gaps are
mapped to eligible strategies before VOI ranking is considered. The resulting
records are governance and closeout inputs; they do not satisfy domain evidence
slots.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon

ACQUISITION_PLANNER_SCHEMA_VERSION = "policyos.runtime.acquisition_planner.v1"
ACQUISITION_PLANNER_KIND = "runtime.acquisition_planner_report"
ACQUISITION_PLANNER_SCHEMA_NAME = "polisyos.runtime.quality.AcquisitionPlannerReport"
ACQUISITION_PLANNER_SCHEMA_VERSION_SHORT = "1.0"
ACQUISITION_PLANNER_REPORT_KEY = "acquisition_planner_report"
ACQUISITION_PLANNER_GATE_LAYER = "acquisition_planner"
ACQUISITION_PLANNER_GATE_PHASE = "evidence_acquisition_boundary"
DEFAULT_ACQUISITION_TTL_SECONDS = 7 * 24 * 60 * 60

_REPORT_KEYS = (
    "acquisition_planner_report",
    "evidence_acquisition_planner",
    "evidence_acquisition_report",
    "acquisition_planner",
)
_SERIOUS_AUTHORITY_LEVELS = frozenset({"governed", "production", "serious_runtime"})
_LOGGER = logging.getLogger(__name__)


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
    "ACQUISITION_PLANNER_GATE_LAYER",
    "ACQUISITION_PLANNER_GATE_PHASE",
    "ACQUISITION_PLANNER_KIND",
    "ACQUISITION_PLANNER_REPORT_KEY",
    "ACQUISITION_PLANNER_SCHEMA_NAME",
    "ACQUISITION_PLANNER_SCHEMA_VERSION",
    "AcquisitionActionRecord",
    "AcquisitionDisposition",
    "AcquisitionGap",
    "AcquisitionGapType",
    "AcquisitionNextAction",
    "AcquisitionPlannerReport",
    "AcquisitionRequirementGap",
    "AcquisitionStrategy",
    "AcquisitionStrategyRecord",
    "AuthorityLevel",
    "MandatoryGateState",
    "RequirementGapFamily",
    "acquisition_gaps_from_capability_failure_modes",
    "acquisition_planner_reports_from_quality_evidence",
    "acquisition_planner_scorecard_gates",
    "acquisition_report_deficit_records",
    "acquisition_report_inputs",
    "load_acquisition_planner_report",
    "persist_acquisition_planner_report",
    "plan_evidence_acquisition",
    "plan_requirement_gap_acquisition",
    "requirement_gaps_from_compiled_specs",
]
