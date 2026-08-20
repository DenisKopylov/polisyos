"""Layer 2 S8 value-choice provenance contracts and P20/P22 firewalls."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel
from polisyos.runtime.quality.design_axes.blind_spot_firewalls import (
    P22MandateLegitimacyError,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    P26ResponsibilityIntegrityError,
)

LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s8_value_choice.v1"
LAYER2_S8_VALUE_CHOICE_RULE_VERSION = "policyos.layer2.s8.value_choice.v1"
S8_VALUE_CHOICE_CELL_REF = "ACTOR.value_choice_provenance"
S8_VALUE_CHOICE_FLOOR_ID = "s8_value_provenance"
P20_VALUE_SCHEDULE_RESOLVER_ABSENT_CODE = "p20_value_schedule_resolver_absent"
# Reserved for a future owner-backed resolver's per-reference failure.
P20_VALUE_SCHEDULE_REF_UNRESOLVABLE_CODE = "p20_value_schedule_ref_unresolvable"

ValueSourceClass = Literal[
    "authorized_governance_schedule",
    "participatory_process",
    "legal_mandate",
    "foundry_social_weight_provenance",
    "llm_candidate",
    "corpus_derived",
    "ad_hoc_reviewer_note",
]
DelegationReferenceClass = Literal[
    "s7_value_authorization_request",
    "s7_value_authorization_record",
    "s7_final_selection_record",
]
ValueDisposition = Literal[
    "authorized",
    "advisory_only",
    "contested_multi_principal",
    "blocked_missing_value_provenance",
    "blocked_mandate_not_pass",
    "blocked_p20_normative_laundering",
    "blocked_p22_mandate_laundering",
    "shadow_scenario_only",
]
RankingMode = Literal[
    "unranked_frontier_only",
    "ranked_with_authorized_values",
    "shadow_scenario_ranking",
    "ranking_blocked",
]
FirewallStatus = Literal["pass", "limit", "block"]
ValueScheduleReviewStatus = Literal[
    "approved",
    "reviewed",
    "pending_review",
    "contested",
    "rejected",
    "scenario_only",
]
Audience = Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

_CREATED_AT = datetime(2026, 6, 1, tzinfo=UTC)
_UNAUTHORIZED_AUTHORITY_SOURCES = frozenset(
    {"llm_candidate", "corpus_derived", "ad_hoc_reviewer_note"}
)
_LLM_SOURCE_CLASSES = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})
_MANDATE_LIMITED_SOURCE_DISPOSITIONS = frozenset(
    {
        "candidate_unverified",
        "consultation_only",
        "evidence_collection_only",
        "workflow_only",
        "budget_planning_only",
        "candidate_exploration_only",
        "limited",
        "blocked",
    }
)
_S8_MAY_NOT_USE_FOR = [
    "production_claim_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "scalar_welfare_authority",
    "preference_learning_authority",
    "mandate_creation",
    "social_weight_selection_without_authorized_schedule",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "s9_projection_maturity",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
]


class P20NormativeChoiceError(ValueError):
    """Raised when S8 detects value-choice or scalar-ranking laundering."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "p20_normative_choice_error",
    ) -> None:
        self.code = code
        super().__init__(message)


def _require_ranked_value_schedule_resolver(ranking_mode: str) -> None:
    if ranking_mode == "ranked_with_authorized_values":
        raise P20NormativeChoiceError(
            f"{P20_VALUE_SCHEDULE_RESOLVER_ABSENT_CODE}: P20 ranked Pareto archive requires "
            "an owner-resolved authorized value schedule; the value schedule resolver is absent",
            code=P20_VALUE_SCHEDULE_RESOLVER_ABSENT_CODE,
        )


