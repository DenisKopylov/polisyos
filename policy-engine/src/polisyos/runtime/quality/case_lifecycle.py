"""Policy Design Case lifecycle, ex-post outcome, and calibration contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.runtime.quality.ddm_monitoring import (
    ImplementationMonitoringEvaluationError,
    validate_implementation_monitoring_evaluation_record,
)
from polisyos.scientist.orchestration.memory.contamination import (
    MemoryContaminationPolicy,
    detect_memory_contamination,
)

CASE_LIFECYCLE_SCHEMA_VERSION = "policyos.runtime.policy_design_case.case_lifecycle.v1"
CASE_LIFECYCLE_CONTRACT_ID = "policy_design_case.case_lifecycle.v1"
EX_POST_LEARNING_SCHEMA_VERSION = "policyos.runtime.policy_design_case.ex_post_learning.v1"
EX_POST_LEARNING_CONTRACT_ID = "policy_design_case.ex_post_learning.v1"
LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
)
LIFECYCLE_REISSUE_CONTRACT_ID = "policy_design_case.lifecycle_reissue_report.v1"
PUBLIC_REVISION_STATE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.public_revision_state.v1"
)
RULE_EVOLUTION_PUBLIC_POLICY_ADR_BLOCKER = "ADR-TBD-rule-evolution-public-revalidation"

GOVERNED_LIFECYCLE_PROFILES = frozenset({"governed", "production"})
ALLOWED_LIFECYCLE_EVENTS = frozenset(
    {
        "draft",
        "ready_for_review",
        "approved",
        "published",
        "amended",
        "superseded",
        "withdrawn",
        "recalled",
        "retracted",
        "stale",
        "contested",
        "ex_post_under_review",
        "confirmed",
        "refuted",
        "inconclusive",
        "reissue",
    }
)
RESOLUTION_LIFECYCLE_EVENTS = frozenset(
    {
        "amended",
        "superseded",
        "withdrawn",
        "recalled",
        "retracted",
        "confirmed",
        "refuted",
        "inconclusive",
        "reissue",
    }
)
REASSESSMENT_STATUSES = frozenset(
    {"confirmed", "refuted", "superseded", "inconclusive", "accepted_data_deficit"}
)
REVISION_ACTION_ORDER = {
    "none": 0,
    "review_required": 1,
    "partial_reissue": 2,
    "supersede": 3,
    "withdraw": 4,
}
_SHA256_REF_RE = re.compile(r"^(?:sha256:|cas://sha256/)[0-9a-f]{64}$", re.IGNORECASE)

COMMITMENT_PROFILE_SCHEMA_VERSION = "policyos.runtime.policy_design_case.commitment_profile.v1"
Reversibility = Literal[
    "reversible",
    "pilotable",
    "option_preserving",
    "lock_in",
    "irreversible",
]
LifecycleStage = Literal[
    "greenfield",
    "reform",
    "transition",
    "termination",
    "grandfathering",
    "emergency",
    "recovery",
]
StakesBand = Literal["low", "high", "catastrophic"]
FloorBand = Literal["low_stakes", "standard", "high_stakes"]

_HARD_COMMITMENT = frozenset({"lock_in", "irreversible"})
_DOMAIN_COMMITMENT_BASELINE: dict[str, tuple[Reversibility, StakesBand, LifecycleStage]] = {
    "climate_adaptation": ("irreversible", "catastrophic", "transition"),
    "digital_public_service": ("lock_in", "catastrophic", "reform"),
    "housing_rent_control": ("lock_in", "high", "reform"),
    "education_access": ("lock_in", "high", "reform"),
    "infrastructure_prioritisation": ("irreversible", "high", "reform"),
    "public_health_intervention": ("reversible", "high", "reform"),
    "public_safety": ("reversible", "high", "reform"),
    "tax_enforcement": ("reversible", "high", "reform"),
    "labour_activation": ("reversible", "high", "reform"),
    "social_protection_targeting": ("pilotable", "high", "emergency"),
    "migration_displacement": ("pilotable", "high", "emergency"),
    "msme_credit_grant": ("pilotable", "high", "emergency"),
}
_DEFAULT_COMMITMENT: tuple[Reversibility, StakesBand, LifecycleStage] = (
    "irreversible",
    "high",
    "transition",
)
_EMERGENCY_TIME_HINTS = ("emergency", "2020", "2022")
_LIFECYCLE_STAGE_EVENT_ANCHORS: dict[str, frozenset[str]] = {
    "transition": frozenset({"amended", "superseded", "reissue"}),
    "termination": frozenset({"withdrawn", "retracted", "superseded"}),
    "grandfathering": frozenset({"amended", "superseded", "reissue"}),
}


class CommitmentProfileRecord(BaseModel):
    """Reversibility, lifecycle, transition-cost, and stakes for a design candidate."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.runtime.policy_design_case.commitment_profile.v1"] = (
        COMMITMENT_PROFILE_SCHEMA_VERSION
    )
    candidate_ref: str = Field(min_length=1)
    reversibility: Reversibility
    option_value: Literal["none", "low", "medium", "high"]
    lifecycle_stage: LifecycleStage
    transition_cost: Literal["low", "medium", "high"]
    stakes: StakesBand
    rule_version_ref: str = Field(min_length=1)

    @property
    def is_high_commitment(self) -> bool:
        """Return whether this profile requires elevated floors."""

        return self.reversibility in _HARD_COMMITMENT and self.stakes in {
            "high",
            "catastrophic",
        }

    @model_validator(mode="after")
    def _lifecycle_stage_reuses_lifecycle_events(self) -> CommitmentProfileRecord:
        anchor_events = _LIFECYCLE_STAGE_EVENT_ANCHORS.get(self.lifecycle_stage)
        if anchor_events and not anchor_events <= ALLOWED_LIFECYCLE_EVENTS:
            raise ValueError("commitment lifecycle stage is not anchored in lifecycle events")
        return self


class P23StakesFloorError(ValueError):
    """Raised when a low-stakes floor is applied to a hard high-stakes commitment."""


@dataclass(frozen=True)
class PolicyDesignLifecycleError(ValueError):
    """Fail-closed lifecycle/ex-post/calibration contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class PolicyDesignLifecycleIssue:
    """Scorecard-readable lifecycle validation issue."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None
    affected_claim: str | None = None
    next_action: str = (
        "Emit Phase 27.2 lifecycle, DDM monitoring, ex-post, and calibration "
        "records from runtime quality before publication closeout."
    )

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
            "affected_claim": self.affected_claim,
            "next_action": self.next_action,
        }


def build_commitment_profile(
    *,
    candidate_ref: str,
    rule_version_ref: str,
    domain: str | None = None,
    instrument_type: str | None = None,
    policy_time: str | None = None,
    annotation: dict[str, str] | None = None,
    **overrides: str,
) -> CommitmentProfileRecord:
    """Derive a commitment profile from case signals.

    Explicit annotation and keyword overrides win over deterministic domain and
    time heuristics. Unknown domains default conservatively to a hard, high-stakes
    transition profile, matching S4's "default toward more uncertainty" posture.

    Args:
        candidate_ref: Stable candidate identifier.
        rule_version_ref: Rule or ADR reference used for replay.
        domain: Policy domain signal from the case.
        instrument_type: Optional instrument signal reserved for later refinement.
        policy_time: Policy-time hint; crisis years lean emergency when otherwise unknown.
        annotation: Expert/gold annotation that overrides derived fields.
        **overrides: Field-level overrides for tests or explicitly recorded signals.

    Returns:
        Strict commitment profile record consumed by regime and floor selection.
    """

    del instrument_type
    reversibility, stakes, lifecycle_stage = _DOMAIN_COMMITMENT_BASELINE.get(
        domain or "",
        _DEFAULT_COMMITMENT,
    )
    if (
        policy_time
        and any(hint in policy_time for hint in _EMERGENCY_TIME_HINTS)
        and lifecycle_stage == "transition"
    ):
        lifecycle_stage = "emergency"

    fields: dict[str, str] = {
        "candidate_ref": candidate_ref,
        "reversibility": reversibility,
        "option_value": "low" if reversibility in _HARD_COMMITMENT else "medium",
        "lifecycle_stage": lifecycle_stage,
        "transition_cost": "high" if reversibility in _HARD_COMMITMENT else "medium",
        "stakes": stakes,
        "rule_version_ref": rule_version_ref,
    }
    fields.update({key: value for key, value in (annotation or {}).items() if key in fields})
    fields.update(overrides)
    return CommitmentProfileRecord(**fields)  # type: ignore[arg-type]


