"""Human-review calibration reports for production approval governance."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec

SCHEMA_VERSION = "policyos.human_review_calibration_report.v1"
PACKET_EVALUATION_SCHEMA_VERSION = "policyos.human_review_packet_evaluation.v1"
REVIEW_EFFECTIVENESS_TELEMETRY_SCHEMA_VERSION = (
    "policyos.human_review_effectiveness_telemetry.v1"
)
HUMAN_REVIEW_CALIBRATION_REPORT_KIND = "runtime.human_review_calibration_report"
HUMAN_REVIEW_CALIBRATION_REPORT_SCHEMA = "polisyos.runtime.HumanReviewCalibrationReport"
HUMAN_REVIEW_CALIBRATION_REPORT_FILENAME = "human_review_calibration_report.json"
REVIEW_EFFECTIVENESS_ADR_REF = "ADR-0171"
REVIEW_EFFECTIVENESS_MATURE_POLICY = "mature_governed"

_FLOW_ALIASES = {
    "approval": "approval",
    "approve": "approval",
    "override": "override",
    "escalation": "escalation",
    "escalate": "escalation",
    "withdrawal": "withdrawal",
    "withdraw": "withdrawal",
    "reissue": "reissue",
    "reject": "approval",
}

_OUTCOME_ALIASES = {
    "approved": "approve",
    "approval": "approve",
    "approve": "approve",
    "rejected": "reject",
    "reject": "reject",
    "escalated": "escalate",
    "escalate": "escalate",
    "overridden": "override",
    "override": "override",
    "reissued": "reissue",
    "reissue": "reissue",
    "withdrawn": "withdraw",
    "withdraw": "withdraw",
}

_PRIVATE_KEYS = {
    "private_note",
    "private_notes",
    "reviewer_private_note",
    "reviewer_private_notes",
    "raw_private_notes",
}


@dataclass(frozen=True)
class HumanReviewThresholds:
    """Production calibration thresholds for human-review quality signals."""

    agreement_warn: float = 0.8
    agreement_fail: float = 0.65
    override_rate_warn: float = 0.25
    override_rate_fail: float = 0.5
    override_correctness_warn: float = 0.75
    override_correctness_fail: float = 0.5
    unresolved_disagreement_warn: int = 1
    unresolved_disagreement_fail: int = 2
    reviewer_burden_minutes_warn: int = 45
    reviewer_burden_minutes_fail: int = 60
    reviewer_independence_warn: float = 0.95
    reviewer_independence_fail: float = 0.8
    separation_of_duty_warn: float = 0.95
    separation_of_duty_fail: float = 0.8
    approve_without_change_rate_warn: float = 0.85
    approve_without_change_rate_fail: float = 0.95
    minimum_effective_time_spent_seconds: int = 120
    rubber_stamp_risk_fail: float = 0.75


@dataclass(frozen=True)
class HumanReviewEffectivenessPolicy:
    """Governed policy controlling review-effectiveness telemetry consequences.

    Early review telemetry is measurement evidence only. It can become a
    blocking closeout input only when a governed policy explicitly enables
    blocking and cites longitudinal promotion evidence.
    """

    maturity: str = "early_advisory"
    blocking_enabled: bool = False
    policy_ref: str | None = None
    longitudinal_evidence_ref: str | None = None

    @property
    def permits_blocking(self) -> bool:
        """Return whether review-effectiveness telemetry may block closeout."""

        return (
            self.maturity == REVIEW_EFFECTIVENESS_MATURE_POLICY
            and self.blocking_enabled
            and _clean_text(self.policy_ref) is not None
            and _clean_text(self.longitudinal_evidence_ref) is not None
        )

    def to_public_dict(self) -> dict[str, Any]:
        """Project the policy into the public report without hidden defaults."""

        payload: dict[str, Any] = {
            "adr_ref": REVIEW_EFFECTIVENESS_ADR_REF,
            "maturity": self.maturity,
            "blocking_enabled": self.blocking_enabled,
            "blocking_permitted": self.permits_blocking,
        }
        if self.policy_ref:
            payload["policy_ref"] = self.policy_ref
        if self.longitudinal_evidence_ref:
            payload["longitudinal_evidence_ref"] = self.longitudinal_evidence_ref
        return payload


@dataclass(frozen=True)
class HumanReviewCalibrationPersistence:
    """Locations written when a human-review calibration report is materialized."""

    human_review_calibration_report_ref: ArtifactRef
    evidence_bundle_report_path: Path | None = None


DEFAULT_HUMAN_REVIEW_THRESHOLDS = HumanReviewThresholds()
DEFAULT_REVIEW_EFFECTIVENESS_POLICY = HumanReviewEffectivenessPolicy()


def deterministic_review_fixtures(*, now: datetime | None = None) -> list[dict[str, Any]]:
    """Return deterministic review events covering production governance outcomes."""

    base = _utc(now)
    return [
        _fixture_event(
            review_id="review-approve",
            flow="approval",
            outcome="approve",
            expected_outcome="approve",
            reviewer_identity="reviewer.alpha@example.test",
            completed_at=base,
            burden_minutes=6,
            decision_ref="sha256:" + "a" * 64,
            private_notes="raw reviewer note: approval evidence checked",
        ),
        _fixture_event(
            review_id="review-reject",
            flow="approval",
            outcome="reject",
            expected_outcome="reject",
            reviewer_identity="reviewer.beta@example.test",
            completed_at=base + timedelta(minutes=5),
            burden_minutes=7,
            decision_ref="sha256:" + "b" * 64,
        ),
        _fixture_event(
            review_id="review-escalate",
            flow="escalation",
            outcome="escalate",
            expected_outcome="reject",
            reviewer_identity="reviewer.gamma@example.test",
            completed_at=base + timedelta(minutes=11),
            burden_minutes=11,
            decision_ref="sha256:" + "c" * 64,
            disagreement_reason_code="scope_unclear",
            escalation_threshold="agreement_below_warn",
            unresolved=True,
        ),
        _fixture_event(
            review_id="review-override",
            flow="override",
            outcome="override",
            expected_outcome="override",
            reviewer_identity="reviewer.alpha@example.test",
            completed_at=base + timedelta(minutes=18),
            burden_minutes=9,
            decision_ref="sha256:" + "d" * 64,
            override_correct=True,
        ),
        _fixture_event(
            review_id="review-reissue",
            flow="reissue",
            outcome="reissue",
            expected_outcome="reissue",
            reviewer_identity="reviewer.beta@example.test",
            completed_at=base + timedelta(minutes=27),
            burden_minutes=8,
            decision_ref="sha256:" + "e" * 64,
        ),
        _fixture_event(
            review_id="review-withdraw",
            flow="withdrawal",
            outcome="withdraw",
            expected_outcome="withdraw",
            reviewer_identity="reviewer.delta@example.test",
            completed_at=base + timedelta(minutes=36),
            burden_minutes=10,
            decision_ref="sha256:" + "f" * 64,
        ),
    ]


def build_human_review_calibration_report(
    *,
    review_events: Sequence[Mapping[str, Any]],
    run_id: str | None = None,
    job_id: str | None = None,
    now: datetime | None = None,
    thresholds: HumanReviewThresholds = DEFAULT_HUMAN_REVIEW_THRESHOLDS,
    review_effectiveness_policy: HumanReviewEffectivenessPolicy = (
        DEFAULT_REVIEW_EFFECTIVENESS_POLICY
    ),
    report_ref: str | None = None,
) -> dict[str, Any]:
    """Build a stable calibration report from reviewer-attributed decisions."""

    generated_at = _utc(now)
    normalized_events = [_normalize_event(event) for event in review_events]
    summary = _summary(normalized_events)
    reviewer_burden = _reviewer_burden(normalized_events)
    oversight_effectiveness = _oversight_effectiveness(
        normalized_events,
        summary=summary,
        thresholds=thresholds,
    )
    producer_independence = _producer_independence(normalized_events)
    disagreement_reason_codes = _disagreement_reason_codes(normalized_events)
    escalation_thresholds = _counter_dict(
        event["escalation_threshold"]
        for event in normalized_events
        if event.get("escalation_threshold")
    )
    unresolved_disagreements = [
        _public_decision(event)
        for event in normalized_events
        if bool(event.get("unresolved"))
    ]
    reviewer_attributed_decisions = [
        _public_decision(event)
        for event in normalized_events
        if event.get("reviewer_identity")
    ]
    quality_signals = _quality_signals(
        summary=summary,
        reviewer_burden=reviewer_burden,
        oversight_effectiveness=oversight_effectiveness,
        producer_independence=producer_independence,
        thresholds=thresholds,
        blocking_permitted=review_effectiveness_policy.permits_blocking,
    )
    threshold_status = _overall_status(quality_signals)
    status = _review_effectiveness_report_status(
        threshold_status,
        policy=review_effectiveness_policy,
    )
    review_effectiveness_telemetry = _review_effectiveness_telemetry(
        normalized_events,
        summary=summary,
        oversight_effectiveness=oversight_effectiveness,
        producer_independence=producer_independence,
        quality_signals=quality_signals,
        policy=review_effectiveness_policy,
        threshold_status=threshold_status,
    )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "status": status,
        "run_id": run_id,
        "job_id": job_id,
        "summary": summary,
        "quality_signals": quality_signals,
        "review_effectiveness_telemetry": review_effectiveness_telemetry,
        "reviewer_burden": reviewer_burden,
        "oversight_effectiveness": oversight_effectiveness,
        "producer_independence": producer_independence,
        "disagreement_reason_codes": disagreement_reason_codes,
        "escalation_thresholds": escalation_thresholds,
        "unresolved_disagreements": unresolved_disagreements,
        "reviewer_attributed_decisions": reviewer_attributed_decisions,
        "privacy": {
            "reviewer_note_redacted_count": sum(
                1 for event in review_events if _has_private_note(event)
            ),
            "public_export_safe": True,
        },
    }
    if report_ref:
        report["human_review_calibration_report_ref"] = str(report_ref)
    return report


def evaluate_review_packet(
    packet: Mapping[str, Any] | Any,
    *,
    expected_scope: str | None = None,
    now: datetime | None = None,
    min_rationale_chars: int = 32,
) -> dict[str, Any]:
    """Evaluate one approval or override packet for human-review completeness."""

    packet_payload = _model_mapping(packet)
    generated_at = _datetime_from(packet_payload.get("generated_at"))
    decision = _clean_text(packet_payload.get("decision"))
    override = _mapping(packet_payload.get("override"))
    review_required = decision == "approved_with_override"
    checked_at = _utc(now)

    if not review_required:
        checks = [
            _check(
                "reviewer_attribution",
                "pass",
                "No reviewer override attribution is required for this decision.",
            ),
            _check(
                "packet_completeness",
                "pass" if generated_at is not None and decision else "fail",
                "Approval packet has generated_at and decision fields.",
            ),
            _check(
                "override_expiry",
                "pass",
                "No override expiry is required for this decision.",
            ),
            _check(
                "override_scope",
                "pass",
                "No override scope is required for this decision.",
            ),
            _check(
                "rationale_quality",
                "pass",
                "No override rationale is required for this decision.",
            ),
        ]
    else:
        expires_at = _datetime_from(override.get("expires_at"))
        checks = [
            _check(
                "reviewer_attribution",
                "pass"
                if _clean_text(override.get("reviewer_identity"))
                and _clean_text(override.get("signature"))
                else "fail",
                "Override packet must include reviewer identity and signature.",
            ),
            _check(
                "packet_completeness",
                "pass"
                if (
                    generated_at is not None
                    and _clean_text(override.get("scope"))
                    and expires_at is not None
                    and _clean_text(override.get("signed_at"))
                    and _clean_text(override.get("reason"))
                    and _nonempty_string_list(override.get("evidence_refs"))
                )
                else "fail",
                (
                    "Override packet must include generated_at, scope, expiry, "
                    "evidence, signed_at, and rationale."
                ),
            ),
            _check(
                "override_expiry",
                "pass" if expires_at is not None and expires_at > checked_at else "fail",
                "Override expiry must be in the future.",
            ),
            _check(
                "override_scope",
                "pass"
                if _scope_matches(
                    actual=_clean_text(override.get("scope")),
                    expected=expected_scope,
                )
                else "fail",
                "Override scope must match the reviewed run or job.",
            ),
            _check(
                "rationale_quality",
                "pass"
                if _rationale_is_strong(
                    override.get("reason"),
                    min_chars=min_rationale_chars,
                )
                else "fail",
                "Override rationale must explain the exception with enough detail.",
            ),
        ]

    return {
        "schema_version": PACKET_EVALUATION_SCHEMA_VERSION,
        "generated_at": checked_at.isoformat(),
        "status": _overall_status(checks),
        "decision": decision,
        "expected_scope": expected_scope,
        "checks": checks,
    }


def human_review_public_export(report: Mapping[str, Any]) -> dict[str, Any]:
    """Project a calibration report into a private-note-free public export."""

    public_payload = {
        "schema_version": report.get("schema_version", SCHEMA_VERSION),
        "generated_at": report.get("generated_at"),
        "status": report.get("status"),
        "run_id": report.get("run_id"),
        "job_id": report.get("job_id"),
        "human_review_calibration_report_ref": report.get(
            "human_review_calibration_report_ref"
        ),
        "summary": report.get("summary", {}),
        "quality_signals": report.get("quality_signals", []),
        "review_effectiveness_telemetry": report.get(
            "review_effectiveness_telemetry",
            {},
        ),
        "reviewer_burden": report.get("reviewer_burden", {}),
        "oversight_effectiveness": report.get("oversight_effectiveness", {}),
        "producer_independence": report.get("producer_independence", {}),
        "disagreement_reason_codes": report.get("disagreement_reason_codes", {}),
        "escalation_thresholds": report.get("escalation_thresholds", {}),
        "unresolved_disagreements": report.get("unresolved_disagreements", []),
        "reviewer_attributed_decisions": report.get(
            "reviewer_attributed_decisions",
            [],
        ),
        "privacy": report.get("privacy", {"public_export_safe": True}),
    }
    return _strip_private_keys(public_payload)


def persist_human_review_calibration_report(
    report: Mapping[str, Any],
    *,
    store: Any,
    evidence_bundle_path: str | Path | None = None,
) -> HumanReviewCalibrationPersistence:
    """Persist a human-review calibration report in CAS and evidence bundles."""

    report_payload = human_review_public_export(report)
    ref = store.put_json(
        report_payload,
        ArtifactWriteOptions(
            kind=HUMAN_REVIEW_CALIBRATION_REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=HUMAN_REVIEW_CALIBRATION_REPORT_SCHEMA,
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    report_path = _write_evidence_bundle_report(
        report_payload=report_payload,
        report_ref=ref,
        evidence_bundle_path=evidence_bundle_path,
    )
    return HumanReviewCalibrationPersistence(
        human_review_calibration_report_ref=ref,
        evidence_bundle_report_path=report_path,
    )


def _fixture_event(**payload: Any) -> dict[str, Any]:
    event = dict(payload)
    completed_at = event.get("completed_at")
    if isinstance(completed_at, datetime):
        event["completed_at"] = completed_at.isoformat()
    return event


def _normalize_event(event: Mapping[str, Any]) -> dict[str, Any]:
    outcome = _normalize_outcome(event.get("outcome") or event.get("decision"))
    expected_outcome = _normalize_outcome(event.get("expected_outcome"))
    agreement = _bool_or_none(event.get("agreement"))
    if agreement is None and outcome and expected_outcome:
        agreement = outcome == expected_outcome
    producer_identity = _clean_text(
        event.get("producer_identity")
        or event.get("producer_id")
        or event.get("producer")
    )
    reviewer_identity = _clean_text(event.get("reviewer_identity"))
    reviewer_independent = _bool_or_none(
        event.get("reviewer_independent")
        if "reviewer_independent" in event
        else event.get("independent_from_producer")
    )
    if (
        reviewer_independent is None
        and reviewer_identity is not None
        and producer_identity is not None
    ):
        reviewer_independent = reviewer_identity != producer_identity
    separation_source = (
        event.get("separation_of_duty_attested")
        if "separation_of_duty_attested" in event
        else event.get("producer_independence_attested")
    )
    separation_of_duty_attested = _bool_or_none(
        separation_source
    )
    time_spent_seconds = _time_spent_seconds(event)
    change_requests = _change_requests(event)
    dissent = bool(_bool_or_none(event.get("dissent")) or False)
    approved_without_change = _bool_or_none(event.get("approved_without_change"))
    if approved_without_change is None:
        approved_without_change = outcome == "approve" and not change_requests and not dissent
    return {
        "review_id": _clean_text(event.get("review_id") or event.get("id")),
        "flow": _normalize_flow(event.get("flow") or outcome),
        "outcome": outcome,
        "expected_outcome": expected_outcome,
        "reviewer_identity": reviewer_identity,
        "producer_identity": producer_identity,
        "reviewer_independent": reviewer_independent,
        "separation_of_duty_attested": separation_of_duty_attested,
        "decision_ref": _clean_text(event.get("decision_ref")),
        "packet_ref": _clean_text(event.get("packet_ref")),
        "completed_at": _clean_text(event.get("completed_at")),
        "burden_minutes": (
            _number(event.get("burden_minutes"))
            or (time_spent_seconds / 60 if time_spent_seconds is not None else 0)
        ),
        "time_spent_seconds": time_spent_seconds,
        "exposure_order": _int_or_none(event.get("exposure_order")),
        "dissent": dissent,
        "change_request_count": len(change_requests),
        "change_requests": change_requests,
        "approved_without_change": approved_without_change,
        "agreement": agreement,
        "disagreement_reason_code": _clean_text(
            event.get("disagreement_reason_code")
        ),
        "override_correct": _bool_or_none(event.get("override_correct")),
        "escalation_threshold": _clean_text(event.get("escalation_threshold")),
        "unresolved": bool(event.get("unresolved")),
    }


def _summary(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    review_count = len(events)
    outcome_counts = _counter_dict(event.get("outcome") for event in events)
    flow_counts = _counter_dict(event.get("flow") for event in events)
    agreement_values = [
        bool(event["agreement"])
        for event in events
        if event.get("agreement") is not None
    ]
    override_events = [
        event
        for event in events
        if event.get("outcome") == "override" or event.get("flow") == "override"
    ]
    override_correctness_values = [
        bool(event["override_correct"])
        for event in override_events
        if event.get("override_correct") is not None
    ]
    approval_events = [event for event in events if event.get("outcome") == "approve"]
    approve_without_change_values = [
        bool(event.get("approved_without_change")) for event in approval_events
    ]
    reviewer_independence_values = [
        bool(event["reviewer_independent"])
        for event in events
        if event.get("reviewer_independent") is not None
    ]
    separation_of_duty_values = [
        bool(event["separation_of_duty_attested"])
        for event in events
        if event.get("separation_of_duty_attested") is not None
    ]
    return {
        "review_count": review_count,
        "flow_counts": flow_counts,
        "outcome_counts": outcome_counts,
        "agreement_rate": _rate(agreement_values),
        "agreement_denominator": len(agreement_values),
        "override_rate": len(override_events) / review_count if review_count else None,
        "override_count": len(override_events),
        "override_correctness_rate": _rate(override_correctness_values),
        "override_correctness_denominator": len(override_correctness_values),
        "approve_without_change_rate": _rate(approve_without_change_values),
        "approve_without_change_count": sum(
            1 for value in approve_without_change_values if value
        ),
        "approval_count": len(approval_events),
        "reviewer_independence_rate": _rate(reviewer_independence_values),
        "reviewer_independence_denominator": len(reviewer_independence_values),
        "separation_of_duty_attestation_rate": _rate(separation_of_duty_values),
        "separation_of_duty_attestation_denominator": len(separation_of_duty_values),
        "dissent_count": sum(1 for event in events if bool(event.get("dissent"))),
        "change_request_count": sum(
            int(event.get("change_request_count") or 0) for event in events
        ),
        "unresolved_disagreement_count": sum(
            1 for event in events if bool(event.get("unresolved"))
        ),
        "reviewer_attributed_decision_count": sum(
            1 for event in events if event.get("reviewer_identity")
        ),
    }


def _oversight_effectiveness(
    events: Sequence[Mapping[str, Any]],
    *,
    summary: Mapping[str, Any],
    thresholds: HumanReviewThresholds,
) -> dict[str, Any]:
    time_spent = [
        int(event["time_spent_seconds"])
        for event in events
        if event.get("time_spent_seconds") is not None
    ]
    low_time_count = sum(
        1
        for seconds in time_spent
        if seconds < thresholds.minimum_effective_time_spent_seconds
    )
    reviewer_independence_rate = _number(summary.get("reviewer_independence_rate"))
    approve_without_change_rate = _number(summary.get("approve_without_change_rate"))
    separation_rate = _number(summary.get("separation_of_duty_attestation_rate"))
    challenge_signal_count = int(summary.get("dissent_count") or 0) + int(
        summary.get("change_request_count") or 0
    )
    score = 0.0
    if approve_without_change_rate is not None:
        score += approve_without_change_rate * 0.4
    if time_spent:
        score += (low_time_count / len(time_spent)) * 0.25
    if reviewer_independence_rate is not None:
        score += (1.0 - reviewer_independence_rate) * 0.2
    if separation_rate is not None:
        score += (1.0 - separation_rate) * 0.1
    if challenge_signal_count == 0 and events:
        score += 0.05
    score = min(1.0, score)
    risk = "low"
    if score >= thresholds.rubber_stamp_risk_fail:
        risk = "high"
    elif score >= 0.5:
        risk = "medium"
    return {
        "review_count": len(events),
        "reviewer_independence_rate": reviewer_independence_rate,
        "separation_of_duty_attestation_rate": separation_rate,
        "approve_without_change_rate": approve_without_change_rate,
        "average_time_spent_seconds": (
            sum(time_spent) / len(time_spent) if time_spent else None
        ),
        "low_time_review_count": low_time_count,
        "dissent_count": int(summary.get("dissent_count") or 0),
        "change_request_count": int(summary.get("change_request_count") or 0),
        "rubber_stamp_score": score,
        "rubber_stamp_risk": risk,
        "effective_oversight": risk != "high"
        and (reviewer_independence_rate is None or reviewer_independence_rate >= 0.8),
    }


def _producer_independence(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attested = [
        bool(event["separation_of_duty_attested"])
        for event in events
        if event.get("separation_of_duty_attested") is not None
    ]
    overlap_count = sum(
        1
        for event in events
        if event.get("producer_identity")
        and event.get("producer_identity") == event.get("reviewer_identity")
    )
    producer_count = len(
        {
            str(event.get("producer_identity"))
            for event in events
            if event.get("producer_identity")
        }
    )
    return {
        "producer_count": producer_count,
        "producer_reviewer_overlap_count": overlap_count,
        "separation_of_duty_attestation_rate": _rate(attested),
        "separation_of_duty_attestation_denominator": len(attested),
        "separation_of_duty_satisfied": not attested or all(attested),
    }


def _reviewer_burden(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_reviewer: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "review_count": 0,
            "burden_minutes": 0,
            "override_count": 0,
            "unresolved_disagreement_count": 0,
        }
    )
    total_minutes = 0
    for event in events:
        reviewer = str(event.get("reviewer_identity") or "unattributed")
        minutes = int(event.get("burden_minutes") or 0)
        total_minutes += minutes
        by_reviewer[reviewer]["review_count"] += 1
        by_reviewer[reviewer]["burden_minutes"] += minutes
        if event.get("outcome") == "override" or event.get("flow") == "override":
            by_reviewer[reviewer]["override_count"] += 1
        if event.get("unresolved"):
            by_reviewer[reviewer]["unresolved_disagreement_count"] += 1

    per_reviewer = [
        {"reviewer_identity": reviewer, **payload}
        for reviewer, payload in sorted(by_reviewer.items())
    ]
    return {
        "total_minutes": total_minutes,
        "average_minutes_per_review": (
            total_minutes / len(events) if len(events) > 0 else None
        ),
        "reviewer_count": len(by_reviewer),
        "per_reviewer": per_reviewer,
        "max_reviewer_minutes": max(
            (row["burden_minutes"] for row in per_reviewer),
            default=0,
        ),
    }


def _disagreement_reason_codes(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return _counter_dict(
        event.get("disagreement_reason_code")
        for event in events
        if event.get("disagreement_reason_code")
    )


def _quality_signals(
    *,
    summary: Mapping[str, Any],
    reviewer_burden: Mapping[str, Any],
    oversight_effectiveness: Mapping[str, Any],
    producer_independence: Mapping[str, Any],
    thresholds: HumanReviewThresholds,
    blocking_permitted: bool,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    agreement_rate = _number(summary.get("agreement_rate"))
    if agreement_rate is not None:
        if agreement_rate < thresholds.agreement_fail:
            signals.append(
                _signal(
                    "reviewer_agreement_below_fail_threshold",
                    "fail",
                    agreement_rate,
                    thresholds.agreement_fail,
                    "Reviewer agreement is below the production fail threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )
        elif agreement_rate < thresholds.agreement_warn:
            signals.append(
                _signal(
                    "reviewer_agreement_below_warn_threshold",
                    "warn",
                    agreement_rate,
                    thresholds.agreement_warn,
                    "Reviewer agreement is below the production warning threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )

    override_rate = _number(summary.get("override_rate"))
    if override_rate is not None:
        if override_rate > thresholds.override_rate_fail:
            signals.append(
                _signal(
                    "override_rate_above_fail_threshold",
                    "fail",
                    override_rate,
                    thresholds.override_rate_fail,
                    "Override rate is above the production fail threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )
        elif override_rate > thresholds.override_rate_warn:
            signals.append(
                _signal(
                    "override_rate_above_warn_threshold",
                    "warn",
                    override_rate,
                    thresholds.override_rate_warn,
                    "Override rate is above the production warning threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )

    override_correctness_rate = _number(summary.get("override_correctness_rate"))
    if override_correctness_rate is not None:
        if override_correctness_rate < thresholds.override_correctness_fail:
            signals.append(
                _signal(
                    "override_correctness_below_fail_threshold",
                    "fail",
                    override_correctness_rate,
                    thresholds.override_correctness_fail,
                    "Override correctness is below the production fail threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )
        elif override_correctness_rate < thresholds.override_correctness_warn:
            signals.append(
                _signal(
                    "override_correctness_below_warn_threshold",
                    "warn",
                    override_correctness_rate,
                    thresholds.override_correctness_warn,
                    "Override correctness is below the production warning threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )

    unresolved_count = int(summary.get("unresolved_disagreement_count") or 0)
    if unresolved_count >= thresholds.unresolved_disagreement_fail:
        signals.append(
            _signal(
                "unresolved_disagreements_above_fail_threshold",
                "fail",
                unresolved_count,
                thresholds.unresolved_disagreement_fail,
                "Unresolved reviewer disagreements exceed the production fail threshold.",
                blocking_permitted=blocking_permitted,
            )
        )
    elif unresolved_count >= thresholds.unresolved_disagreement_warn:
        signals.append(
            _signal(
                "unresolved_disagreements_above_warn_threshold",
                "warn",
                unresolved_count,
                thresholds.unresolved_disagreement_warn,
                "Unresolved reviewer disagreements exceed the production warning threshold.",
                blocking_permitted=blocking_permitted,
            )
        )

    max_minutes = int(reviewer_burden.get("max_reviewer_minutes") or 0)
    if max_minutes >= thresholds.reviewer_burden_minutes_fail:
        signals.append(
            _signal(
                "reviewer_burden_above_fail_threshold",
                "fail",
                max_minutes,
                thresholds.reviewer_burden_minutes_fail,
                "Reviewer burden exceeds the production fail threshold.",
                blocking_permitted=blocking_permitted,
            )
        )
    elif max_minutes >= thresholds.reviewer_burden_minutes_warn:
        signals.append(
            _signal(
                "reviewer_burden_above_warn_threshold",
                "warn",
                max_minutes,
                thresholds.reviewer_burden_minutes_warn,
                "Reviewer burden exceeds the production warning threshold.",
                blocking_permitted=blocking_permitted,
            )
        )
    reviewer_independence_rate = _number(summary.get("reviewer_independence_rate"))
    if reviewer_independence_rate is not None:
        if reviewer_independence_rate < thresholds.reviewer_independence_fail:
            signals.append(
                _signal(
                    "reviewer_independence_below_fail_threshold",
                    "fail",
                    reviewer_independence_rate,
                    thresholds.reviewer_independence_fail,
                    "Reviewer independence is below the production fail threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )
        elif reviewer_independence_rate < thresholds.reviewer_independence_warn:
            signals.append(
                _signal(
                    "reviewer_independence_below_warn_threshold",
                    "warn",
                    reviewer_independence_rate,
                    thresholds.reviewer_independence_warn,
                    "Reviewer independence is below the production warning threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )

    separation_rate = _number(
        producer_independence.get("separation_of_duty_attestation_rate")
    )
    if separation_rate is not None:
        if separation_rate < thresholds.separation_of_duty_fail:
            signals.append(
                _signal(
                    "separation_of_duty_below_fail_threshold",
                    "fail",
                    separation_rate,
                    thresholds.separation_of_duty_fail,
                    (
                        "Producer/reviewer separation of duty is below the production "
                        "fail threshold."
                    ),
                    blocking_permitted=blocking_permitted,
                )
            )
        elif separation_rate < thresholds.separation_of_duty_warn:
            signals.append(
                _signal(
                    "separation_of_duty_below_warn_threshold",
                    "warn",
                    separation_rate,
                    thresholds.separation_of_duty_warn,
                    (
                        "Producer/reviewer separation of duty is below the production "
                        "warning threshold."
                    ),
                    blocking_permitted=blocking_permitted,
                )
            )

    approve_without_change_rate = _number(summary.get("approve_without_change_rate"))
    if approve_without_change_rate is not None:
        if approve_without_change_rate >= thresholds.approve_without_change_rate_fail:
            signals.append(
                _signal(
                    "approve_without_change_rate_above_fail_threshold",
                    "fail",
                    approve_without_change_rate,
                    thresholds.approve_without_change_rate_fail,
                    "Approve-without-change rate is above the production fail threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )
        elif approve_without_change_rate >= thresholds.approve_without_change_rate_warn:
            signals.append(
                _signal(
                    "approve_without_change_rate_above_warn_threshold",
                    "warn",
                    approve_without_change_rate,
                    thresholds.approve_without_change_rate_warn,
                    "Approve-without-change rate is above the production warning threshold.",
                    blocking_permitted=blocking_permitted,
                )
            )

    rubber_stamp_score = _number(oversight_effectiveness.get("rubber_stamp_score"))
    if rubber_stamp_score is not None and rubber_stamp_score >= thresholds.rubber_stamp_risk_fail:
        signals.append(
            _signal(
                "rubber_stamp_risk_above_fail_threshold",
                "fail",
                rubber_stamp_score,
                thresholds.rubber_stamp_risk_fail,
                "Review pattern is consistent with rubber-stamp risk.",
                blocking_permitted=blocking_permitted,
            )
        )
    return signals


def _review_effectiveness_report_status(
    threshold_status: str,
    *,
    policy: HumanReviewEffectivenessPolicy,
) -> str:
    if policy.permits_blocking:
        return threshold_status
    return "pass"


def _review_effectiveness_telemetry(
    events: Sequence[Mapping[str, Any]],
    *,
    summary: Mapping[str, Any],
    oversight_effectiveness: Mapping[str, Any],
    producer_independence: Mapping[str, Any],
    quality_signals: Sequence[Mapping[str, Any]],
    policy: HumanReviewEffectivenessPolicy,
    threshold_status: str,
) -> dict[str, Any]:
    blocking_permitted = policy.permits_blocking
    blocking_signal_codes = [
        str(signal.get("code"))
        for signal in quality_signals
        if signal.get("status") == "fail" and signal.get("blocking")
    ]
    advisory_signal_codes = [
        str(signal.get("code"))
        for signal in quality_signals
        if signal.get("status") in {"fail", "warn"} and not signal.get("blocking")
    ]
    return {
        "schema_version": REVIEW_EFFECTIVENESS_TELEMETRY_SCHEMA_VERSION,
        "adr_ref": REVIEW_EFFECTIVENESS_ADR_REF,
        "threshold_status": threshold_status,
        "posture": "governed_blocking" if blocking_permitted else "advisory",
        "blocking_permitted": blocking_permitted,
        "report_status_effect": (
            threshold_status if blocking_permitted else "pass_advisory_only"
        ),
        "policy": policy.to_public_dict(),
        "authority_boundary": {
            "authoritative_for": [
                "review_effectiveness_measurement",
                "future_policy_calibration",
                "reviewer_load_observability",
            ],
            "may_not_use_for": (
                []
                if blocking_permitted
                else [
                    "current_run_closeout_block",
                    "publication_block",
                    "claim_support_downgrade",
                ]
            ),
        },
        "measured_signals": _review_effectiveness_measured_signals(
            events,
            summary=summary,
            oversight_effectiveness=oversight_effectiveness,
            producer_independence=producer_independence,
        ),
        "advisory_signal_codes": advisory_signal_codes,
        "blocking_signal_codes": blocking_signal_codes,
    }


def _review_effectiveness_measured_signals(
    events: Sequence[Mapping[str, Any]],
    *,
    summary: Mapping[str, Any],
    oversight_effectiveness: Mapping[str, Any],
    producer_independence: Mapping[str, Any],
) -> dict[str, Any]:
    review_count = len(events)
    review_times = [
        int(event["time_spent_seconds"])
        for event in events
        if event.get("time_spent_seconds") is not None
    ]
    no_delta_count = sum(
        1
        for event in events
        if bool(event.get("approved_without_change"))
        or (
            not bool(event.get("dissent"))
            and int(event.get("change_request_count") or 0) == 0
            and event.get("outcome") == "approve"
        )
    )
    separation_values = [
        bool(event["separation_of_duty_attested"])
        for event in events
        if event.get("separation_of_duty_attested") is not None
    ]
    separation_failure_count = sum(1 for value in separation_values if not value)
    return {
        "review_count": review_count,
        "review_time_seconds_average": (
            sum(review_times) / len(review_times) if review_times else None
        ),
        "review_time_seconds_median": _median(review_times),
        "low_time_review_count": int(
            oversight_effectiveness.get("low_time_review_count") or 0
        ),
        "override_rate": summary.get("override_rate"),
        "override_count": int(summary.get("override_count") or 0),
        "dissent_rate": (
            int(summary.get("dissent_count") or 0) / review_count
            if review_count
            else None
        ),
        "dissent_count": int(summary.get("dissent_count") or 0),
        "no_delta_review_rate": no_delta_count / review_count if review_count else None,
        "no_delta_review_count": no_delta_count,
        "separation_of_duty_failure_rate": (
            separation_failure_count / len(separation_values)
            if separation_values
            else None
        ),
        "separation_of_duty_failure_count": separation_failure_count,
    }


def _median(values: Sequence[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[midpoint])
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _signal(
    code: str,
    status: str,
    value: float | int,
    threshold: float | int,
    message: str,
    *,
    blocking_permitted: bool,
) -> dict[str, Any]:
    return {
        "code": code,
        "status": status,
        "value": value,
        "threshold": threshold,
        "message": message,
        "blocking": status == "fail" and blocking_permitted,
        "authority_effect": (
            "blocking_closeout_input"
            if status == "fail" and blocking_permitted
            else "advisory_measurement"
        ),
    }


def _public_decision(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "review_id": event.get("review_id"),
            "flow": event.get("flow"),
            "outcome": event.get("outcome"),
            "expected_outcome": event.get("expected_outcome"),
            "reviewer_identity": event.get("reviewer_identity"),
            "producer_identity": event.get("producer_identity"),
            "reviewer_independent": event.get("reviewer_independent"),
            "separation_of_duty_attested": event.get("separation_of_duty_attested"),
            "decision_ref": event.get("decision_ref"),
            "packet_ref": event.get("packet_ref"),
            "completed_at": event.get("completed_at"),
            "exposure_order": event.get("exposure_order"),
            "time_spent_seconds": event.get("time_spent_seconds"),
            "dissent": bool(event.get("dissent")),
            "change_request_count": event.get("change_request_count"),
            "approved_without_change": event.get("approved_without_change"),
            "disagreement_reason_code": event.get("disagreement_reason_code"),
            "escalation_threshold": event.get("escalation_threshold"),
            "unresolved": bool(event.get("unresolved")),
        }.items()
        if value not in (None, "")
    }


def _write_evidence_bundle_report(
    *,
    report_payload: dict[str, Any],
    report_ref: ArtifactRef,
    evidence_bundle_path: str | Path | None,
) -> Path | None:
    if evidence_bundle_path is None:
        return None
    bundle_path = Path(evidence_bundle_path)
    report_path = (
        bundle_path
        if bundle_path.suffix.lower() == ".json"
        else bundle_path / HUMAN_REVIEW_CALIBRATION_REPORT_FILENAME
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_payload = {
        "schema_version": "policyos.human_review_calibration_bundle_entry.v1",
        "human_review_calibration_report_ref": str(report_ref.artifact_id),
        "report": report_payload,
    }
    report_path.write_text(
        json.dumps(bundle_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path


def _check(code: str, status: str, message: str) -> dict[str, str]:
    return {"code": code, "status": status, "message": message}


def _overall_status(signals_or_checks: Sequence[Mapping[str, Any]]) -> str:
    statuses = {str(item.get("status") or "").lower() for item in signals_or_checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses or "warning" in statuses:
        return "warn"
    return "pass"


def _rate(values: Sequence[bool]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _counter_dict(values: Any) -> dict[str, int]:
    counts = Counter(str(value) for value in values if value not in (None, ""))
    return dict(sorted(counts.items()))


def _normalize_flow(value: Any) -> str:
    text = _clean_text(value) or "approval"
    return _FLOW_ALIASES.get(text, text)


def _normalize_outcome(value: Any) -> str:
    text = _clean_text(value) or ""
    return _OUTCOME_ALIASES.get(text, text)


def _scope_matches(*, actual: str | None, expected: str | None) -> bool:
    normalized_actual = _clean_text(actual)
    normalized_expected = _clean_text(expected)
    if not normalized_actual:
        return False
    if not normalized_expected:
        return True
    return normalized_actual == normalized_expected


def _rationale_is_strong(value: Any, *, min_chars: int) -> bool:
    text = _clean_text(value) or ""
    if len(text) < min_chars:
        return False
    return len([part for part in text.split() if len(part) > 2]) >= 6


def _nonempty_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _change_requests(event: Mapping[str, Any]) -> list[str]:
    value = event.get("change_requests") or event.get("requested_changes")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    count = _int_or_none(event.get("change_request_count"))
    if count is None or count <= 0:
        return []
    return [f"change_request_{index}" for index in range(1, count + 1)]


def _time_spent_seconds(event: Mapping[str, Any]) -> int | None:
    seconds = _number(event.get("time_spent_seconds"))
    if seconds is not None:
        return max(0, int(seconds))
    minutes = _number(
        event.get("time_spent_minutes")
        if "time_spent_minutes" in event
        else event.get("burden_minutes")
    )
    if minutes is None:
        return None
    return max(0, int(minutes * 60))


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _has_private_note(event: Mapping[str, Any]) -> bool:
    return any(_clean_text(event.get(key)) for key in _PRIVATE_KEYS)


def _strip_private_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_private_keys(child)
            for key, child in value.items()
            if str(key) not in _PRIVATE_KEYS
        }
    if isinstance(value, list):
        return [_strip_private_keys(item) for item in value]
    return deepcopy(value)


def _model_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json", exclude_none=True)
        if isinstance(payload, Mapping):
            return payload
    return {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    return text or None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes"}:
            return True
        if text in {"0", "false", "no"}:
            return False
    return None


def _datetime_from(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if isinstance(value, str) and value.strip():
        try:
            return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "DEFAULT_HUMAN_REVIEW_THRESHOLDS",
    "DEFAULT_REVIEW_EFFECTIVENESS_POLICY",
    "HUMAN_REVIEW_CALIBRATION_REPORT_FILENAME",
    "HUMAN_REVIEW_CALIBRATION_REPORT_KIND",
    "HUMAN_REVIEW_CALIBRATION_REPORT_SCHEMA",
    "REVIEW_EFFECTIVENESS_ADR_REF",
    "REVIEW_EFFECTIVENESS_TELEMETRY_SCHEMA_VERSION",
    "HumanReviewCalibrationPersistence",
    "HumanReviewEffectivenessPolicy",
    "HumanReviewThresholds",
    "build_human_review_calibration_report",
    "deterministic_review_fixtures",
    "evaluate_review_packet",
    "human_review_public_export",
    "persist_human_review_calibration_report",
]