class AuthorizedValueSchedule(Layer2ReadinessModel):
    """Mandate-bounded value schedule that may authorize ranking when disposition passes."""

    schema_version: str = LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
    schedule_id: str = Field(..., min_length=1, max_length=160)
    schedule_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    mandate_record_ref: str = Field(..., min_length=1, max_length=300)
    s6_mandate_firewall_disposition: FirewallStatus
    mandate_source_dispositions: list[str] = Field(default_factory=list, max_length=40)
    principal_refs: list[str] = Field(..., min_length=1, max_length=40)
    source_class: ValueSourceClass
    review_status: ValueScheduleReviewStatus
    effective_at: AwareDatetime
    social_weight_provenance_refs: list[str] = Field(default_factory=list, max_length=80)
    delegation_reference_class: DelegationReferenceClass | None = None
    s7_decision_rights_matrix_ref: str | None = Field(default=None, max_length=300)
    s7_value_authorization_request_ref: str | None = Field(default=None, max_length=300)
    s7_value_authorization_record_ref: str | None = Field(default=None, max_length=300)
    s7_value_authorization_decision_class_id: str | None = Field(default=None, max_length=120)
    s7_five_rights_passed: bool | None = None
    disposition: ValueDisposition = "authorized"
    scenario_label: str | None = Field(default=None, max_length=300)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S8_MAY_NOT_USE_FOR))
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    @model_validator(mode="after")
    def _validate_authorized_schedule(self) -> AuthorizedValueSchedule:
        if self.disposition == "authorized":
            if self.s6_mandate_firewall_disposition != "pass":
                raise ValueError("authorized value schedule requires S6 mandate pass")
            if self.source_class in _UNAUTHORIZED_AUTHORITY_SOURCES:
                raise ValueError("unauthorized value source cannot be authorized")
            if "ranked_recommendation_authority" in self.may_not_use_for:
                raise ValueError("authorized schedule cannot deny ranked recommendation authority")
        if self.disposition == "shadow_scenario_only" and (
            "ranked_recommendation_authority" not in self.may_not_use_for
        ):
            self.may_not_use_for.append("ranked_recommendation_authority")
        return self


class ObjectiveFunctionProvenanceRecord(Layer2ReadinessModel):
    """S8 provenance for objectives and proxy/value-loss disclosures used in ranking."""

    schema_version: str = LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=160)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    objective_refs: list[str] = Field(..., min_length=1, max_length=80)
    objective_source_refs: list[str] = Field(default_factory=list, max_length=80)
    value_schedule_ref: str | None = Field(default=None, max_length=300)
    measurability_refs: list[str] = Field(default_factory=list, max_length=80)
    proxy_value_loss_disclosures: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=80,
    )
    mandate_refs: list[str] = Field(default_factory=list, max_length=80)
    p20_firewall_status: FirewallStatus
    p22_firewall_status: FirewallStatus
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class ParetoArchive(Layer2ReadinessModel):
    """Replayable S8 archive separating Pareto facts from ranked value choices."""

    schema_version: str = LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
    archive_id: str = Field(..., min_length=1, max_length=160)
    archive_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    frontier_refs: list[str] = Field(default_factory=list, max_length=80)
    nondominated_alternative_ids: list[str] = Field(default_factory=list, max_length=80)
    rejected_nondominated_alternative_ids: list[str] = Field(
        default_factory=list,
        max_length=80,
    )
    objective_refs: list[str] = Field(default_factory=list, max_length=80)
    value_schedule_ref: str | None = Field(default=None, max_length=300)
    ranking_mode: RankingMode
    archive_status: str = Field(..., min_length=1, max_length=120)
    scenario_value_schedule_refs: list[str] = Field(default_factory=list, max_length=80)
    claim_refs: list[str] = Field(default_factory=list, max_length=80)
    audit_refs: list[str] = Field(default_factory=list, max_length=80)
    authority_boundary: AuthorityBoundary
    may_not_use_for: list[str] = Field(default_factory=lambda: list(_S8_MAY_NOT_USE_FOR))
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT

    @model_validator(mode="after")
    def _validate_ranked_admission(self) -> ParetoArchive:
        _require_ranked_value_schedule_resolver(self.ranking_mode)
        return self