def select_floor(profile: CommitmentProfileRecord) -> FloorBand:
    """Select the floor band required by a commitment profile."""

    if profile.stakes == "catastrophic" or profile.is_high_commitment:
        return "high_stakes"
    if profile.stakes == "high":
        return "standard"
    return "low_stakes"


def assert_stakes_floor_consistency(
    profile: CommitmentProfileRecord,
    *,
    selected_floor: str,
) -> None:
    """Fail closed when P23 would launder a low-stakes floor into a hard commitment."""

    if (
        profile.stakes == "catastrophic"
        and profile.reversibility in _HARD_COMMITMENT
        and selected_floor == "low_stakes"
    ):
        raise P23StakesFloorError(
            "low-stakes floor cannot be applied to a catastrophic irreversible commitment (P23)"
        )


def build_case_lifecycle_record(
    *,
    ledger_id: str,
    case_id: str,
    current_state: str,
    events: Iterable[Mapping[str, Any]],
    continuous_governance_reports: Mapping[str, str],
    resolution_event_refs: Iterable[str] = (),
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    """Build an append-only lifecycle ledger for a governed Policy Design Case."""

    payload = {
        "schema_version": CASE_LIFECYCLE_SCHEMA_VERSION,
        "contract_id": CASE_LIFECYCLE_CONTRACT_ID,
        "ledger_id": ledger_id,
        "case_id": case_id,
        "current_state": current_state,
        "events": [dict(event) for event in events],
        "continuous_governance_reports": dict(continuous_governance_reports),
        "resolution_event_refs": list(resolution_event_refs),
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }
    return validate_case_lifecycle_record(payload)


def validate_case_lifecycle_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate append-only lifecycle semantics for published/governed cases."""

    if not isinstance(record, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_missing",
            "Policy Design Case lifecycle record must be a mapping.",
            "case_lifecycle",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_case_lifecycle_schema_version_missing",
    )
    if schema_version != CASE_LIFECYCLE_SCHEMA_VERSION:
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_schema_version_invalid",
            "Case lifecycle record must use the Phase 27.2 schema.",
            "schema_version",
        )
    normalized["schema_version"] = CASE_LIFECYCLE_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or CASE_LIFECYCLE_CONTRACT_ID
    normalized["ledger_id"] = _required_text(
        record.get("ledger_id") or record.get("record_id") or record.get("id"),
        "ledger_id",
        "policy_design_case_lifecycle_id_missing",
    )
    normalized["case_id"] = _required_text(
        record.get("case_id"),
        "case_id",
        "policy_design_case_lifecycle_case_id_missing",
    )
    current_state = _required_text(
        record.get("current_state") or record.get("state"),
        "current_state",
        "policy_design_case_lifecycle_state_missing",
    )
    normalized["current_state"] = current_state
    events = [_validate_lifecycle_event(event) for event in _mapping_rows(record.get("events"))]
    if not events:
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_event_missing",
            "Case lifecycle ledger must include append-only lifecycle events.",
            "events",
        )
    normalized["events"] = events
    reports = _continuous_governance_reports(record.get("continuous_governance_reports"))
    normalized["continuous_governance_reports"] = reports
    resolution_refs = _text_values(record.get("resolution_event_refs"))
    normalized["resolution_event_refs"] = resolution_refs
    _reject_historical_rewrite(record, events)
    if _state_is_stale(current_state, events) and not _has_stale_resolution(
        events,
        resolution_refs,
    ):
        raise PolicyDesignLifecycleError(
            "policy_design_published_case_stale",
            (
                "Published Policy Design Case is stale without reissue, supersession, "
                "withdrawal, or ex-post reassessment resolution."
            ),
            "case_lifecycle.current_state",
        )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_case_lifecycle_runtime_ref_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_case_lifecycle_runtime_event_missing",
    )
    return normalized


def build_ex_post_learning_record(
    *,
    record_id: str,
    case_id: str,
    claim_prediction_links: Iterable[Mapping[str, Any]],
    calibration: Mapping[str, Any],
    memory_contamination_check: Mapping[str, Any],
    learning_records: Iterable[Mapping[str, Any]],
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    """Build ex-post learning evidence without rewriting publication authority."""

    payload = {
        "schema_version": EX_POST_LEARNING_SCHEMA_VERSION,
        "contract_id": EX_POST_LEARNING_CONTRACT_ID,
        "record_id": record_id,
        "case_id": case_id,
        "claim_prediction_links": [dict(link) for link in claim_prediction_links],
        "calibration": dict(calibration),
        "memory_contamination_check": dict(memory_contamination_check),
        "learning_records": [dict(record) for record in learning_records],
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }
    return validate_ex_post_learning_record(payload)


def validate_ex_post_learning_record(
    record: Mapping[str, Any],
    *,
    required_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate ex-post outcome links, calibration, and clean reusable learning."""

    if not isinstance(record, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_learning_missing",
            "Ex-post learning record must be a mapping.",
            "ex_post_learning",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_ex_post_learning_schema_version_missing",
    )
    if schema_version != EX_POST_LEARNING_SCHEMA_VERSION:
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_learning_schema_version_invalid",
            "Ex-post learning record must use the Phase 27.2 schema.",
            "schema_version",
        )
    normalized["schema_version"] = EX_POST_LEARNING_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or EX_POST_LEARNING_CONTRACT_ID
    normalized["record_id"] = _required_text(
        record.get("record_id") or record.get("id"),
        "record_id",
        "policy_design_ex_post_learning_id_missing",
    )
    normalized["case_id"] = _required_text(
        record.get("case_id"),
        "case_id",
        "policy_design_ex_post_learning_case_id_missing",
    )
    links = [
        _validate_prediction_outcome_link(link)
        for link in _mapping_rows(
            record.get("claim_prediction_links") or record.get("outcome_links")
        )
    ]
    if not links:
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_outcome_link_missing",
            "Ex-post learning must link claim predictions to observed outcomes.",
            "claim_prediction_links",
        )
    missing_claims = set(_text_values(required_claim_ids)).difference(
        {str(link["claim_id"]) for link in links}
    )
    if missing_claims:
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_outcome_link_missing",
            "Ex-post learning omits outcome links for claims: " + ", ".join(sorted(missing_claims)),
            "claim_prediction_links",
        )
    normalized["claim_prediction_links"] = links
    normalized["calibration"] = _validate_calibration(record.get("calibration"))
    normalized["learning_records"] = _validate_learning_records(
        record.get("learning_records")
    )
    normalized["memory_contamination_check"] = _validate_memory_contamination_check(
        record.get("memory_contamination_check"),
        learning_records=normalized["learning_records"],
    )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_ex_post_learning_runtime_ref_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_ex_post_learning_runtime_event_missing",
    )
    return normalized


