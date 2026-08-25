"""Coverage-honest review-effectiveness projection over retained decisions."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationAuditEvent,
    RuntimeAuthorizationOutcome,
)
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionReviewEffectivenessResponse,
)
from polisyos.runtime.http.services.human_decisions import (
    HumanDecisionOperationalResolutionError,
)
from polisyos.runtime.quality.human_review import build_human_review_calibration_report

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.runtime.http.access_audit import RuntimeDataAccessAuditTrail
    from polisyos.runtime.http.services.human_decisions import HumanDecisionService
    from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
        HumanDecisionRecord,
    )

_AUTHORIZATION_EVENT_TYPE = "runtime.authorization.decision"
_CREATE_PERMISSION = "runs.human_decisions.create"
_RECORD_CREATED_OUTCOME = "human_decision_record_created"
_RECORD_RESOURCE_KIND = "runtime.run.human_decision"
_AUTHORIZATION_ROUTE = "/api/v1/runs/{run_id}/human-decisions"


class _RecordCreatedMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: str


class _RecordCreatedAuditPointer(BaseModel):
    """Exact generic-writer shape admitted only as a candidate pointer."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    timestamp: float
    request_id: str
    tenant_id: str
    actor: str
    method: Literal["POST"]
    endpoint: str
    operation: Literal["READ runtime.run.human_decision"]
    resource_kind: Literal["runtime.run.human_decision"]
    resource_id: str
    outcome: Literal["human_decision_record_created"]
    metadata: _RecordCreatedMetadata


@dataclass(frozen=True, slots=True)
class _ResolvedCreation:
    pointer: _RecordCreatedAuditPointer
    record: HumanDecisionRecord