class ValueChoiceProvenanceRecord(Layer2ReadinessModel):
    """S8 record binding selected alternatives to authorized value provenance."""

    schema_version: str = LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
    record_id: str = Field(..., min_length=1, max_length=160)
    record_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    selected_alternative_ref: str | None = Field(default=None, max_length=300)
    objective_provenance_ref: str = Field(..., min_length=1, max_length=300)
    value_schedule_ref: str | None = Field(default=None, max_length=300)
    pareto_archive_ref: str = Field(..., min_length=1, max_length=300)
    social_weight_provenance_refs: list[str] = Field(default_factory=list, max_length=80)
    mandate_refs: list[str] = Field(default_factory=list, max_length=80)
    delegation_refs: list[str] = Field(default_factory=list, max_length=80)
    value_authorization_decision_refs: list[str] = Field(default_factory=list, max_length=80)
    conflict_rows: list[dict[str, object]] = Field(default_factory=list, max_length=80)
    affected_group_rows: list[dict[str, object]] = Field(default_factory=list, max_length=80)
    dissent_refs: list[str] = Field(default_factory=list, max_length=80)
    blocking_rights_refs: list[str] = Field(default_factory=list, max_length=80)
    alternative_schedule_sensitivity_rows: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=80,
    )
    disposition: ValueDisposition
    integrity_status: FirewallStatus
    replay_refs: list[str] = Field(default_factory=list, max_length=120)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class ValueTradeoffDisclosureRecord(Layer2ReadinessModel):
    """Audience-bounded projection of value tradeoffs without scalar authority."""

    schema_version: str = LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
    disclosure_id: str = Field(..., min_length=1, max_length=160)
    disclosure_ref: str = Field(..., min_length=1, max_length=300)
    case_id: str = Field(..., min_length=1, max_length=200)
    audience: Audience
    decision_tradeoff_summary: str = Field(..., min_length=1, max_length=800)
    value_schedule_ref: str | None = Field(default=None, max_length=300)
    objective_provenance_ref: str | None = Field(default=None, max_length=300)
    pareto_archive_ref: str | None = Field(default=None, max_length=300)
    value_choice_provenance_ref: str | None = Field(default=None, max_length=300)
    reviewer_status_fields: dict[str, object] = Field(default_factory=dict)
    expert_refs: list[str] = Field(default_factory=list, max_length=120)
    machine_integrity_fields: dict[str, object] = Field(default_factory=dict)
    conflict_rows: list[dict[str, object]] = Field(default_factory=list, max_length=80)
    affected_group_rows: list[dict[str, object]] = Field(default_factory=list, max_length=80)
    dissent_refs: list[str] = Field(default_factory=list, max_length=80)
    blocking_rights_refs: list[str] = Field(default_factory=list, max_length=80)
    alternative_schedule_sensitivity: list[dict[str, object]] = Field(
        default_factory=list,
        max_length=80,
    )
    projection_authority_boundary: AuthorityBoundary
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


class ValueChoiceIntegrityReport(Layer2ReadinessModel):
    """Completeness and false-clear report for the S8 value-provenance floor."""

    schema_version: str = LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION
    report_id: str = Field(..., min_length=1, max_length=160)
    report_ref: str = Field(..., min_length=1, max_length=300)
    completeness_denominator: int = Field(ge=0)
    completeness_numerator: int = Field(ge=0)
    value_provenance_completeness: float = Field(ge=0.0, le=1.0)
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    negative_control_results: dict[str, object] = Field(default_factory=dict)
    case_count: int = Field(ge=0)
    floor_id: Literal["s8_value_provenance"] = S8_VALUE_CHOICE_FLOOR_ID
    metric_name: Literal["value_provenance_completeness"] = "value_provenance_completeness"
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    created_at: AwareDatetime = _CREATED_AT


def coerce_social_weight_provenance_for_s8(
    provenance: Mapping[str, object] | object,
    *,
    authority_required: bool,
    rule_version_ref: str,
) -> dict[str, object]:
    """Normalize foundry or mapping social-weight provenance for S8 use."""

    payload = _model_payload(provenance)
    source_class = str(payload.get("source_class", ""))
    if authority_required and (
        source_class in _UNAUTHORIZED_AUTHORITY_SOURCES or source_class in _LLM_SOURCE_CLASSES
    ):
        raise P20NormativeChoiceError(
            f"P20 value authority requires authorized social weights, got {source_class!r}"
        )
    if authority_required and payload.get("review_status") in {"rejected", "superseded"}:
        raise P20NormativeChoiceError(
            "P20 value authority requires active social-weight provenance"
        )
    payload.setdefault(
        "authority_boundary",
        _authority_boundary(
            rule_version_ref,
            authoritative_for=["social_weight_provenance_advisory_disclosure"],
            posture="advisory" if not authority_required else "governed",
        ).model_dump(mode="json"),
    )
    return payload