def build_lifecycle_reissue_report(
    *,
    report_id: str,
    case_id: str,
    claim_ids: Iterable[str],
    implementation_monitoring_evaluation: Mapping[str, Any] | None = None,
    rule_evolution_replay_context: Mapping[str, Any] | None = None,
    claim_requirement_bindings: Mapping[str, Iterable[str]] | None = None,
    legal_authority_report: Mapping[str, Any] | None = None,
    source_events: Iterable[Mapping[str, Any]] = (),
    participation_events: Iterable[Mapping[str, Any]] = (),
    policy_context_events: Iterable[Mapping[str, Any]] = (),
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    generated_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build the W4.C scoped lifecycle and partial-reissue report.

    The report is a runtime reader over existing DDM, legal, source,
    participation, policy-context, and rule-evolution evidence. It deliberately
    maps events to claim ids and emits a fail-closed issue when an event lacks
    claim scope, instead of rewriting an entire closed case.
    """

    generated = _iso_time(generated_at)
    known_claim_ids = _dedupe_texts(claim_ids)
    issues: list[dict[str, Any]] = []
    impacts: list[dict[str, Any]] = []
    impacts.extend(
        _ddm_lifecycle_impacts(
            implementation_monitoring_evaluation,
            claim_ids=known_claim_ids,
            generated_at=generated,
            issues=issues,
        )
    )
    impacts.extend(
        _legal_lifecycle_impacts(
            legal_authority_report,
            claim_ids=known_claim_ids,
            generated_at=generated,
            issues=issues,
        )
    )
    impacts.extend(
        _event_lifecycle_impacts(
            source_events,
            event_family="source",
            claim_ids=known_claim_ids,
            generated_at=generated,
            issues=issues,
        )
    )
    impacts.extend(
        _event_lifecycle_impacts(
            participation_events,
            event_family="participation",
            claim_ids=known_claim_ids,
            generated_at=generated,
            issues=issues,
        )
    )
    impacts.extend(
        _event_lifecycle_impacts(
            policy_context_events,
            event_family="policy_context",
            claim_ids=known_claim_ids,
            generated_at=generated,
            issues=issues,
        )
    )
    rule_impact = _rule_evolution_lifecycle_impact(
        rule_evolution_replay_context,
        claim_ids=known_claim_ids,
        claim_requirement_bindings=claim_requirement_bindings or {},
        generated_at=generated,
        issues=issues,
    )
    if rule_impact is not None:
        impacts.append(rule_impact)

    claim_states = _claim_revision_states(
        claim_ids=known_claim_ids,
        event_impacts=impacts,
    )
    status = _lifecycle_reissue_status(claim_states, issues)
    public_revision_state = _public_revision_state(
        case_id=case_id,
        status=status,
        claim_ids=known_claim_ids,
        claim_revision_states=claim_states,
        generated_at=generated,
        rule_evolution_replay_context=rule_evolution_replay_context,
    )
    report_ref = (
        _text(evidence_ref)
        or _stable_ref(
            {
                "report_id": report_id,
                "case_id": case_id,
                "claim_ids": known_claim_ids,
                "event_impacts": impacts,
                "public_revision_state": public_revision_state,
            }
        )
    )
    report_id_text = _required_text(
        report_id,
        "report_id",
        "policy_design_lifecycle_reissue_report_id_missing",
    )
    event_ref = (
        _text(runtime_event_ref)
        or f"event://policy-design-case/lifecycle-reissue/{report_id_text}"
    )
    payload = {
        "schema_version": LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION,
        "contract_id": LIFECYCLE_REISSUE_CONTRACT_ID,
        "report_id": report_id,
        "case_id": case_id,
        "generated_at": generated,
        "status": status,
        "claim_ids": known_claim_ids,
        "event_impacts": impacts,
        "claim_revision_states": claim_states,
        "public_revision_state": public_revision_state,
        "issues": issues,
        "summary": {
            "claim_count": len(known_claim_ids),
            "event_impact_count": len(impacts),
            "affected_claim_count": len(public_revision_state["affected_claim_ids"]),
            "unaffected_claim_count": len(public_revision_state["unaffected_claim_ids"]),
            "issue_count": len(issues),
        },
        "evidence_ref": report_ref,
        "runtime_event_ref": event_ref,
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "runtime_authority_envelope": _lifecycle_reissue_authority_envelope(
            report_ref=report_ref,
            runtime_event_ref=event_ref,
        ),
        "capability_reality": {
            "typed_contract": LIFECYCLE_REISSUE_CONTRACT_ID,
            "producer": "polisyos.runtime.quality.case_lifecycle.build_lifecycle_reissue_report",
            "artifact": report_ref,
            "orchestration_bridge": "DDM/legal/source/participation/rule events -> claim ids",
            "consumer": "validate_policy_design_lifecycle_records",
            "verification": "tests/unit/runtime/quality/test_policy_design_case_lifecycle.py",
            "surface": "public_export.semantic_audit.public_revision_states",
            "semantic_test": "unscoped lifecycle event cannot rewrite whole case",
        },
    }
    return validate_lifecycle_reissue_report(payload)


def validate_lifecycle_reissue_report(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the W4.C partial-reissue report shape and authority boundary."""

    if not isinstance(record, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_reissue_report_missing",
            "Lifecycle reissue report must be a mapping.",
            "lifecycle_reissue_report",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_lifecycle_reissue_schema_version_missing",
    )
    if schema_version != LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION:
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_reissue_schema_version_invalid",
            "Lifecycle reissue report must use the W4.C schema.",
            "schema_version",
        )
    normalized["schema_version"] = LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or LIFECYCLE_REISSUE_CONTRACT_ID
    normalized["report_id"] = _required_text(
        record.get("report_id") or record.get("id"),
        "report_id",
        "policy_design_lifecycle_reissue_report_id_missing",
    )
    normalized["case_id"] = _required_text(
        record.get("case_id"),
        "case_id",
        "policy_design_lifecycle_reissue_case_id_missing",
    )
    claim_ids = _dedupe_texts(record.get("claim_ids") or ())
    if not claim_ids:
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_reissue_claim_ids_missing",
            "Lifecycle reissue report must name scoped case claim ids.",
            "claim_ids",
        )
    normalized["claim_ids"] = claim_ids
    normalized["event_impacts"] = [
        _normalized_event_impact(row, claim_ids=claim_ids)
        for row in _mapping_rows(record.get("event_impacts"))
    ]
    normalized["claim_revision_states"] = [
        _normalized_claim_revision_state(row, claim_ids=claim_ids)
        for row in _mapping_rows(record.get("claim_revision_states"))
    ]
    normalized["public_revision_state"] = _required_mapping(
        record.get("public_revision_state"),
        "public_revision_state",
        "policy_design_public_revision_state_missing",
        "Lifecycle reissue report must include public revision state.",
    )
    normalized["issues"] = [dict(issue) for issue in _mapping_rows(record.get("issues"))]
    normalized["status"] = _required_text(
        record.get("status"),
        "status",
        "policy_design_lifecycle_reissue_status_missing",
    )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_lifecycle_reissue_runtime_ref_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_lifecycle_reissue_runtime_event_missing",
    )
    _reject_lifecycle_reissue_authority_leak(normalized)
    return normalized


