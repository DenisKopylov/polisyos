"""Advisory review-effectiveness measurement over human-escalation VOI metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon
from polisyos.scientist.methods.search.voi_models import VOIDecisionRecord, VOIDecisionType

REVIEW_EFFECTIVENESS_REPORT_PUBLIC_SCHEMA_VERSION = (
    "policyos.scientist.review_effectiveness_report.v1"
)
REVIEW_EFFECTIVENESS_REPORT_KIND = "scientist.human_review_effectiveness_report"
REVIEW_EFFECTIVENESS_REPORT_SCHEMA_NAME = (
    "polisyos.scientist.governance.human_review.ReviewEffectivenessReport"
)
REVIEW_EFFECTIVENESS_REPORT_SCHEMA_VERSION = "1.0"

_PRIVATE_KEYS = {
    "private_note",
    "private_notes",
    "reviewer_private_note",
    "reviewer_private_notes",
    "raw_private_notes",
}
_OBSERVED_REVIEW_KEYS = frozenset(
    {
        "review_outcome",
        "outcome",
        "decision",
        "action",
        "reviewer_identity",
        "reviewer_id",
        "reviewer",
        "producer_identity",
        "producer_id",
        "producer",
        "time_spent_seconds",
        "review_time_seconds",
        "time_spent_minutes",
        "burden_minutes",
        "separation_of_duty_attested",
        "producer_independence_attested",
        "reviewer_independent",
        "independent_from_producer",
        "dissent",
        "change_requests",
        "requested_changes",
        "change_request_count",
        "approved_without_change",
        "no_delta_review",
        "override_correct",
    }
)

_ACTION_TO_OUTCOME = {
    "approve": "approve",
    "approved": "approve",
    "reject": "reject",
    "rejected": "reject",
    "request_rerun": "reissue",
    "rerun_requested": "reissue",
    "override": "override",
    "overridden": "override",
    "explanation_insufficient": "reject",
    "interrupt_release": "withdraw",
}


def build_human_review_calibration_report(
    *,
    review_events: Sequence[Mapping[str, Any]],
    run_id: str | None = None,
    now: datetime | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the advisory telemetry shape consumed by review effectiveness.

    Runtime remains the persistence owner for human-review quality evidence.
    Scientist only needs this read-only measurement contract to avoid importing
    runtime orchestration from governance-side validation code.
    """

    _ = thresholds
    generated_at = _utc(now)
    event_count = len(review_events)
    review_seconds = [
        seconds
        for event in review_events
        for seconds in [_time_spent_seconds(event)]
        if seconds is not None
    ]
    override_count = sum(1 for event in review_events if event.get("outcome") == "override")
    no_delta_count = sum(1 for event in review_events if bool(event.get("approved_without_change")))
    separation_failures = sum(
        1
        for event in review_events
        if not bool(event.get("separation_of_duty_attested"))
        or (
            _text(event.get("reviewer_identity")) is not None
            and _text(event.get("reviewer_identity")) == _text(event.get("producer_identity"))
        )
        or event.get("reviewer_independent") is False
    )
    low_time_count = sum(1 for seconds in review_seconds if seconds < 60)
    average_seconds = sum(review_seconds) / len(review_seconds) if review_seconds else 0.0
    measured = {
        "review_count": event_count,
        "review_time_seconds_average": average_seconds,
        "low_time_review_count": low_time_count,
        "override_count": override_count,
        "override_rate": override_count / event_count if event_count else 0.0,
        "no_delta_review_count": no_delta_count,
        "separation_of_duty_failure_count": separation_failures,
    }
    quality_signals: list[dict[str, Any]] = []
    if event_count and measured["override_rate"] > 0:
        quality_signals.append(
            {
                "code": "override_rate_above_warn_threshold",
                "status": "warn",
                "message": "Human-review override rate is above the advisory warning threshold.",
                "measured_value": measured["override_rate"],
            }
        )
    if separation_failures:
        quality_signals.append(
            {
                "code": "separation_of_duty_below_fail_threshold",
                "status": "fail",
                "message": "Human-review separation of duty fell below the advisory floor.",
                "measured_value": separation_failures,
            }
        )
    threshold_status = "fail" if any(s["status"] == "fail" for s in quality_signals) else "pass"
    return {
        "schema_version": "policyos.runtime.quality.human_review_calibration_report.v1",
        "status": "pass",
        "run_id": run_id,
        "generated_at": generated_at.isoformat(),
        "threshold_status": threshold_status,
        "review_effectiveness_telemetry": {
            "posture": "advisory",
            "threshold_status": threshold_status,
            "blocking_permitted": False,
            "report_status_effect": "pass_advisory_only",
            "authority_boundary": {
                "may_not_use_for": [
                    "current_run_closeout_block",
                    "publication_block",
                    "claim_support_downgrade",
                ]
            },
            "measured_signals": measured,
        },
        "quality_signals": quality_signals,
    }