def build_authorized_value_schedule(
    *,
    schedule_id: str,
    schedule_ref: str,
    case_id: str,
    mandate_record_ref: str | None,
    s6_mandate_firewall_disposition: str | None,
    principal_refs: Sequence[str],
    source_class: str,
    review_status: str,
    effective_at: AwareDatetime | str,
    social_weight_provenance_refs: Sequence[str] = (),
    authority_boundary: AuthorityBoundary | Mapping[str, object],
    may_not_use_for: Sequence[str] = (),
    rule_version_ref: str,
    mandate_source_dispositions: Sequence[str] = (),
    delegation_reference_class: str | None = None,
    s7_decision_rights_matrix_ref: str | None = None,
    s7_value_authorization_request_ref: str | None = None,
    s7_value_authorization_record_ref: str | None = None,
    s7_value_authorization_decision_class_id: str | None = None,
    s7_five_rights_passed: bool | None = None,
    **_: object,
) -> AuthorizedValueSchedule:
    """Build an authorized S8 value schedule or fail closed on P20/P22/P26."""

    _require_mandate_pass(
        mandate_record_ref=mandate_record_ref,
        s6_mandate_firewall_disposition=s6_mandate_firewall_disposition,
        mandate_source_dispositions=mandate_source_dispositions,
    )
    _require_authorized_source(source_class)
    _validate_s7_value_authorization_refs(
        decision_class_id=s7_value_authorization_decision_class_id,
        five_rights_passed=s7_five_rights_passed,
        request_ref=s7_value_authorization_request_ref,
        record_ref=s7_value_authorization_record_ref,
    )
    return AuthorizedValueSchedule(
        schedule_id=schedule_id,
        schedule_ref=schedule_ref,
        case_id=case_id,
        mandate_record_ref=str(mandate_record_ref),
        s6_mandate_firewall_disposition="pass",
        mandate_source_dispositions=[str(item) for item in mandate_source_dispositions],
        principal_refs=[str(ref) for ref in principal_refs],
        source_class=source_class,  # type: ignore[arg-type]
        review_status=review_status,  # type: ignore[arg-type]
        effective_at=_aware_datetime(effective_at),
        social_weight_provenance_refs=[str(ref) for ref in social_weight_provenance_refs],
        delegation_reference_class=delegation_reference_class,  # type: ignore[arg-type]
        s7_decision_rights_matrix_ref=s7_decision_rights_matrix_ref,
        s7_value_authorization_request_ref=s7_value_authorization_request_ref,
        s7_value_authorization_record_ref=s7_value_authorization_record_ref,
        s7_value_authorization_decision_class_id=s7_value_authorization_decision_class_id,
        s7_five_rights_passed=s7_five_rights_passed,
        disposition="authorized",
        authority_boundary=_as_authority_boundary(authority_boundary),
        may_not_use_for=list(may_not_use_for) or _authorized_may_not_use_for(),
        rule_version_ref=rule_version_ref,
    )


def build_shadow_scenario_value_schedule(
    *,
    schedule_ref: str,
    case_id: str,
    principal_refs: Sequence[str],
    social_weight_provenance_refs: Sequence[str],
    scenario_label: str,
    rule_version_ref: str,
) -> AuthorizedValueSchedule:
    """Build a non-authoritative scenario schedule for sensitivity analysis."""

    slug = _slug(schedule_ref.rsplit("/", 1)[-1] or case_id)
    return AuthorizedValueSchedule(
        schedule_id=f"layer2.s8.shadow_schedule.{slug}",
        schedule_ref=schedule_ref,
        case_id=case_id,
        mandate_record_ref=f"{schedule_ref}/mandate-not-authority",
        s6_mandate_firewall_disposition="limit",
        mandate_source_dispositions=["scenario_only"],
        principal_refs=[str(ref) for ref in principal_refs],
        source_class="foundry_social_weight_provenance",
        review_status="scenario_only",
        effective_at=_CREATED_AT,
        social_weight_provenance_refs=[str(ref) for ref in social_weight_provenance_refs],
        disposition="shadow_scenario_only",
        scenario_label=scenario_label,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=["shadow_scenario_value_schedule"],
            posture="shadow",
        ),
        may_not_use_for=[*_S8_MAY_NOT_USE_FOR, "ranked_recommendation_authority"],
        rule_version_ref=rule_version_ref,
    )