def validate_policy_design_lifecycle_records(
    case: Mapping[str, Any],
    *,
    canary_kind: str = "production",
) -> list[PolicyDesignLifecycleIssue]:
    """Return scorecard issues for Phase 27.2 lifecycle/DDM/ex-post records."""

    if not isinstance(case, Mapping):
        return []
    if not _phase27_in_scope(case, canary_kind=canary_kind):
        return []
    issues: list[PolicyDesignLifecycleIssue] = []
    claim_ids = _major_claim_ids(case)

    monitoring_record = _first_mapping(
        case.get("implementation_monitoring_evaluation"),
        case.get("implementation_monitoring_and_evaluation"),
        case.get("implementation_monitoring_record"),
        case.get("implementation_monitoring_records"),
    )
    if monitoring_record is None:
        issues.append(
            PolicyDesignLifecycleIssue(
                code="policy_design_implementation_monitoring_record_missing",
                message=(
                    "Governed and production Policy Design Cases require implementation "
                    "contract, monitoring plan, and evaluation design records before "
                    "publication authority."
                ),
                field="implementation_monitoring_evaluation",
            )
        )
    else:
        try:
            validate_implementation_monitoring_evaluation_record(
                monitoring_record,
                required_claim_ids=claim_ids,
            )
        except ImplementationMonitoringEvaluationError as exc:
            issues.append(_issue_from_error(exc))

    lifecycle_record = _first_mapping(
        case.get("case_lifecycle"),
        case.get("lifecycle"),
        case.get("lifecycle_ledger"),
    )
    if lifecycle_record is None:
        issues.append(
            PolicyDesignLifecycleIssue(
                code="policy_design_case_lifecycle_missing",
                message=(
                    "Published or governed Policy Design Case requires an append-only "
                    "lifecycle ledger."
                ),
                field="case_lifecycle",
            )
        )
    else:
        try:
            validate_case_lifecycle_record(lifecycle_record)
        except PolicyDesignLifecycleError as exc:
            issues.append(_issue_from_error(exc))

    ex_post_record = _first_mapping(
        case.get("ex_post_learning"),
        case.get("ex_post_outcomes"),
        case.get("lifecycle_ex_post_and_calibration"),
    )
    if ex_post_record is None:
        issues.append(
            PolicyDesignLifecycleIssue(
                code="policy_design_ex_post_learning_missing",
                message=(
                    "Governed and production Policy Design Cases require ex-post "
                    "outcome reassessment, calibration, and contamination-control records."
                ),
                field="ex_post_learning",
            )
        )
    else:
        try:
            validate_ex_post_learning_record(
                ex_post_record,
                required_claim_ids=claim_ids,
            )
        except PolicyDesignLifecycleError as exc:
            issues.append(_issue_from_error(exc))

    reissue_report = _first_mapping(
        case.get("lifecycle_reissue_report"),
        case.get("partial_reissue_report"),
        case.get("claim_lifecycle_reissue"),
    )
    if reissue_report is not None:
        try:
            normalized_reissue = validate_lifecycle_reissue_report(reissue_report)
        except PolicyDesignLifecycleError as exc:
            issues.append(_issue_from_error(exc))
        else:
            issues.extend(_lifecycle_reissue_report_issues(normalized_reissue))

    issues.extend(_claim_future_prior_issues(case))
    return issues


def _validate_lifecycle_event(event: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    normalized["event_id"] = _required_text(
        event.get("event_id") or event.get("id"),
        "events.event_id",
        "policy_design_case_lifecycle_event_missing",
    )
    event_type = _required_text(
        event.get("event_type") or event.get("lifecycle_event"),
        "events.event_type",
        "policy_design_case_lifecycle_event_type_missing",
    )
    if event_type not in ALLOWED_LIFECYCLE_EVENTS:
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_event_type_invalid",
            "Lifecycle event type is not recognized.",
            "events.event_type",
        )
    normalized["event_type"] = event_type
    _required_text(
        event.get("previous_state"),
        "events.previous_state",
        "policy_design_case_lifecycle_transition_missing",
    )
    _required_text(
        event.get("new_state"),
        "events.new_state",
        "policy_design_case_lifecycle_transition_missing",
    )
    if not _text_values(event.get("evidence_refs")):
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_evidence_missing",
            "Lifecycle events must reference transition evidence.",
            "events.evidence_refs",
        )
    _required_text(
        event.get("runtime_event_ref"),
        "events.runtime_event_ref",
        "policy_design_case_lifecycle_runtime_event_missing",
    )
    return normalized


def _continuous_governance_reports(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_continuous_governance_report_missing",
            (
                "Case lifecycle must link continuous governance validity, reissue, "
                "supersession, and withdrawal reports."
            ),
            "continuous_governance_reports",
        )
    aliases = {
        "reissue": ("reissue", "reissued", "continuous_governance_reissue_report_ref"),
        "supersede": ("supersede", "superseded", "continuous_governance_supersede_report_ref"),
        "withdraw": ("withdraw", "withdrawn", "continuous_governance_withdraw_report_ref"),
        "validity": ("validity", "validity_report", "continuous_governance_stale_report_ref"),
    }
    normalized: dict[str, str] = {}
    for key, candidates in aliases.items():
        ref = None
        for candidate in candidates:
            candidate_ref = _text(value.get(candidate))
            if candidate_ref:
                ref = candidate_ref
                break
        if ref is None:
            raise PolicyDesignLifecycleError(
                "policy_design_continuous_governance_report_missing",
                f"Continuous governance report ref is missing: {key}.",
                f"continuous_governance_reports.{key}",
            )
        if not _runtime_artifact_ref(ref):
            raise PolicyDesignLifecycleError(
                "policy_design_continuous_governance_report_ref_invalid",
                f"Continuous governance report ref is not runtime authority: {key}.",
                f"continuous_governance_reports.{key}",
            )
        normalized[key] = ref
    return normalized


def _reject_historical_rewrite(
    record: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
) -> None:
    if bool(record.get("historical_authority_rewritten")) or bool(
        record.get("rewrites_historical_authority")
    ):
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_historical_rewrite",
            "Lifecycle records must append evidence without rewriting publication authority.",
            "case_lifecycle.historical_authority_rewritten",
        )
    for event in events:
        if bool(event.get("rewrites_historical_authority")):
            raise PolicyDesignLifecycleError(
                "policy_design_lifecycle_historical_rewrite",
                "Lifecycle events must not rewrite historical authority.",
                "case_lifecycle.events.rewrites_historical_authority",
            )


def _state_is_stale(current_state: str, events: Iterable[Mapping[str, Any]]) -> bool:
    if current_state == "stale":
        return True
    return any(
        _text(event.get("event_type")) == "stale"
        or _text(event.get("new_state")) == "stale"
        for event in events
    )


def _has_stale_resolution(
    events: Iterable[Mapping[str, Any]],
    resolution_refs: Iterable[str],
) -> bool:
    refs = set(resolution_refs)
    ordered_events = list(events)
    stale_indexes = [
        index
        for index, event in enumerate(ordered_events)
        if _text(event.get("event_type")) == "stale"
        or _text(event.get("new_state")) == "stale"
    ]
    last_stale_index = max(stale_indexes, default=-1)
    for index, event in enumerate(ordered_events):
        if index <= last_stale_index:
            continue
        event_id = _text(event.get("event_id"))
        event_type = _text(event.get("event_type"))
        if event_type in RESOLUTION_LIFECYCLE_EVENTS and (
            not refs or (event_id is not None and event_id in refs)
        ):
            return True
    return False