class ReviewEffectivenessService:
    """Reconcile strict audit events with exact signed record readback."""

    def __init__(
        self,
        *,
        trail: RuntimeDataAccessAuditTrail,
        human_decisions: HumanDecisionService | None,
    ) -> None:
        self._trail: RuntimeDataAccessAuditTrail = trail
        self._human_decisions: HumanDecisionService | None = human_decisions

    def for_run(
        self,
        *,
        tenant_id: str,
        run_id: str,
    ) -> HumanDecisionReviewEffectivenessResponse:
        """Return an advisory report whose completeness requires an exact join."""

        scan = self._trail.scan_read_only()
        authorization_events, invalid_authorization_event_count = _authorization_events(
            scan.entries,
            tenant_id=tenant_id,
            run_id=run_id,
        )
        pointers, invalid_record_event_count = _record_pointers(
            scan.entries,
            tenant_id=tenant_id,
        )

        claimed_target_pointers = tuple(
            pointer for pointer in pointers if pointer.metadata.run_id == run_id
        )
        tenant_scope_unknown_record_event_count = invalid_record_event_count
        retained_or_missing_record_count = 0
        resolved_target: list[_ResolvedCreation] = []
        for pointer in pointers:
            if self._human_decisions is None:
                if pointer.metadata.run_id == run_id:
                    retained_or_missing_record_count += 1
                else:
                    tenant_scope_unknown_record_event_count += 1
                continue
            try:
                record = self._human_decisions.read_record(
                    pointer.resource_id,
                    tenant_id=tenant_id,
                    run_id=pointer.metadata.run_id,
                )
            except HumanDecisionOperationalResolutionError:
                if pointer.metadata.run_id == run_id:
                    retained_or_missing_record_count += 1
                else:
                    tenant_scope_unknown_record_event_count += 1
                continue
            if record.run_id != run_id:
                continue
            if not _pointer_matches_record(pointer, record=record, run_id=run_id):
                invalid_record_event_count += 1
                continue
            resolved_target.append(_ResolvedCreation(pointer=pointer, record=record))

        record_ref_counts = Counter(pointer.resource_id for pointer in claimed_target_pointers)
        duplicate_record_event_count = sum(count - 1 for count in record_ref_counts.values())
        exact_join_count, join_counts = _exact_join_count(
            authorization_events,
            resolved_target,
        )
        duplicate_authorization_request_count = join_counts["duplicate_authorization"]
        duplicate_record_request_count = join_counts["duplicate_record"]
        unmatched_authorization_count = join_counts["unmatched_authorization"]
        unmatched_record_event_count = join_counts["unmatched_record"]

        records_by_ref = {
            resolved.record.record_ref: resolved.record for resolved in resolved_target
        }
        records = tuple(records_by_ref.values())
        candidate_count = len(record_ref_counts)
        completed_count = len(records)
        coverage_complete = (
            scan.path_exists
            and scan.audit_read_error_count == 0
            and scan.malformed_json_line_count == 0
            and scan.nonobject_line_count == 0
            and invalid_authorization_event_count == 0
            and invalid_record_event_count == 0
            and tenant_scope_unknown_record_event_count == 0
            and retained_or_missing_record_count == 0
            and duplicate_record_event_count == 0
            and duplicate_authorization_request_count == 0
            and duplicate_record_request_count == 0
            and unmatched_authorization_count == 0
            and unmatched_record_event_count == 0
            and candidate_count > 0
            and exact_join_count
            == len(authorization_events)
            == len(resolved_target)
            == candidate_count
            == completed_count
        )

        report = cast(
            "Mapping[str, object]",
            build_human_review_calibration_report(
                review_events=tuple(_review_event(record) for record in records),
                run_id=run_id,
            ),
        )
        telemetry = cast(
            "Mapping[str, object]",
            report["review_effectiveness_telemetry"],
        )
        raw_threshold_status = telemetry.get("threshold_status")
        threshold_status: Literal["pass", "warn", "fail"] = (
            raw_threshold_status
            if isinstance(raw_threshold_status, str)
            and raw_threshold_status in ("pass", "warn", "fail")
            else "fail"
        )
        advisory_signal_codes = _advisory_signal_codes(telemetry)
        if not coverage_complete:
            threshold_status = "fail"
            advisory_signal_codes.add("human_decision_review_coverage_incomplete")
        if records:
            advisory_signal_codes.add("review_time_not_established")
            if threshold_status == "pass":
                threshold_status = "warn"

        summary = cast("Mapping[str, object]", report["summary"])
        return HumanDecisionReviewEffectivenessResponse(
            run_id=run_id,
            coverage_status="complete" if coverage_complete else "incomplete",
            trail_path_exists=scan.path_exists,
            nonblank_line_count=scan.nonblank_line_count,
            parsed_object_count=scan.parsed_object_count,
            malformed_json_line_count=scan.malformed_json_line_count,
            nonobject_line_count=scan.nonobject_line_count,
            audit_read_error_count=scan.audit_read_error_count,
            authorization_allow_count=len(authorization_events),
            candidate_human_decision_count=candidate_count,
            completed_human_decision_count=completed_count,
            exact_join_count=exact_join_count,
            invalid_authorization_event_count=invalid_authorization_event_count,
            invalid_record_event_count=invalid_record_event_count,
            tenant_scope_unknown_record_event_count=(tenant_scope_unknown_record_event_count),
            unmatched_authorization_count=unmatched_authorization_count,
            unmatched_record_event_count=unmatched_record_event_count,
            duplicate_authorization_request_count=(duplicate_authorization_request_count),
            duplicate_record_request_count=duplicate_record_request_count,
            duplicate_record_event_count=duplicate_record_event_count,
            retained_or_missing_record_count=retained_or_missing_record_count,
            review_count=completed_count,
            approval_count=sum(record.decision_action_exercised == "approve" for record in records),
            override_count=sum(record.decision_mode == "override" for record in records),
            blocking_count=sum(record.decision_mode == "blocking" for record in records),
            dissent_count=sum(bool(record.dissent_statement) for record in records),
            reviewer_independence_rate=_rate(summary.get("reviewer_independence_rate")),
            separation_of_duty_attestation_rate=_rate(
                summary.get("separation_of_duty_attestation_rate")
            ),
            review_time_not_established_count=completed_count,
            threshold_status=threshold_status,
            advisory_signal_codes=tuple(sorted(advisory_signal_codes)),
        )


def _authorization_events(
    entries: Sequence[Mapping[str, object]],
    *,
    tenant_id: str,
    run_id: str,
) -> tuple[tuple[RuntimeAuthorizationAuditEvent, ...], int]:
    events: list[RuntimeAuthorizationAuditEvent] = []
    invalid = 0
    for entry in entries:
        if (
            entry.get("event_type") != _AUTHORIZATION_EVENT_TYPE
            or entry.get("permission") != _CREATE_PERMISSION
            or entry.get("tenant_id") != tenant_id
            or entry.get("resource_id") != run_id
        ):
            continue
        try:
            event = RuntimeAuthorizationAuditEvent.model_validate(entry)
        except ValidationError:
            invalid += 1
            continue
        if not _is_exact_authorization(event, tenant_id=tenant_id, run_id=run_id):
            invalid += 1
            continue
        events.append(event)
    return tuple(events), invalid


def _is_exact_authorization(
    event: RuntimeAuthorizationAuditEvent,
    *,
    tenant_id: str,
    run_id: str,
) -> bool:
    return (
        event.outcome is RuntimeAuthorizationOutcome.ALLOW
        and event.denial_reason == ""
        and event.method == "POST"
        and event.route_path == _AUTHORIZATION_ROUTE
        and event.permission == _CREATE_PERMISSION
        and event.resource_id == run_id
        and _is_sha256_ref(event.resource_digest)
        and event.resource_kind == _RECORD_RESOURCE_KIND
        and event.step_up_class == "human_decision"
        and event.step_up_outcome == "verified"
        and bool(event.subject)
        and event.tenant_id == tenant_id
    )