def build_objective_function_provenance(
    **payload: object,
) -> ObjectiveFunctionProvenanceRecord:
    """Build S8 objective-function provenance for value-bound objectives."""

    if not payload.get("objective_refs"):
        raise P20NormativeChoiceError("P20 objective provenance requires objective refs")
    return ObjectiveFunctionProvenanceRecord.model_validate(payload)


def build_pareto_archive(
    *,
    archive_id: str,
    archive_ref: str,
    case_id: str,
    ranking_mode: str,
    archive_status: str,
    value_schedule_ref: str | None = None,
    frontier_refs: Sequence[str] = (),
    nondominated_alternative_ids: Sequence[str] = (),
    rejected_nondominated_alternative_ids: Sequence[str] = (),
    objective_refs: Sequence[str] = (),
    scenario_value_schedule_refs: Sequence[str] = (),
    claim_refs: Sequence[str] = (),
    audit_refs: Sequence[str] = (),
    authority_boundary: AuthorityBoundary | Mapping[str, object],
    may_not_use_for: Sequence[str] = (),
    rule_version_ref: str,
    foundry_emission: Mapping[str, object] | object | None = None,
    frontier_record: Mapping[str, object] | object | None = None,
    **_: object,
) -> ParetoArchive:
    """Build a Pareto archive while blocking hidden ranked value choices."""

    _require_ranked_value_schedule_resolver(ranking_mode)
    mapped = _frontier_payload(foundry_emission=foundry_emission, frontier_record=frontier_record)
    frontier_refs = list(frontier_refs) or mapped["frontier_refs"]
    nondominated_alternative_ids = (
        list(nondominated_alternative_ids) or mapped["nondominated_alternative_ids"]
    )
    objective_refs = list(objective_refs) or mapped["objective_refs"]
    claim_refs = list(claim_refs) or mapped["claim_refs"]
    audit_refs = list(audit_refs) or mapped["audit_refs"]
    return ParetoArchive(
        archive_id=archive_id,
        archive_ref=archive_ref,
        case_id=case_id,
        frontier_refs=[str(ref) for ref in frontier_refs],
        nondominated_alternative_ids=[str(item) for item in nondominated_alternative_ids],
        rejected_nondominated_alternative_ids=[
            str(item) for item in rejected_nondominated_alternative_ids
        ],
        objective_refs=[str(ref) for ref in objective_refs],
        value_schedule_ref=value_schedule_ref,
        ranking_mode=ranking_mode,  # type: ignore[arg-type]
        archive_status=archive_status,
        scenario_value_schedule_refs=[str(ref) for ref in scenario_value_schedule_refs],
        claim_refs=[str(ref) for ref in claim_refs],
        audit_refs=[str(ref) for ref in audit_refs],
        authority_boundary=_as_authority_boundary(authority_boundary),
        may_not_use_for=list(may_not_use_for) or list(_S8_MAY_NOT_USE_FOR),
        rule_version_ref=rule_version_ref,
    )


def build_value_choice_provenance_record(
    **payload: object,
) -> ValueChoiceProvenanceRecord:
    """Build S8 value-choice provenance and expose contested conflicts explicitly."""

    value_schedule_ref = payload.get("value_schedule_ref")
    disposition = str(payload.get("disposition") or "")
    if not value_schedule_ref and disposition == "authorized":
        if payload.get("delegation_refs") or payload.get("value_authorization_decision_refs"):
            raise P20NormativeChoiceError(
                "P20 S7 decision refs cannot substitute for S8 value authority"
            )
        raise P20NormativeChoiceError("P20 authorized value choice requires value schedule")
    conflict_rows = list(_sequence(payload.get("conflict_rows")))
    if conflict_rows:
        _require_arrow_disclosure_rows(payload)
        payload = {**payload, "disposition": "contested_multi_principal"}
    return ValueChoiceProvenanceRecord.model_validate(payload)