class ReviewEffectivenessAdvisoryNote(BaseModel):
    """Non-blocking note emitted by the review-effectiveness measurement bridge."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: Literal["info", "warn", "fail"] = "warn"
    message: str = Field(min_length=1)
    blocking: Literal[False] = False
    authority_effect: Literal["advisory_measurement"] = "advisory_measurement"
    source_decision_ids: list[str] = Field(default_factory=list)
    signal: dict[str, Any] | None = None


class ReviewEffectivenessReport(BaseModel):
    """Scientist-facing advisory report for review-effectiveness telemetry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.scientist.review_effectiveness_report.v1"] = (
        REVIEW_EFFECTIVENESS_REPORT_PUBLIC_SCHEMA_VERSION
    )
    generated_at: datetime
    status: Literal["pass"] = "pass"
    run_id: str | None = None
    threshold_status: str = Field(min_length=1)
    measured_event_count: int = Field(ge=0)
    source_decision_ids: list[str] = Field(default_factory=list)
    observation_gap_decision_ids: list[str] = Field(default_factory=list)
    ignored_decision_ids: list[str] = Field(default_factory=list)
    review_time_distribution_seconds: dict[str, Any] = Field(default_factory=dict)
    review_effectiveness_telemetry: dict[str, Any] = Field(default_factory=dict)
    quality_signals: list[dict[str, Any]] = Field(default_factory=list)
    advisory_notes: list[ReviewEffectivenessAdvisoryNote] = Field(default_factory=list)
    authority_boundary: dict[str, list[str]] = Field(default_factory=dict)
    calibration_report: dict[str, Any] = Field(default_factory=dict)
    bridge_summary: dict[str, Any] = Field(default_factory=dict)


