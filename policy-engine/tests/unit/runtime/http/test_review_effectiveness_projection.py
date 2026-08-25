"""Red-first review-effectiveness witnesses over the existing access trail."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.http.access_audit import (
    RuntimeAuthorizationAuditError,
    RuntimeAuthorizationAuditEvent,
    RuntimeAuthorizationOutcome,
    RuntimeDataAccessAuditTrail,
)
from polisyos.runtime.http.services.human_decisions import (
    HumanDecisionOperationalResolutionError,
)
from polisyos.runtime.http.services.review_effectiveness import ReviewEffectivenessService


class _RecordReader:
    def __init__(self, records: dict[str, Any]) -> None:
        self._records = records

    def read_record(self, record_ref: str, *, tenant_id: str, run_id: str) -> Any:
        record = self._records.get(record_ref)
        if record is None or record.run_id != run_id or record.tenant_id != tenant_id:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-ARTIFACT-MISSING")
        return record


def _seed_trail_line(path: Path, entry: dict[str, object]) -> None:
    """Seed bytes as if replaying a previously trusted writer receipt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _record(record_ref: str, *, run_id: str = "run-a") -> Any:
    now = datetime.now(UTC)
    return SimpleNamespace(
        schema_version="policyos.runtime.human_decision_record.v2",
        record_id=f"record-{record_ref[-4:]}",
        record_ref=record_ref,
        tenant_id="tenant-a",
        run_id=run_id,
        canonical_actor=SimpleNamespace(subject="user:reviewer"),
        actor_ref="actor:reviewer",
        decision_action_exercised="approve",
        decision_mode="ordinary",
        dissent_statement=None,
        predicate_receipts=(
            SimpleNamespace(
                predicate="reviewer_independence_change",
                satisfied=True,
                provenance="independently_reconciled",
            ),
        ),
        recorded_at=now,
        decided_at=now,
        exposure_event_refs=("sha256:" + "9" * 64,),
    )


def _allow(request_id: str, *, run_id: str = "run-a") -> RuntimeAuthorizationAuditEvent:
    return RuntimeAuthorizationAuditEvent(
        timestamp=datetime.now(UTC).timestamp(),
        request_id=request_id,
        outcome=RuntimeAuthorizationOutcome.ALLOW,
        denial_reason="",
        method="POST",
        route_path="/api/v1/runs/{run_id}/human-decisions",
        permission="runs.human_decisions.create",
        resource_id=run_id,
        resource_digest="sha256:" + "d" * 64,
        resource_kind="runtime.run.human_decision",
        binding_authority="ownership_verified",
        step_up_class="human_decision",
        step_up_outcome="verified",
        subject="user:reviewer",
        tenant_id="tenant-a",
        principal_type="user",
        opa_policy="runtime.action_permission",
        opa_reasons=[],
    )


def _pointer(request_id: str, record_ref: str, *, run_id: str = "run-a") -> dict[str, object]:
    return {
        "timestamp": datetime.now(UTC).timestamp(),
        "request_id": request_id,
        "tenant_id": "tenant-a",
        "actor": "user:reviewer",
        "method": "POST",
        "endpoint": f"/api/v1/runs/{run_id}/human-decisions",
        "operation": "READ runtime.run.human_decision",
        "resource_kind": "runtime.run.human_decision",
        "resource_id": record_ref,
        "outcome": "human_decision_record_created",
        "metadata": {"run_id": run_id},
    }


def test_review_effectiveness_does_not_count_authorization_allow_as_success(
    runtime_api_env,
) -> None:
    run_id = runtime_api_env["core_run_id"]
    event = RuntimeAuthorizationAuditEvent(
        timestamp=datetime.now(UTC).timestamp(),
        request_id="ds9-authorization-allow",
        outcome=RuntimeAuthorizationOutcome.ALLOW,
        denial_reason="",
        method="POST",
        route_path="/api/v1/runs/{run_id}/human-decisions",
        permission="runs.human_decisions.create",
        resource_id=run_id,
        resource_digest="sha256:" + "d" * 64,
        resource_kind="runtime.run.human_decision",
        binding_authority="ownership_verified",
        step_up_class="human_decision",
        step_up_outcome="verified",
        subject="user:reviewer",
        tenant_id=runtime_api_env["tenant_a"],
        principal_type="user",
        opa_policy="runtime.action_permission",
        opa_reasons=[],
    )
    audit_path = Path(runtime_api_env["cas_root"]) / "runtime" / "audit" / "access.jsonl"
    _seed_trail_line(audit_path, event.model_dump(mode="json"))

    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{run_id}/human-decisions/review-effectiveness"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authorization_allow_count"] == 1
    assert payload["completed_human_decision_count"] == 0
    assert payload["coverage_status"] == "incomplete"


def test_review_effectiveness_surfaces_malformed_or_retained_audit_gap(
    runtime_api_env,
) -> None:
    run_id = runtime_api_env["core_run_id"]
    tenant_id = runtime_api_env["tenant_a"]
    trail = runtime_api_env["client"].app.state.runtime_container.runtime_access_audit
    trail.append(
        {
            "timestamp": datetime.now(UTC).timestamp(),
            "request_id": "ds9-retained-record-pointer",
            "tenant_id": tenant_id,
            "actor": "user:reviewer",
            "method": "POST",
            "endpoint": f"/api/v1/runs/{run_id}/human-decisions",
            "operation": "READ runtime.run.human_decision",
            "resource_kind": "runtime.run.human_decision",
            "resource_id": "sha256:" + "e" * 64,
            "outcome": "human_decision_record_created",
            "metadata": {"run_id": run_id},
        }
    )
    audit_path = Path(runtime_api_env["cas_root"]) / "runtime" / "audit" / "access.jsonl"
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write('{"truncated":')

    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{run_id}/human-decisions/review-effectiveness"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["candidate_human_decision_count"] == 1
    assert payload["completed_human_decision_count"] == 0
    assert payload["retained_or_missing_record_count"] == 1
    assert payload["malformed_json_line_count"] == 1
    assert payload["coverage_status"] == "incomplete"