def project_value_tradeoff_disclosure(
    *,
    value_choice_record: ValueChoiceProvenanceRecord | Mapping[str, object],
    audience: str,
    rule_version_ref: str,
) -> ValueTradeoffDisclosureRecord:
    """Project value-choice tradeoffs for one audience without scalar authority."""

    record = (
        value_choice_record
        if isinstance(value_choice_record, ValueChoiceProvenanceRecord)
        else ValueChoiceProvenanceRecord.model_validate(value_choice_record)
    )
    upper_audience = audience.upper()
    value_schedule_ref = record.value_schedule_ref if upper_audience != "PUBLIC" else None
    expert_refs = [
        ref
        for ref in [
            record.value_schedule_ref,
            record.objective_provenance_ref,
            record.pareto_archive_ref,
            *record.social_weight_provenance_refs,
            *record.mandate_refs,
            *record.delegation_refs,
        ]
        if ref
    ]
    return ValueTradeoffDisclosureRecord(
        disclosure_id=f"layer2.s8.disclosure.{_slug(record.case_id)}.{upper_audience.lower()}",
        disclosure_ref=(
            f"pdc://layer2/s8/{_slug(record.case_id)}/value-tradeoff-disclosure/"
            f"{upper_audience.lower()}"
        ),
        case_id=record.case_id,
        audience=upper_audience,  # type: ignore[arg-type]
        decision_tradeoff_summary=_tradeoff_summary(record, upper_audience),
        value_schedule_ref=value_schedule_ref,
        objective_provenance_ref=(
            record.objective_provenance_ref if upper_audience in {"EXPERT", "MACHINE"} else None
        ),
        pareto_archive_ref=(
            record.pareto_archive_ref if upper_audience in {"EXPERT", "MACHINE"} else None
        ),
        value_choice_provenance_ref=(
            record.record_ref if upper_audience in {"EXPERT", "MACHINE"} else None
        ),
        reviewer_status_fields=_reviewer_fields(record) if upper_audience == "REVIEWER" else {},
        expert_refs=expert_refs if upper_audience in {"EXPERT", "MACHINE"} else [],
        machine_integrity_fields=(
            _machine_integrity_fields(record) if upper_audience == "MACHINE" else {}
        ),
        conflict_rows=record.conflict_rows if upper_audience in {"EXPERT", "MACHINE"} else [],
        affected_group_rows=record.affected_group_rows,
        dissent_refs=record.dissent_refs,
        blocking_rights_refs=record.blocking_rights_refs,
        alternative_schedule_sensitivity=record.alternative_schedule_sensitivity_rows
        if upper_audience in {"EXPERT", "MACHINE"}
        else [],
        projection_authority_boundary=_projection_boundary(rule_version_ref),
        authority_boundary=_projection_boundary(rule_version_ref),
        rule_version_ref=rule_version_ref,
    )


def s8_value_provenance_integrity(
    rows: Sequence[Mapping[str, object]],
    *,
    rule_version_ref: str = LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
) -> ValueChoiceIntegrityReport:
    """Compute S8 completeness and false-clear metrics from case/probe rows."""

    denominator = len(rows)
    numerator = sum(1 for row in rows if _row_has_value_provenance(row))
    false_clear_counts = {
        "llm_weight_false_clear_count": _false_clear_count(rows, "llm"),
        "corpus_weight_false_clear_count": _false_clear_count(rows, "corpus"),
        "blocked_mandate_value_choice_false_clear_count": _false_clear_count(rows, "mandate"),
        "pareto_ranking_without_value_source_false_clear_count": _false_clear_count(
            rows,
            "pareto",
        ),
        "multi_principal_silent_average_false_clear_count": _false_clear_count(
            rows,
            "multi_principal",
        ),
        "s7_decision_substitution_false_clear_count": _false_clear_count(rows, "s7"),
        "shadow_scenario_authority_false_clear_count": _false_clear_count(rows, "shadow"),
        "missing_arrow_disclosure_false_clear_count": _false_clear_count(rows, "arrow"),
    }
    return ValueChoiceIntegrityReport(
        report_id="layer2.s8.value_choice_integrity",
        report_ref="pdc://layer2/s8/value-choice-integrity",
        completeness_denominator=denominator,
        completeness_numerator=numerator,
        value_provenance_completeness=1.0 if denominator == 0 else numerator / denominator,
        false_clear_counts=false_clear_counts,
        negative_control_results={
            str(row.get("case_id")): dict(row)
            for row in rows
            if str(row.get("case_id", "")).endswith("_probe")
        },
        case_count=denominator,
        authority_boundary=_authority_boundary(
            rule_version_ref,
            authoritative_for=["value_choice_integrity_report"],
        ),
        rule_version_ref=rule_version_ref,
    )