def _validate_prediction_outcome_link(link: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(link)
    normalized["link_id"] = _required_text(
        link.get("link_id") or link.get("id"),
        "claim_prediction_links.link_id",
        "policy_design_ex_post_outcome_link_missing",
    )
    normalized["claim_id"] = _required_text(
        link.get("claim_id"),
        "claim_prediction_links.claim_id",
        "policy_design_ex_post_outcome_link_missing",
    )
    for field, code in (
        ("prediction_ref", "policy_design_claim_prediction_ref_missing"),
        ("observed_outcome_ref", "policy_design_observed_outcome_ref_missing"),
        ("reassessment_ref", "policy_design_reassessment_ref_missing"),
        ("future_method_prior_ref", "policy_design_future_prior_ref_missing"),
        ("future_uncertainty_prior_ref", "policy_design_future_prior_ref_missing"),
    ):
        _required_text(link.get(field), f"claim_prediction_links.{field}", code)
    status = _required_text(
        link.get("reassessment_status"),
        "claim_prediction_links.reassessment_status",
        "policy_design_reassessment_status_missing",
    )
    if status not in REASSESSMENT_STATUSES:
        raise PolicyDesignLifecycleError(
            "policy_design_reassessment_status_invalid",
            (
                "Reassessment status must be confirmation, refutation, supersession, "
                "inconclusive, or accepted data deficit."
            ),
            "claim_prediction_links.reassessment_status",
        )
    normalized["reassessment_status"] = status
    return normalized


def _validate_calibration(value: object) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "calibration",
        "policy_design_calibration_evidence_missing",
        "Ex-post learning requires calibration, backtesting, leaderboard, and track-record refs.",
    )
    for field in (
        "calibration_report_refs",
        "backtesting_report_refs",
        "calibration_leaderboard_ref",
        "track_record_ref",
    ):
        if not _surface_present(record.get(field)):
            raise PolicyDesignLifecycleError(
                "policy_design_calibration_evidence_missing",
                f"Calibration evidence is missing {field}.",
                f"calibration.{field}",
            )
    return dict(record)


def _validate_learning_records(value: object) -> list[dict[str, Any]]:
    records = _mapping_rows(value)
    if not records:
        raise PolicyDesignLifecycleError(
            "policy_design_learning_record_missing",
            "Ex-post learning requires scoped reusable learning records.",
            "learning_records",
        )
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        for field in (
            "learning_id",
            "scope",
            "applicability",
            "revocation_conditions",
            "memory_contamination_controls",
        ):
            if not _surface_present(record.get(field)):
                raise PolicyDesignLifecycleError(
                    "policy_design_learning_record_missing",
                    f"Learning record is missing {field}.",
                    f"learning_records[{index}].{field}",
                )
        normalized.append(dict(record))
    return normalized


def _validate_memory_contamination_check(
    value: object,
    *,
    learning_records: list[dict[str, Any]],
) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "memory_contamination_check",
        "policy_design_memory_contamination_check_missing",
        "Ex-post learning requires a memory-contamination check.",
    )
    status = _required_text(
        record.get("status"),
        "memory_contamination_check.status",
        "policy_design_memory_contamination_check_missing",
    )
    explicit_findings = _mapping_rows(record.get("findings"))
    policy = _memory_policy(record.get("policy"))
    detected_findings = [
        finding.model_dump(mode="json")
        for finding in detect_memory_contamination(learning_records, policy=policy)
    ]
    blocking_findings = [
        finding
        for finding in [*explicit_findings, *detected_findings]
        if _text(finding.get("severity")) != "warning"
    ]
    if status != "clean" or blocking_findings:
        raise PolicyDesignLifecycleError(
            "policy_design_learning_contamination_detected",
            "Ex-post learning is contaminated or lacks a clean memory-contamination check.",
            "memory_contamination_check.findings",
        )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "memory_contamination_check.evidence_ref",
        "policy_design_memory_contamination_check_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "memory_contamination_check.runtime_event_ref",
        "policy_design_memory_contamination_check_missing",
    )
    return dict(record)


def _memory_policy(value: object) -> MemoryContaminationPolicy:
    if not isinstance(value, Mapping):
        return MemoryContaminationPolicy()
    return MemoryContaminationPolicy(
        hidden_ref_ids=set(_text_values(value.get("hidden_ref_ids"))),
        hidden_suite_ids=set(_text_values(value.get("hidden_suite_ids"))),
        canary_tokens=set(_text_values(value.get("canary_tokens"))),
    )


def _claim_future_prior_issues(case: Mapping[str, Any]) -> list[PolicyDesignLifecycleIssue]:
    issues: list[PolicyDesignLifecycleIssue] = []
    for claim in _major_claim_rows(case):
        claim_id = _text(claim.get("claim_id"))
        if claim_id is None:
            continue
        for field, code, message in (
            (
                "prediction_refs",
                "policy_design_claim_prediction_ref_missing",
                "Major claims need explicit prediction refs before ex-post reassessment.",
            ),
            (
                "observed_outcome_refs",
                "policy_design_observed_outcome_ref_missing",
                "Major claims need observed outcome refs after implementation monitoring.",
            ),
            (
                "reassessment_refs",
                "policy_design_reassessment_ref_missing",
                "Major claims need reassessment status refs.",
            ),
            (
                "future_prior_refs",
                "policy_design_future_prior_ref_missing",
                "Major claims need future method/uncertainty prior refs.",
            ),
        ):
            if not _surface_present(claim.get(field)):
                issues.append(
                    PolicyDesignLifecycleIssue(
                        code=code,
                        message=message,
                        field=f"final_major_claims.{field}",
                        affected_claim=claim_id,
                    )
                )
    return issues