def test_review_effectiveness_keeps_fail_separate_from_advisory_posture(
    runtime_api_env,
) -> None:
    run_id = runtime_api_env["core_run_id"]

    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{run_id}/human-decisions/review-effectiveness"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["threshold_status"] == "fail"
    assert payload["review_posture"] == "advisory"
    assert payload["blocking_permitted"] is False
    assert payload["report_status_effect"] == "pass_advisory_only"


def test_review_effectiveness_rejects_shaped_fake_authorization_allow(tmp_path: Path) -> None:
    audit_path = tmp_path / "access.jsonl"
    trail = RuntimeDataAccessAuditTrail(path=audit_path)
    record_ref = "sha256:" + "1" * 64
    _seed_trail_line(
        audit_path,
        {
            "event_type": "runtime.authorization.decision",
            "outcome": "allow",
            "permission": "runs.human_decisions.create",
            "tenant_id": "tenant-a",
            "resource_id": "run-a",
        },
    )
    trail.append(_pointer("request-a", record_ref))

    projection = ReviewEffectivenessService(
        trail=trail,
        human_decisions=_RecordReader({record_ref: _record(record_ref)}),
    ).for_run(tenant_id="tenant-a", run_id="run-a")

    assert projection.coverage_status == "incomplete"
    assert projection.invalid_authorization_event_count == 1
    assert projection.exact_join_count == 0


def test_review_effectiveness_requires_request_id_bijection_not_equal_counts(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "access.jsonl"
    trail = RuntimeDataAccessAuditTrail(path=audit_path)
    first_ref = "sha256:" + "2" * 64
    second_ref = "sha256:" + "3" * 64
    _seed_trail_line(
        audit_path,
        _allow("authorization-a").model_dump(mode="json"),
    )
    _seed_trail_line(
        audit_path,
        _allow("authorization-d").model_dump(mode="json"),
    )
    trail.append(_pointer("creation-b", first_ref))
    trail.append(_pointer("creation-c", second_ref))

    projection = ReviewEffectivenessService(
        trail=trail,
        human_decisions=_RecordReader(
            {
                first_ref: _record(first_ref),
                second_ref: _record(second_ref),
            }
        ),
    ).for_run(tenant_id="tenant-a", run_id="run-a")

    assert projection.authorization_allow_count == 2
    assert projection.candidate_human_decision_count == 2
    assert projection.completed_human_decision_count == 2
    assert projection.exact_join_count == 0
    assert projection.unmatched_authorization_count == 2
    assert projection.unmatched_record_event_count == 2
    assert projection.coverage_status == "incomplete"


def test_review_effectiveness_does_not_label_request_age_as_review_time(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "access.jsonl"
    trail = RuntimeDataAccessAuditTrail(path=audit_path)
    record_ref = "sha256:" + "4" * 64
    _seed_trail_line(
        audit_path,
        _allow("request-time").model_dump(mode="json"),
    )
    trail.append(_pointer("request-time", record_ref))

    projection = ReviewEffectivenessService(
        trail=trail,
        human_decisions=_RecordReader({record_ref: _record(record_ref)}),
    ).for_run(tenant_id="tenant-a", run_id="run-a")

    assert projection.coverage_status == "complete"
    assert projection.audit_predicate_provenance == "institutionally_supplied"
    assert projection.coverage_claim_scope == "retained_trail_bytes_only"
    assert "authorization_writer_provenance" in projection.may_not_use_for
    assert projection.review_time_status == "not_established"
    assert projection.review_time_established_count == 0
    assert projection.review_time_not_established_count == 1
    assert projection.measurement_status == "partial"
    assert projection.threshold_scope == "established_signals_only"
    assert projection.threshold_status != "pass"
    assert "review_time_not_established" in projection.advisory_signal_codes

    invalid = projection.model_dump(mode="json")
    invalid["trail_path_exists"] = False
    with pytest.raises(ValueError, match="coverage status contradicts"):
        type(projection).model_validate(invalid)


def test_review_effectiveness_scan_counts_invalid_utf8_as_malformed(tmp_path: Path) -> None:
    audit_path = tmp_path / "access.jsonl"
    trail = RuntimeDataAccessAuditTrail(path=audit_path)
    audit_path.write_bytes(b"\xff\n")

    scan = trail.scan_read_only()

    assert scan.audit_read_error_count == 0
    assert scan.malformed_json_line_count == 1
    assert scan.parsed_object_count == 0


def test_generic_access_append_rejects_fully_shaped_authorization_event(
    tmp_path: Path,
) -> None:
    trail = RuntimeDataAccessAuditTrail(path=tmp_path / "access.jsonl")

    with pytest.raises(RuntimeAuthorizationAuditError, match="sealed writer"):
        trail.append(_allow("forged-request").model_dump(mode="json"))