def persist_value_choice_provenance_bundle(
    bundle: Mapping[str, object],
    *,
    store: artifacts.FileSystemCAS | None = None,
    rule_version_ref: str = LAYER2_S8_VALUE_CHOICE_RULE_VERSION,
) -> dict[str, object]:
    """Persist an S8 bundle through CAS or return deterministic replay refs."""

    payload = dict(bundle)
    if store is None:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "bundle_ref": f"pdc://layer2/s8/value-choice-bundle/sha256:{digest}",
            "artifact_ref": f"sha256:{digest}",
            "rule_version_ref": rule_version_ref,
        }
    ref = store.put_json(
        payload,
        artifacts.PutOptions(
            kind="policyos.layer2_s8.value_choice_bundle",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s8.value_choice_bundle",
                version=LAYER2_S8_VALUE_CHOICE_SCHEMA_VERSION,
            ),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.quality.design_axes.value_choice_provenance",
                version=rule_version_ref,
            ),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    return {
        "bundle_ref": ref,
        "artifact_ref": ref.artifact_id,
        "rule_version_ref": rule_version_ref,
    }


def _require_mandate_pass(
    *,
    mandate_record_ref: str | None,
    s6_mandate_firewall_disposition: str | None,
    mandate_source_dispositions: Sequence[str],
) -> None:
    if not mandate_record_ref:
        raise P22MandateLegitimacyError("P22 mandate record ref is required")
    if s6_mandate_firewall_disposition != "pass":
        raise P22MandateLegitimacyError(
            f"P22 mandate firewall must pass, got {s6_mandate_firewall_disposition!r}"
        )
    limited_sources = {str(item) for item in mandate_source_dispositions}
    blocked = limited_sources & _MANDATE_LIMITED_SOURCE_DISPOSITIONS
    if blocked:
        raise P22MandateLegitimacyError(
            f"P22 candidate_unverified mandate source cannot authorize values: {sorted(blocked)}"
        )


def _require_authorized_source(source_class: str) -> None:
    if source_class in _UNAUTHORIZED_AUTHORITY_SOURCES:
        raise P20NormativeChoiceError(f"P20 unauthorized value source: {source_class}")
    if source_class.startswith("s7_"):
        raise P20NormativeChoiceError("P20 S7 refs are routing refs, not value-source authority")


def _validate_s7_value_authorization_refs(
    *,
    decision_class_id: str | None,
    five_rights_passed: bool | None,
    request_ref: str | None,
    record_ref: str | None,
) -> None:
    if not any([decision_class_id, five_rights_passed is not None, request_ref, record_ref]):
        return
    if decision_class_id != "value_authorization":
        raise P26ResponsibilityIntegrityError("value_authorization decision class required")
    if five_rights_passed is not True:
        raise P26ResponsibilityIntegrityError("value_authorization five_rights_required")


def _require_arrow_disclosure_rows(payload: Mapping[str, object]) -> None:
    required = {
        "affected_group_rows": list(_sequence(payload.get("affected_group_rows"))),
        "dissent_refs": list(_sequence(payload.get("dissent_refs"))),
        "blocking_rights_refs": list(_sequence(payload.get("blocking_rights_refs"))),
        "alternative_schedule_sensitivity_rows": list(
            _sequence(payload.get("alternative_schedule_sensitivity_rows"))
        ),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise P20NormativeChoiceError(
            "P20 multi-principal conflict requires affected groups, dissent, "
            f"blocking rights, and sensitivity rows; missing {missing}"
        )


def _frontier_payload(
    *,
    foundry_emission: Mapping[str, object] | object | None,
    frontier_record: Mapping[str, object] | object | None,
) -> dict[str, list[str]]:
    frontier: Mapping[str, object] | object | None = frontier_record
    if foundry_emission is not None:
        emission_payload = _model_payload(foundry_emission)
        frontier = emission_payload.get("frontier") or getattr(
            foundry_emission,
            "frontier",
            None,
        )
    if frontier is None:
        return {
            "frontier_refs": [],
            "nondominated_alternative_ids": [],
            "objective_refs": [],
            "claim_refs": [],
            "audit_refs": [],
        }
    payload = _model_payload(frontier)
    objective_specs = _sequence_of_mappings(payload.get("objective_specs"))
    return {
        "frontier_refs": [str(payload.get("frontier_id"))] if payload.get("frontier_id") else [],
        "nondominated_alternative_ids": [
            str(item) for item in _sequence(payload.get("frontier_alternative_ids"))
        ],
        "objective_refs": [
            str(row.get("objective_id")) for row in objective_specs if row.get("objective_id")
        ],
        "claim_refs": [str(ref) for ref in _sequence(payload.get("claim_refs"))],
        "audit_refs": [str(ref) for ref in _sequence(payload.get("welfare_bound_refs"))],
    }


def _authority_boundary(
    rule_version_ref: str,
    *,
    authoritative_for: Sequence[str],
    posture: Literal["shadow", "advisory", "governed"] = "governed",
) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[str(item) for item in authoritative_for],
        may_not_use_for=list(_S8_MAY_NOT_USE_FOR),
        source_authority="deterministic_producer",
        posture=posture,
        rule_version_refs=[rule_version_ref],
    )