def _ddm_lifecycle_impacts(
    record: Mapping[str, Any] | None,
    *,
    claim_ids: list[str],
    generated_at: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(record, Mapping):
        return []
    ddm = _first_mapping(record.get("ddm_monitoring"), record.get("ddm_events"))
    if ddm is None:
        return []
    impacts: list[dict[str, Any]] = []
    for group, rows in ddm.items():
        for row in _mapping_rows(rows):
            impact = _event_lifecycle_impact(
                row,
                event_family="ddm",
                claim_ids=claim_ids,
                generated_at=generated_at,
                issues=issues,
                default_event_type=str(group),
            )
            if impact is not None:
                impacts.append(impact)
    return impacts


def _legal_lifecycle_impacts(
    report: Mapping[str, Any] | None,
    *,
    claim_ids: list[str],
    generated_at: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(report, Mapping):
        return []
    impacts: list[dict[str, Any]] = []
    for anchor in _mapping_rows(report.get("claim_legal_anchors")):
        grade = (_text(anchor.get("admissibility_grade")) or "").casefold()
        blockers = _text_values(anchor.get("legal_authority_blocker_refs"))
        if (
            grade not in {"blocked_no_authority", "contested_authority", "limited_authority"}
            and not blockers
        ):
            continue
        event = {
            "event_id": anchor.get("anchor_id")
            or anchor.get("claim_legal_anchor_id")
            or f"legal-authority:{anchor.get('claim_id')}",
            "event_type": "legal_authority_change",
            "affected_claim_ids": _text_values(anchor.get("claim_id")),
            "admissibility_grade": grade,
            "reason": anchor.get("no_anchor_rationale")
            or anchor.get("reason")
            or "Claim-level legal authority changed.",
            "evidence_ref": report.get("producer_artifact_ref") or report.get("evidence_ref"),
            "runtime_event_ref": report.get("runtime_event_ref")
            or "event://lex/legal-authority/lifecycle",
        }
        impact = _event_lifecycle_impact(
            event,
            event_family="legal",
            claim_ids=claim_ids,
            generated_at=generated_at,
            issues=issues,
        )
        if impact is not None:
            impacts.append(impact)
    for issue in _mapping_rows(report.get("issues")):
        if not _text(issue.get("claim_id")):
            continue
        impact = _event_lifecycle_impact(
            {
                "event_id": issue.get("code") or "legal-authority-issue",
                "event_type": "legal_authority_issue",
                "affected_claim_ids": [issue.get("claim_id")],
                "severity": issue.get("severity"),
                "reason": issue.get("message") or issue.get("code"),
                "evidence_ref": issue.get("evidence_ref") or report.get("producer_artifact_ref"),
                "runtime_event_ref": issue.get("runtime_event_ref")
                or "event://lex/legal-authority/issue",
            },
            event_family="legal",
            claim_ids=claim_ids,
            generated_at=generated_at,
            issues=issues,
        )
        if impact is not None:
            impacts.append(impact)
    return impacts


def _event_lifecycle_impacts(
    events: Iterable[Mapping[str, Any]],
    *,
    event_family: str,
    claim_ids: list[str],
    generated_at: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        impact = _event_lifecycle_impact(
            event,
            event_family=event_family,
            claim_ids=claim_ids,
            generated_at=generated_at,
            issues=issues,
        )
        if impact is not None:
            impacts.append(impact)
    return impacts


def _event_lifecycle_impact(
    event: Mapping[str, Any],
    *,
    event_family: str,
    claim_ids: list[str],
    generated_at: str,
    issues: list[dict[str, Any]],
    default_event_type: str | None = None,
) -> dict[str, Any] | None:
    event_id = _text(event.get("event_id") or event.get("id")) or _stable_event_id(
        event_family=event_family,
        event=event,
    )
    affected_claims = [
        claim_id
        for claim_id in _dedupe_texts(
            event.get("affected_claim_ids")
            or event.get("claim_ids")
            or event.get("affected_claims")
            or event.get("claim_id")
        )
        if claim_id in set(claim_ids)
    ]
    if not affected_claims:
        issues.append(
            _lifecycle_reissue_issue(
                code="policy_design_lifecycle_event_claim_scope_missing",
                message=(
                    "Lifecycle event has no claim scope. W4.C refuses to rewrite "
                    "the whole case without affected claim ids."
                ),
                field="affected_claim_ids",
                event_id=event_id,
                event_family=event_family,
                evidence_ref=_text(event.get("evidence_ref") or event.get("cas_ref")),
            )
        )
        return None
    raw_unknown_claims = set(
        _dedupe_texts(
            event.get("affected_claim_ids")
            or event.get("claim_ids")
            or event.get("affected_claims")
            or event.get("claim_id")
        )
    ).difference(claim_ids)
    if raw_unknown_claims:
        issues.append(
            _lifecycle_reissue_issue(
                code="policy_design_lifecycle_event_unknown_claim_scope",
                message=(
                    "Lifecycle event references claim ids outside the closed case "
                    "revision scope."
                ),
                field="affected_claim_ids",
                event_id=event_id,
                event_family=event_family,
                evidence_ref=_text(event.get("evidence_ref") or event.get("cas_ref")),
                affected_claim=None,
                extra={"unknown_claim_ids": sorted(raw_unknown_claims)},
            )
        )
    event_type = _text(event.get("event_type") or event.get("type")) or default_event_type
    return {
        "event_id": event_id,
        "event_family": event_family,
        "event_type": event_type or event_family,
        "affected_claim_ids": affected_claims,
        "lifecycle_action": _lifecycle_action_for_event(
            event,
            event_family=event_family,
            event_type=event_type or event_family,
        ),
        "reason": _text(event.get("reason") or event.get("message"))
        or f"{event_family} event requires claim lifecycle review.",
        "downstream_status": _text(
            event.get("downstream_status")
            or event.get("publication_status")
            or event.get("readiness_status")
            or event.get("status")
        ),
        "evidence_ref": _text(event.get("evidence_ref") or event.get("cas_ref")),
        "runtime_event_ref": _text(event.get("runtime_event_ref")),
        "time_roles": _event_time_roles(event, generated_at=generated_at),
        "closed_case_historical_meaning": "preserved",
    }


def _rule_evolution_lifecycle_impact(
    replay_context: Mapping[str, Any] | None,
    *,
    claim_ids: list[str],
    claim_requirement_bindings: Mapping[str, Iterable[str]],
    generated_at: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(replay_context, Mapping):
        return None
    revalidation = _first_mapping(replay_context.get("revalidation_state")) or {}
    affected_requirements = _dedupe_texts(revalidation.get("affected_requirement_ids"))
    for mismatch in _mapping_rows(replay_context.get("logic_hash_mismatches")):
        affected_requirements.extend(
            _dedupe_texts(
                [
                    mismatch.get("requirement_id"),
                    mismatch.get("current_requirement_id"),
                ]
            )
        )
    affected_requirements = _dedupe_texts(affected_requirements)
    semantic_change = bool(replay_context.get("semantic_change_detected")) or bool(
        affected_requirements
    )
    if not semantic_change:
        return None
    claims = _claims_for_requirements(
        affected_requirements=affected_requirements,
        claim_requirement_bindings=claim_requirement_bindings,
        claim_ids=claim_ids,
    )
    event = {
        "event_id": "rule-evolution:" + (
            _text(replay_context.get("current_rule_registry_version")) or "current"
        ),
        "event_type": "rule_evolution_semantic_change",
        "affected_claim_ids": claims,
        "reason": "Rule or taxonomy semantics changed; closed case replays under original logic.",
        "evidence_ref": replay_context.get("current_rule_registry_ref"),
        "runtime_event_ref": "event://rule-evolution/public-revalidation",
        "lifecycle_action": "partial_reissue",
        "closure_time": _first_mapping(replay_context.get("time_roles"), {}).get(
            "closure_time"
        )
        if isinstance(replay_context.get("time_roles"), Mapping)
        else None,
        "replay_time": _first_mapping(replay_context.get("time_roles"), {}).get("replay_time")
        if isinstance(replay_context.get("time_roles"), Mapping)
        else generated_at,
    }
    impact = _event_lifecycle_impact(
        event,
        event_family="rule_evolution",
        claim_ids=claim_ids,
        generated_at=generated_at,
        issues=issues,
    )
    if impact is not None:
        impact["affected_requirement_ids"] = affected_requirements
        impact["public_annotation"] = dict(
            replay_context.get("public_annotation")
            if isinstance(replay_context.get("public_annotation"), Mapping)
            else {}
        )
    return impact


def _claims_for_requirements(
    *,
    affected_requirements: list[str],
    claim_requirement_bindings: Mapping[str, Iterable[str]],
    claim_ids: list[str],
) -> list[str]:
    affected = set(affected_requirements)
    claims: list[str] = []
    for claim_id in claim_ids:
        requirement_refs = set(_dedupe_texts(claim_requirement_bindings.get(claim_id) or ()))
        if affected.intersection(requirement_refs):
            claims.append(claim_id)
    return claims


def _claim_revision_states(
    *,
    claim_ids: list[str],
    event_impacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_claim: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claim_ids}
    for impact in event_impacts:
        for claim_id in _dedupe_texts(impact.get("affected_claim_ids")):
            if claim_id in by_claim:
                by_claim[claim_id].append(impact)
    states: list[dict[str, Any]] = []
    for claim_id in claim_ids:
        impacts = by_claim[claim_id]
        action = _strongest_lifecycle_action(impact["lifecycle_action"] for impact in impacts)
        states.append(
            {
                "claim_id": claim_id,
                "current_validity": _claim_current_validity(action),
                "lifecycle_action": action,
                "public_revision_status": _public_revision_status(action),
                "affected_event_ids": [str(impact["event_id"]) for impact in impacts],
                "affected_event_families": sorted(
                    {str(impact["event_family"]) for impact in impacts}
                ),
                "public_diff_required": action != "none",
                "closed_case_historical_meaning": "preserved",
                "reason": _claim_revision_reason(impacts, action=action),
            }
        )
    return states


def _public_revision_state(
    *,
    case_id: str,
    status: str,
    claim_ids: list[str],
    claim_revision_states: list[dict[str, Any]],
    generated_at: str,
    rule_evolution_replay_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    affected = [
        str(row["claim_id"])
        for row in claim_revision_states
        if row.get("lifecycle_action") != "none"
    ]
    unaffected = [claim_id for claim_id in claim_ids if claim_id not in set(affected)]
    public_diffs = [
        {
            "claim_id": str(row["claim_id"]),
            "diff_kind": str(row["lifecycle_action"]),
            "public_status": str(row["public_revision_status"]),
            "reason": str(row["reason"]),
        }
        for row in claim_revision_states
        if row.get("lifecycle_action") != "none"
    ]
    return {
        "schema_version": PUBLIC_REVISION_STATE_SCHEMA_VERSION,
        "case_id": case_id,
        "generated_at": generated_at,
        "current_case_validity": _public_case_validity(
            status=status,
            affected_count=len(affected),
            claim_count=len(claim_ids),
        ),
        "closed_case_historical_meaning": "preserved",
        "affected_claim_ids": affected,
        "unaffected_claim_ids": unaffected,
        "public_diffs": public_diffs,
        "public_diff_required": bool(public_diffs),
        "silent_upgrade_allowed": False,
        "revalidation_status": _public_revalidation_status(status),
        "rule_evolution_public_annotation": dict(
            rule_evolution_replay_context.get("public_annotation")
            if isinstance(rule_evolution_replay_context, Mapping)
            and isinstance(rule_evolution_replay_context.get("public_annotation"), Mapping)
            else {}
        ),
        "blocked_structural_policy_ref": RULE_EVOLUTION_PUBLIC_POLICY_ADR_BLOCKER,
        "authority_role": "projection_only",
        "provenance_kind": "runtime_projection",
        "authoritative_for": ["public_revision_state"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "mandatory_public_revalidation_policy",
            "scorecard_authority",
            "silent_current_logic_upgrade",
        ],
    }


def _lifecycle_reissue_status(
    claim_revision_states: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> str:
    if issues:
        return "fail"
    actions = [str(row["lifecycle_action"]) for row in claim_revision_states]
    if "withdraw" in actions:
        return "withdraw_required"
    if "supersede" in actions:
        return "supersede_required"
    if "partial_reissue" in actions:
        return "reissue_required"
    if "review_required" in actions:
        return "review_required"
    return "pass"


def _lifecycle_action_for_event(
    event: Mapping[str, Any],
    *,
    event_family: str,
    event_type: str,
) -> str:
    explicit = _text(event.get("lifecycle_action") or event.get("action"))
    if explicit:
        normalized = explicit.casefold()
        if normalized in {"reissue", "reissue_required", "partial_reissue"}:
            return "partial_reissue"
        if normalized in {"supersede", "superseded"}:
            return "supersede"
        if normalized in {"withdraw", "withdrawn", "withdrawal_review"}:
            return "withdraw"
        if normalized in {"review", "review_required", "human_review"}:
            return "review_required"
    status_text = " ".join(
        value
        for value in (
            _text(event.get("downstream_status")),
            _text(event.get("publication_status")),
            _text(event.get("readiness_status")),
            _text(event.get("status")),
            _text(event.get("severity")),
            _text(event.get("invalidation_type")),
            _text(event.get("admissibility_grade")),
            event_type,
        )
        if value
    ).casefold()
    if "withdraw" in status_text or "blocked_no_authority" in status_text:
        return "withdraw" if event_family in {"legal", "incident"} else "partial_reissue"
    if "supersede" in status_text:
        return "supersede"
    if any(token in status_text for token in ("reissue", "contradicted", "block")):
        return "partial_reissue"
    return "review_required"


def _strongest_lifecycle_action(actions: Iterable[str]) -> str:
    strongest = "none"
    for action in actions:
        normalized = action if action in REVISION_ACTION_ORDER else "review_required"
        if REVISION_ACTION_ORDER[normalized] > REVISION_ACTION_ORDER[strongest]:
            strongest = normalized
    return strongest


def _claim_current_validity(action: str) -> str:
    return {
        "none": "current",
        "review_required": "review_required",
        "partial_reissue": "revalidation_required",
        "supersede": "superseded",
        "withdraw": "withdrawn",
    }[action]


def _public_revision_status(action: str) -> str:
    return {
        "none": "current",
        "review_required": "review_required",
        "partial_reissue": "revalidation_required",
        "supersede": "superseded",
        "withdraw": "withdrawn",
    }[action]


def _public_case_validity(*, status: str, affected_count: int, claim_count: int) -> str:
    if status == "fail":
        return "review_required"
    if affected_count == 0:
        return "current"
    if affected_count < claim_count:
        return "partially_current"
    return _public_revalidation_status(status)


def _public_revalidation_status(status: str) -> str:
    return {
        "pass": "current",
        "review_required": "review_required",
        "reissue_required": "revalidation_required",
        "supersede_required": "superseded",
        "withdraw_required": "withdrawn",
        "fail": "review_required",
    }.get(status, "review_required")


def _claim_revision_reason(impacts: list[dict[str, Any]], *, action: str) -> str:
    if not impacts:
        return "No lifecycle event currently affects this claim."
    reasons = _dedupe_texts(impact.get("reason") for impact in impacts)
    if reasons:
        return "; ".join(reasons)
    return f"Claim requires {action} because lifecycle events affected its evidence."


def _event_time_roles(event: Mapping[str, Any], *, generated_at: str) -> dict[str, str | None]:
    occurred = _text(event.get("occurred_at") or event.get("event_time"))
    detection = _text(event.get("detected_at") or event.get("detection_time")) or occurred
    return {
        "event_time": occurred,
        "detection_time": detection or generated_at,
        "valid_time": _text(event.get("valid_time") or event.get("as_of_time")),
        "publication_time": _text(event.get("publication_time")),
        "closure_time": _text(event.get("closure_time")),
        "replay_time": _text(event.get("replay_time")) or generated_at,
    }


def _normalized_event_impact(
    row: Mapping[str, Any],
    *,
    claim_ids: list[str],
) -> dict[str, Any]:
    normalized = dict(row)
    normalized["event_id"] = _required_text(
        row.get("event_id"),
        "event_impacts.event_id",
        "policy_design_lifecycle_event_id_missing",
    )
    normalized["event_family"] = _required_text(
        row.get("event_family"),
        "event_impacts.event_family",
        "policy_design_lifecycle_event_family_missing",
    )
    affected = _dedupe_texts(row.get("affected_claim_ids"))
    if not affected:
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_event_claim_scope_missing",
            "Lifecycle event impacts must name affected claim ids.",
            "event_impacts.affected_claim_ids",
        )
    unknown = set(affected).difference(claim_ids)
    if unknown:
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_event_unknown_claim_scope",
            "Lifecycle event impacts reference claim ids outside this report.",
            "event_impacts.affected_claim_ids",
        )
    normalized["affected_claim_ids"] = affected
    action = _required_text(
        row.get("lifecycle_action"),
        "event_impacts.lifecycle_action",
        "policy_design_lifecycle_event_action_missing",
    )
    if action not in REVISION_ACTION_ORDER or action == "none":
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_event_action_invalid",
            (
                "Lifecycle event action must be review_required, partial_reissue, "
                "supersede, or withdraw."
            ),
            "event_impacts.lifecycle_action",
        )
    normalized["lifecycle_action"] = action
    return normalized


def _normalized_claim_revision_state(
    row: Mapping[str, Any],
    *,
    claim_ids: list[str],
) -> dict[str, Any]:
    normalized = dict(row)
    claim_id = _required_text(
        row.get("claim_id"),
        "claim_revision_states.claim_id",
        "policy_design_lifecycle_claim_state_claim_id_missing",
    )
    if claim_id not in claim_ids:
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_claim_state_unknown_claim",
            "Claim revision state references a claim outside this report.",
            "claim_revision_states.claim_id",
        )
    normalized["claim_id"] = claim_id
    action = _required_text(
        row.get("lifecycle_action"),
        "claim_revision_states.lifecycle_action",
        "policy_design_lifecycle_claim_state_action_missing",
    )
    if action not in REVISION_ACTION_ORDER:
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_claim_state_action_invalid",
            "Claim revision state action is not recognized.",
            "claim_revision_states.lifecycle_action",
        )
    return normalized


def _reject_lifecycle_reissue_authority_leak(record: Mapping[str, Any]) -> None:
    public_state = record.get("public_revision_state")
    if not isinstance(public_state, Mapping):
        return
    if _text(public_state.get("authority_role")) != "projection_only":
        raise PolicyDesignLifecycleError(
            "policy_design_public_revision_state_authority_leak",
            "Public revision state is a projection and cannot mint claim authority.",
            "public_revision_state.authority_role",
        )
    if public_state.get("silent_upgrade_allowed") is not False:
        raise PolicyDesignLifecycleError(
            "policy_design_public_revision_state_silent_upgrade",
            "Public revision state must forbid silent current-logic upgrades.",
            "public_revision_state.silent_upgrade_allowed",
        )


def _lifecycle_reissue_report_issues(
    report: Mapping[str, Any],
) -> list[PolicyDesignLifecycleIssue]:
    issues: list[PolicyDesignLifecycleIssue] = []
    for issue in _mapping_rows(report.get("issues")):
        if str(issue.get("severity") or "fail") not in {"fail", "error", "critical"}:
            continue
        issues.append(
            PolicyDesignLifecycleIssue(
                code=str(issue.get("code") or "policy_design_lifecycle_reissue_invalid"),
                message=str(
                    issue.get("message")
                    or "Lifecycle reissue report contains a blocking issue."
                ),
                field=str(issue.get("field") or "lifecycle_reissue_report"),
                evidence_ref=_text(issue.get("evidence_ref") or report.get("evidence_ref")),
                affected_claim=_text(issue.get("affected_claim")),
                next_action=str(
                    issue.get("next_action")
                    or (
                        "Resolve scoped lifecycle event mapping before public "
                        "revision or closeout."
                    )
                ),
            )
        )
    status = _text(report.get("status")) or "fail"
    if status in {
        "review_required",
        "reissue_required",
        "supersede_required",
        "withdraw_required",
    }:
        public_state = report.get("public_revision_state")
        affected_claims = (
            _text_values(public_state.get("affected_claim_ids"))
            if isinstance(public_state, Mapping)
            else []
        )
        issues.append(
            PolicyDesignLifecycleIssue(
                code=f"policy_design_lifecycle_{status}",
                message=(
                    "Lifecycle reissue report marks current public validity as "
                    f"{status} for scoped claims."
                ),
                field="lifecycle_reissue_report.status",
                evidence_ref=_text(report.get("evidence_ref")),
                affected_claim=affected_claims[0] if affected_claims else None,
                next_action=(
                    "Publish public revision state and complete scoped review, "
                    "partial reissue, supersession, or withdrawal before closeout."
                ),
            )
        )
    return issues


def _lifecycle_reissue_issue(
    *,
    code: str,
    message: str,
    field: str,
    event_id: str,
    event_family: str,
    evidence_ref: str | None,
    affected_claim: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": "fail",
        "status": "fail",
        "field": field,
        "event_id": event_id,
        "event_family": event_family,
        "message": message,
        "evidence_ref": evidence_ref,
        "affected_claim": affected_claim,
        "next_action": (
            "Map the event to affected claim ids and emit scoped public revision "
            "state; do not rewrite the whole case."
        ),
    }
    payload.update(dict(extra or {}))
    return {key: value for key, value in payload.items() if value not in (None, "", [])}


def _lifecycle_reissue_authority_envelope(
    *,
    report_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    return {
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "reader_contract": LIFECYCLE_REISSUE_CONTRACT_ID,
        "cas_ref": report_ref,
        "runtime_event_ref": runtime_event_ref,
        "authoritative_for": ["claim_lifecycle_reissue_state", "public_revision_state"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "mandatory_public_revalidation_policy",
            "silent_current_logic_upgrade",
        ],
    }


def _stable_event_id(*, event_family: str, event: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {"event_family": event_family, "event": _json_safe(event)},
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"lifecycle_event_{digest}"


def _stable_ref(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(_json_safe(payload), ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in sorted(value.items())}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _iso_time(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(microsecond=0).isoformat()
    text = _text(value)
    if text is not None:
        return text
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _dedupe_texts(value: object) -> list[str]:
    return list(dict.fromkeys(_text_values(value)))


def _phase27_in_scope(case: Mapping[str, Any], *, canary_kind: str) -> bool:
    profile = _effective_profile(case) or canary_kind.casefold()
    if profile in GOVERNED_LIFECYCLE_PROFILES:
        return True
    lifecycle = _first_mapping(case.get("case_lifecycle"), case.get("lifecycle"))
    if lifecycle is not None:
        state = _text(lifecycle.get("current_state") or lifecycle.get("state"))
        return state in {"published", "stale", "superseded", "withdrawn", "retracted"}
    return False


def _effective_profile(case: Mapping[str, Any]) -> str | None:
    authority_profile = case.get("authority_profile")
    if isinstance(authority_profile, Mapping):
        for key in (
            "effective_execution_profile",
            "requested_authority_level",
            "authority_profile",
        ):
            text = _text(authority_profile.get(key))
            if text is not None:
                return text.casefold()
    text = _text(case.get("effective_execution_profile"))
    return None if text is None else text.casefold()


def _major_claim_ids(case: Mapping[str, Any]) -> list[str]:
    return [
        claim_id
        for claim_id in (_text(claim.get("claim_id")) for claim in _major_claim_rows(case))
        if claim_id is not None
    ]


def _major_claim_rows(case: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _mapping_rows(case.get("final_major_claims") or case.get("major_claims"))
    return [row for row in rows if row.get("major") is not False]


def _issue_from_error(
    error: PolicyDesignLifecycleError | ImplementationMonitoringEvaluationError,
) -> PolicyDesignLifecycleIssue:
    return PolicyDesignLifecycleIssue(
        code=error.code,
        message=str(error),
        field=error.field or "policy_design_case",
    )


def _first_mapping(*candidates: object) -> Mapping[str, Any] | None:
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return candidate
        if isinstance(candidate, list | tuple):
            for item in candidate:
                if isinstance(item, Mapping):
                    return item
    return None


def _required_mapping(
    value: object,
    field: str,
    code: str,
    message: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise PolicyDesignLifecycleError(code, message, field)
    return value


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list | tuple):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _surface_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Iterable):
        return any(_surface_present(item) for item in value)
    return True


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise PolicyDesignLifecycleError(
            code,
            f"Required lifecycle text is missing: {field}.",
            field,
        )
    return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [] if text is None else [text]
    if isinstance(value, Mapping):
        return [
            text
            for text in (_text(item) for item in value.values())
            if text is not None
        ]
    if isinstance(value, Iterable):
        return [text for text in (_text(item) for item in value) if text is not None]
    return []


def _runtime_artifact_ref(value: object) -> bool:
    text = _text(value)
    if text is None:
        return False
    return bool(_SHA256_REF_RE.fullmatch(text)) or text.startswith("artifact://")


__all__ = [
    "ALLOWED_LIFECYCLE_EVENTS",
    "CASE_LIFECYCLE_CONTRACT_ID",
    "CASE_LIFECYCLE_SCHEMA_VERSION",
    "EX_POST_LEARNING_CONTRACT_ID",
    "EX_POST_LEARNING_SCHEMA_VERSION",
    "LIFECYCLE_REISSUE_CONTRACT_ID",
    "LIFECYCLE_REISSUE_REPORT_SCHEMA_VERSION",
    "PUBLIC_REVISION_STATE_SCHEMA_VERSION",
    "PolicyDesignLifecycleError",
    "PolicyDesignLifecycleIssue",
    "build_case_lifecycle_record",
    "build_ex_post_learning_record",
    "build_lifecycle_reissue_report",
    "validate_case_lifecycle_record",
    "validate_ex_post_learning_record",
    "validate_lifecycle_reissue_report",
    "validate_policy_design_lifecycle_records",
]