def build_review_effectiveness_report(
    *,
    voi_decisions: Sequence[VOIDecisionRecord],
    run_id: str | None = None,
    now: datetime | None = None,
    thresholds: object | None = None,
) -> ReviewEffectivenessReport:
    """Measure review effectiveness from human-escalation VOI metadata.

    The report is advisory-only under ADR-0171. Threshold failures remain visible
    as quality signals and advisory notes, but the returned report status never
    becomes a current-run closeout or publication blocker.

    Args:
        voi_decisions: VOI decision records that may contain human-escalation
            review observation metadata.
        run_id: Optional run id to stamp on the generated runtime calibration
            report. When omitted, a shared run id is inferred when possible.
        now: Optional generation timestamp.
        thresholds: Optional runtime human-review thresholds object supplied by
            governed configuration. When omitted, runtime defaults apply.

    Returns:
        Advisory review-effectiveness report with runtime telemetry, notes, and
        public/audit boundary fields.
    """

    generated_at = _utc(now)
    review_events: list[dict[str, Any]] = []
    source_decision_ids: list[str] = []
    observation_gap_decision_ids: list[str] = []
    ignored_decision_ids: list[str] = []
    resolved_run_id = run_id or _single_run_id(voi_decisions)

    for decision in voi_decisions:
        if decision.decision_type is not VOIDecisionType.HUMAN_ESCALATION:
            ignored_decision_ids.append(decision.decision_id)
            continue
        if not _has_observed_review_metadata(decision.metadata):
            observation_gap_decision_ids.append(decision.decision_id)
            continue
        review_events.append(_event_from_voi_decision(decision))
        source_decision_ids.append(decision.decision_id)

    if thresholds is None:
        calibration_report = build_human_review_calibration_report(
            review_events=review_events,
            run_id=resolved_run_id,
            now=generated_at,
        )
    else:
        calibration_report = build_human_review_calibration_report(
            review_events=review_events,
            run_id=resolved_run_id,
            now=generated_at,
            thresholds=thresholds,
        )
    telemetry = dict(calibration_report.get("review_effectiveness_telemetry") or {})
    quality_signals = [
        dict(signal) for signal in calibration_report.get("quality_signals", [])
    ]
    advisory_notes = _advisory_notes(
        quality_signals=quality_signals,
        observation_gap_decision_ids=observation_gap_decision_ids,
        source_decision_ids=source_decision_ids,
    )
    authority_boundary = _authority_boundary(telemetry)

    return ReviewEffectivenessReport(
        generated_at=generated_at,
        run_id=resolved_run_id,
        threshold_status=str(telemetry.get("threshold_status") or "pass"),
        measured_event_count=len(review_events),
        source_decision_ids=sorted(source_decision_ids),
        observation_gap_decision_ids=sorted(observation_gap_decision_ids),
        ignored_decision_ids=sorted(ignored_decision_ids),
        review_time_distribution_seconds=_review_time_distribution(review_events),
        review_effectiveness_telemetry=telemetry,
        quality_signals=quality_signals,
        advisory_notes=advisory_notes,
        authority_boundary=authority_boundary,
        calibration_report=dict(calibration_report),
        bridge_summary={
            "reuse_classification": "wire_existing",
            "source": "VOIDecisionRecord.metadata",
            "producer": (
                "polisyos.scientist.governance.human_review.effectiveness."
                "build_review_effectiveness_report"
            ),
            "runtime_measurement_consumer": (
                "polisyos.runtime.quality.human_review."
                "build_human_review_calibration_report"
            ),
            "surface": "review_effectiveness_public_export",
            "capability_state": "implemented_advisory",
        },
    )


def review_effectiveness_public_export(
    report: ReviewEffectivenessReport | Mapping[str, Any],
) -> dict[str, Any]:
    """Return a private-note-free public/audit projection of the report.

    Args:
        report: Review-effectiveness report model or report-shaped mapping.

    Returns:
        JSON-compatible public projection with reviewer private note keys
        recursively removed.
    """

    payload = (
        report.model_dump(mode="json", exclude_none=True)
        if isinstance(report, ReviewEffectivenessReport)
        else dict(report)
    )
    stripped = _strip_private_keys(payload)
    return dict(stripped) if isinstance(stripped, Mapping) else {}