def _projection_boundary(rule_version_ref: str) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["value_tradeoff_disclosure_projection"],
        may_not_use_for=[
            "production_recommendation",
            "claim_authority",
            "scalar_welfare_authority",
            "preference_learning_authority",
            "mandate_creation",
        ],
        source_authority="deterministic_producer",
        posture="shadow",
        rule_version_refs=[rule_version_ref],
    )


def _as_authority_boundary(value: AuthorityBoundary | Mapping[str, object]) -> AuthorityBoundary:
    if isinstance(value, AuthorityBoundary):
        return value
    return AuthorityBoundary.model_validate(value)


def _model_payload(value: Mapping[str, object] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[no-any-return, attr-defined]
    raise TypeError(f"expected mapping-like payload, got {type(value).__name__}")


def _authorized_may_not_use_for() -> list[str]:
    return [
        item
        for item in _S8_MAY_NOT_USE_FOR
        if item not in {"social_weight_selection_without_authorized_schedule"}
    ]


def _aware_datetime(value: AwareDatetime | str) -> AwareDatetime:
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _tradeoff_summary(record: ValueChoiceProvenanceRecord, audience: str) -> str:
    if record.disposition == "authorized":
        return "Ranked frontier selection is tied to an authorized value schedule."
    if record.disposition == "contested_multi_principal":
        return "Frontier tradeoff is contested across principals and is not silently averaged."
    if audience == "PUBLIC":
        return "Frontier facts are visible; ranking depends on authorized value provenance."
    return f"S8 value-choice disposition: {record.disposition}."


def _reviewer_fields(record: ValueChoiceProvenanceRecord) -> dict[str, object]:
    return {
        "s8_value_disposition": record.disposition,
        "p20_firewall_status": "pass" if record.disposition == "authorized" else "limit",
        "p22_firewall_status": "pass" if record.mandate_refs else "block",
        "p12_firewall_status": "pass" if record.replay_refs else "limit",
        "p15_firewall_status": "pass",
        "p26_firewall_status": "pass" if record.delegation_refs else "limit",
    }


def _machine_integrity_fields(record: ValueChoiceProvenanceRecord) -> dict[str, object]:
    return {
        "integrity_status": record.integrity_status,
        "replay_refs": list(record.replay_refs),
        "authority_boundary": record.authority_boundary.model_dump(mode="json"),
    }


def _row_has_value_provenance(row: Mapping[str, object]) -> bool:
    if str(row.get("ranking_mode")) == "ranked_with_authorized_values":
        return (
            bool(row.get("authorized_value_schedule_ref"))
            and row.get("p20_firewall_status") == "pass"
        )
    return True


def _false_clear_count(rows: Sequence[Mapping[str, object]], probe_key: str) -> int:
    return sum(
        1
        for row in rows
        if probe_key in str(row.get("case_id", ""))
        and bool(row.get("negative_control_false_clear") or row.get("false_clear"))
    )


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _sequence_of_mappings(value: object) -> list[Mapping[str, object]]:
    return [item for item in _sequence(value) if isinstance(item, dict)]


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