def _record_pointers(
    entries: Sequence[Mapping[str, object]],
    *,
    tenant_id: str,
) -> tuple[tuple[_RecordCreatedAuditPointer, ...], int]:
    pointers: list[_RecordCreatedAuditPointer] = []
    invalid = 0
    for entry in entries:
        if entry.get("outcome") != _RECORD_CREATED_OUTCOME or entry.get("tenant_id") != tenant_id:
            continue
        try:
            pointer = _RecordCreatedAuditPointer.model_validate(entry)
        except ValidationError:
            invalid += 1
            continue
        if not _is_sha256_ref(pointer.resource_id):
            invalid += 1
            continue
        pointers.append(pointer)
    return tuple(pointers), invalid


def _pointer_matches_record(
    pointer: _RecordCreatedAuditPointer,
    *,
    record: HumanDecisionRecord,
    run_id: str,
) -> bool:
    actor = record.canonical_actor
    return (
        record.schema_version == "policyos.runtime.human_decision_record.v2"
        and record.record_ref == pointer.resource_id
        and record.run_id == pointer.metadata.run_id == run_id
        and pointer.endpoint == f"/api/v1/runs/{run_id}/human-decisions"
        and actor is not None
        and pointer.actor == actor.subject
    )


def _exact_join_count(
    authorization_events: Sequence[RuntimeAuthorizationAuditEvent],
    resolved_creations: Sequence[_ResolvedCreation],
) -> tuple[int, dict[str, int]]:
    authorizations_by_request: dict[str, list[RuntimeAuthorizationAuditEvent]] = defaultdict(list)
    creations_by_request: dict[str, list[_ResolvedCreation]] = defaultdict(list)
    for event in authorization_events:
        authorizations_by_request[event.request_id].append(event)
    for resolved in resolved_creations:
        creations_by_request[resolved.pointer.request_id].append(resolved)

    joined = 0
    for request_id in set(authorizations_by_request) | set(creations_by_request):
        authorization_rows = authorizations_by_request.get(request_id, [])
        creation_rows = creations_by_request.get(request_id, [])
        if len(authorization_rows) != 1 or len(creation_rows) != 1:
            continue
        authorization = authorization_rows[0]
        creation = creation_rows[0]
        actor = creation.record.canonical_actor
        if (
            actor is not None
            and authorization.subject == creation.pointer.actor == actor.subject
            and authorization.tenant_id == creation.pointer.tenant_id
        ):
            joined += 1
    return joined, {
        "duplicate_authorization": sum(
            len(rows) - 1 for rows in authorizations_by_request.values() if len(rows) > 1
        ),
        "duplicate_record": sum(
            len(rows) - 1 for rows in creations_by_request.values() if len(rows) > 1
        ),
        "unmatched_authorization": len(authorization_events) - joined,
        "unmatched_record": len(resolved_creations) - joined,
    }


def _review_event(record: HumanDecisionRecord) -> dict[str, object]:
    receipts = {receipt.predicate: receipt for receipt in record.predicate_receipts or ()}
    separation = receipts.get("reviewer_independence_change")
    flow = "override" if record.decision_mode == "override" else "approval"
    disagreement_reason_code = None
    unresolved = False
    if record.decision_mode == "blocking":
        disagreement_reason_code = "blocking_reason_recorded"
        unresolved = True
    elif record.dissent_statement:
        disagreement_reason_code = "dissent_recorded"
    return {
        "review_id": record.record_id,
        "flow": flow,
        "outcome": record.decision_action_exercised,
        "reviewer_identity": record.actor_ref,
        "reviewer_independent": bool(
            separation is not None
            and separation.satisfied
            and separation.provenance == "independently_reconciled"
        ),
        "separation_of_duty_attested": bool(
            separation is not None
            and separation.satisfied
            and separation.provenance == "independently_reconciled"
        ),
        "decision_ref": record.record_ref,
        "completed_at": (record.recorded_at or record.decided_at).isoformat(),
        "time_spent_seconds": None,
        "review_time_status": "not_established",
        "exposure_order": len(record.exposure_event_refs or ()),
        "dissent": bool(record.dissent_statement),
        "approved_without_change": None,
        "disagreement_reason_code": disagreement_reason_code,
        "unresolved": unresolved,
    }


def _advisory_signal_codes(telemetry: Mapping[str, object]) -> set[str]:
    raw_codes = telemetry.get("advisory_signal_codes")
    if not isinstance(raw_codes, list):
        return set()
    return {value for value in cast("list[object]", raw_codes) if isinstance(value, str)}


def _rate(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _is_sha256_ref(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


__all__ = ["ReviewEffectivenessService"]