def persist_review_effectiveness_report(
    store: artifacts.FileSystemCAS,
    report: ReviewEffectivenessReport,
) -> artifacts.ArtifactRef:
    """Persist a review-effectiveness report in the shared CAS.

    Args:
        store: File-system CAS used by Scientist governance artifacts.
        report: Advisory review-effectiveness report to persist.

    Returns:
        Artifact reference for the persisted report.
    """

    return store.put_json(
        review_effectiveness_public_export(report),
        artifacts.PutOptions(
            kind=REVIEW_EFFECTIVENESS_REPORT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=REVIEW_EFFECTIVENESS_REPORT_SCHEMA_NAME,
                version=REVIEW_EFFECTIVENESS_REPORT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def load_review_effectiveness_report(
    store: artifacts.FileSystemCAS,
    ref: artifacts.ArtifactRef,
) -> ReviewEffectivenessReport:
    """Load a persisted review-effectiveness report from CAS.

    Args:
        store: File-system CAS containing the report payload.
        ref: Artifact reference returned by `persist_review_effectiveness_report`.

    Returns:
        Validated review-effectiveness report.
    """

    return ReviewEffectivenessReport.model_validate(
        canon.from_canonical_bytes(store.get_bytes(ref.artifact_id))
    )


def _event_from_voi_decision(decision: VOIDecisionRecord) -> dict[str, Any]:
    metadata = decision.metadata
    outcome = _review_outcome(metadata)
    event: dict[str, Any] = {
        "review_id": _text(metadata.get("review_id")) or decision.decision_id,
        "flow": _text(metadata.get("review_flow") or metadata.get("flow"))
        or ("override" if outcome == "override" else "escalation"),
        "outcome": outcome,
        "expected_outcome": _review_outcome(
            {"outcome": metadata.get("expected_outcome")}
        ),
        "reviewer_identity": _text(
            metadata.get("reviewer_identity")
            or metadata.get("reviewer_id")
            or metadata.get("reviewer")
        ),
        "producer_identity": _text(
            metadata.get("producer_identity")
            or metadata.get("producer_id")
            or metadata.get("producer")
        ),
        "reviewer_independent": _bool_or_none(
            metadata.get("reviewer_independent")
            if "reviewer_independent" in metadata
            else metadata.get("independent_from_producer")
        ),
        "separation_of_duty_attested": _bool_or_none(
            metadata.get("separation_of_duty_attested")
            if "separation_of_duty_attested" in metadata
            else metadata.get("producer_independence_attested")
        ),
        "time_spent_seconds": metadata.get(
            "time_spent_seconds",
            metadata.get("review_time_seconds"),
        ),
        "time_spent_minutes": metadata.get("time_spent_minutes"),
        "burden_minutes": metadata.get("burden_minutes"),
        "dissent": _bool_or_none(metadata.get("dissent")) or False,
        "change_requests": metadata.get(
            "change_requests",
            metadata.get("requested_changes"),
        ),
        "change_request_count": metadata.get("change_request_count"),
        "approved_without_change": _approved_without_change(metadata),
        "override_correct": _bool_or_none(metadata.get("override_correct")),
        "decision_ref": _text(metadata.get("decision_ref")),
        "packet_ref": _text(metadata.get("packet_ref")),
        "completed_at": _text(metadata.get("completed_at")),
        "disagreement_reason_code": _text(metadata.get("disagreement_reason_code")),
        "escalation_threshold": _text(metadata.get("escalation_threshold")),
        "unresolved": _bool_or_none(metadata.get("unresolved")) or False,
    }
    for key in _PRIVATE_KEYS:
        if key in metadata:
            event[key] = metadata[key]
    return {key: value for key, value in event.items() if value not in (None, "")}


def _has_observed_review_metadata(metadata: Mapping[str, Any]) -> bool:
    return any(_present(metadata.get(key)) for key in _OBSERVED_REVIEW_KEYS)


def _advisory_notes(
    *,
    quality_signals: Sequence[Mapping[str, Any]],
    observation_gap_decision_ids: Sequence[str],
    source_decision_ids: Sequence[str],
) -> list[ReviewEffectivenessAdvisoryNote]:
    notes: list[ReviewEffectivenessAdvisoryNote] = []
    for signal in quality_signals:
        status = str(signal.get("status") or "warn")
        if status not in {"warn", "fail"}:
            continue
        notes.append(
            ReviewEffectivenessAdvisoryNote(
                code=str(signal.get("code") or "review_effectiveness_signal"),
                severity="fail" if status == "fail" else "warn",
                message=str(signal.get("message") or "Review telemetry signal emitted."),
                source_decision_ids=sorted(source_decision_ids),
                signal=dict(signal),
            )
        )
    if observation_gap_decision_ids:
        notes.append(
            ReviewEffectivenessAdvisoryNote(
                code="review_effectiveness_observation_missing",
                severity="warn",
                message=(
                    "Human-escalation VOI metadata requested review but did not "
                    "include observed review outcome, reviewer, challenge, time, or "
                    "separation-of-duty fields."
                ),
                source_decision_ids=sorted(observation_gap_decision_ids),
            )
        )
    return notes


def _review_time_distribution(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = sorted(
        seconds
        for event in events
        if (seconds := _time_spent_seconds(event)) is not None
    )
    if not values:
        return {
            "sample_count": 0,
            "minimum": None,
            "maximum": None,
            "buckets": {
                "lt_60": 0,
                "60_to_119": 0,
                "120_to_299": 0,
                "gte_300": 0,
            },
        }
    return {
        "sample_count": len(values),
        "minimum": values[0],
        "maximum": values[-1],
        "buckets": {
            "lt_60": sum(1 for value in values if value < 60),
            "60_to_119": sum(1 for value in values if 60 <= value < 120),
            "120_to_299": sum(1 for value in values if 120 <= value < 300),
            "gte_300": sum(1 for value in values if value >= 300),
        },
    }


def _time_spent_seconds(event: Mapping[str, Any]) -> int | None:
    seconds = _int_or_none(event.get("time_spent_seconds"))
    if seconds is not None:
        return max(0, seconds)
    minutes = _number_or_none(
        event.get("time_spent_minutes")
        if "time_spent_minutes" in event
        else event.get("burden_minutes")
    )
    if minutes is None:
        return None
    return max(0, int(minutes * 60))


def _authority_boundary(telemetry: Mapping[str, Any]) -> dict[str, list[str]]:
    boundary = telemetry.get("authority_boundary")
    if isinstance(boundary, Mapping):
        return {
            "authoritative_for": _string_list(boundary.get("authoritative_for")),
            "may_not_use_for": _string_list(boundary.get("may_not_use_for")),
        }
    return {
        "authoritative_for": [
            "review_effectiveness_measurement",
            "future_policy_calibration",
            "reviewer_load_observability",
        ],
        "may_not_use_for": [
            "current_run_closeout_block",
            "publication_block",
            "claim_support_downgrade",
        ],
    }


def _review_outcome(metadata: Mapping[str, Any]) -> str | None:
    raw = (
        metadata.get("review_outcome")
        or metadata.get("outcome")
        or metadata.get("decision")
        or metadata.get("action")
    )
    text = _text(raw)
    if text is None:
        return None
    return _ACTION_TO_OUTCOME.get(text, text)


def _approved_without_change(metadata: Mapping[str, Any]) -> bool | None:
    explicit = _bool_or_none(metadata.get("approved_without_change"))
    if explicit is not None:
        return explicit
    no_delta = _bool_or_none(metadata.get("no_delta_review"))
    if no_delta is not None:
        return no_delta
    return None


def _single_run_id(decisions: Sequence[VOIDecisionRecord]) -> str | None:
    run_ids = {decision.run_id for decision in decisions}
    if len(run_ids) == 1:
        return next(iter(run_ids))
    return None


def _strip_private_keys(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_private_keys(child)
            for key, child in value.items()
            if str(key) not in _PRIVATE_KEYS
        }
    if isinstance(value, list):
        return [_strip_private_keys(item) for item in value]
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set | dict):
        return bool(value)
    return True


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    return text or None


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().casefold()
        if text in {"1", "true", "yes"}:
            return True
        if text in {"0", "false", "no"}:
            return False
    return None


def _int_or_none(value: object) -> int | None:
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


def _number_or_none(value: object) -> float | None:
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


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "REVIEW_EFFECTIVENESS_REPORT_KIND",
    "REVIEW_EFFECTIVENESS_REPORT_PUBLIC_SCHEMA_VERSION",
    "REVIEW_EFFECTIVENESS_REPORT_SCHEMA_NAME",
    "REVIEW_EFFECTIVENESS_REPORT_SCHEMA_VERSION",
    "ReviewEffectivenessAdvisoryNote",
    "ReviewEffectivenessReport",
    "build_review_effectiveness_report",
    "load_review_effectiveness_report",
    "persist_review_effectiveness_report",
    "review_effectiveness_public_export",
]
