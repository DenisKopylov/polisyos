from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.runtime.http.services.control.artifacts import (
    write_authority_artifact,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
    reconcile_authority_event,
    reconcile_authority_ref,
)
from polisyos.runtime.quality.diagnostic_events import (
    DIAGNOSTIC_EVENT_SCHEMA_NAME,
    DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    DiagnosticEvent,
    DiagnosticEventContractError,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    diagnostic_events,
    runtime_cas_refs,
    scorecard_for,
    sha,
)


def _make_store(tmp_path: Path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def _stores(tmp_path: Path) -> tuple[FileSystemCAS, ControlPlaneStore, RuntimeDiagnosticEventLog]:
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    control_store = _make_store(tmp_path)
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    return artifact_store, control_store, event_log


def _opts(source_ref: str) -> PutOptions:
    return PutOptions(
        kind="scientist.policy_grounding_matrix",
        media_type="application/json",
        schema=SchemaInfo(
            name="polisyos.scientist.PolicyGroundingMatrix",
            version="1.0",
        ),
        producer=ProducerInfo(
            component="polisyos.runtime.quality.policy_grounding_matrix",
            version="2026.05.15+hds-phase5.2",
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[
            InputRef.model_validate(
                {"artifact_id": source_ref, "role": "policy_grounding_input"}
            )
        ],
    )


def _authority_context(
    source_ref: str,
    *,
    run_id: str = "run-phase-52",
    job_id: str = "job-phase-52",
    event_id: str = "evt-phase-52-cas-write",
    closure_sha256: str = "1" * 64,
) -> dict[str, Any]:
    return {
        "evidence_id": "evidence-policy-grounding",
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "owner": "team-runtime",
        "reader_contract": "runtime_quality.policy_grounding.reader",
        "reader_contract_version": "1.0",
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "run_id": run_id,
        "job_id": job_id,
        "trace_id": f"trace-{job_id}",
        "span_id": "span-policy-grounding",
        "parent_span_id": "span-parent",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "phase": "policy_grounding",
        "generated_at": "2026-05-15T09:30:00+00:00",
        "as_of_time": "2026-05-15T09:30:00+00:00",
        "same_input_closure": {
            "closure_id": f"closure-{job_id}",
            "status": "closed",
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "evidence_input_refs": [source_ref],
            "closure_sha256": closure_sha256,
        },
        "input_refs": [source_ref, f"same-input-closure:{closure_sha256}"],
        "effective_mode_ref": sha("2"),
        "degradation_ledger_ref": sha("3"),
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
        "event_id": event_id,
    }


def _diagnostic_event(
    *,
    event_id: str,
    cas_ref: str,
    input_refs: tuple[str, ...] = ("same-input-closure:closed",),
    event_type: str = "polisyos.runtime.diagnostic.cas_write.v1",
    run_id: str = "run-phase-52",
    job_id: str = "job-phase-52",
) -> DiagnosticEvent:
    return DiagnosticEvent(
        event_id=event_id,
        event_source="polisyos.runtime.cas",
        event_type=event_type,
        event_time=datetime(2026, 5, 15, 9, 30, tzinfo=UTC),
        event_subject=f"run/{run_id}/job/{job_id}/phase/policy_grounding",
        schema_name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
        schema_version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
        trace_id=f"trace-{job_id}",
        span_id="span-policy-grounding",
        parent_span_id="span-parent",
        run_id=run_id,
        job_id=job_id,
        tenant_id="tenant-1",
        cell_id="cell-a",
        producer_component="polisyos.runtime.quality.policy_grounding_matrix",
        producer_version="2026.05.15+hds-phase5.2",
        execution_profile="production",
        phase="policy_grounding",
        state_before="running",
        state_after="persisted",
        payload_ref=cas_ref,
        artifact_refs=(cas_ref,),
        input_refs=input_refs,
        blocking_status="non_blocking",
        redaction_policy_ref="redaction-policy/runtime-diagnostics-v1",
        duplicate_of=None,
        dedupe_key=f"{job_id}:policy_grounding:evidence-policy-grounding:cas_write",
        sampling_decision="always_record",
        sampling_rate=1.0,
    )


def _cas_ref_for(payload: dict[str, Any]) -> str:
    digest = content_hash(to_canonical_bytes(payload, CanonSpec()))
    return f"sha256:{digest}"


def test_worker_crash_after_cas_write_before_progress_update_retries_idempotently(
    tmp_path: Path,
) -> None:
    artifact_store, control_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    control_store.create_job(
        job_id="job-crash-after-cas",
        kind="workflow_run",
        run_id="run-crash-after-cas",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _authority_context(
        str(source_ref.artifact_id),
        run_id="run-crash-after-cas",
        job_id="job-crash-after-cas",
        event_id="evt-crash-after-cas",
    )
    observed_refs: list[str] = []

    def _crash_after_cas(job: ControlJobRecord) -> None:
        result = write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **context,
        )
        observed_refs.append(str(result.cas_ref.artifact_id))
        raise RuntimeError("simulated crash before progress update")

    first_worker = ControlWorker(
        store=control_store,
        handler=_crash_after_cas,
        lease_seconds=1,
        poll_interval_s=0.05,
        worker_id="worker-crash",
    )

    with pytest.raises(RuntimeError, match="simulated crash"):
        first_worker.dispatch_once()

    crashed = control_store.get_job("job-crash-after-cas")
    assert crashed is not None
    assert crashed.state == "running"
    assert "policy_grounding_matrix_ref" not in crashed.progress.get("details", {})

    time.sleep(1.2)

    def _retry_same_job(job: ControlJobRecord) -> None:
        result = write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **context,
        )
        cas_ref = str(result.cas_ref.artifact_id)
        observed_refs.append(cas_ref)
        control_store.update_progress_state(
            job_id=job.job_id,
            state="running",
            progress={"details": {"policy_grounding_matrix_ref": cas_ref}},
        )
        control_store.complete_job(
            job_id=job.job_id,
            progress={"details": {"policy_grounding_matrix_ref": cas_ref}},
        )

    retry_worker = ControlWorker(
        store=control_store,
        handler=_retry_same_job,
        lease_seconds=1,
        poll_interval_s=0.05,
        worker_id="worker-retry",
    )

    assert retry_worker.dispatch_once() is True

    completed = control_store.get_job("job-crash-after-cas")
    assert completed is not None
    assert completed.state == "completed"
    assert completed.attempt == 2
    assert observed_refs == [observed_refs[0], observed_refs[0]]

    cas_write_events = [
        record
        for record in event_log.list_events(
            run_id="run-crash-after-cas",
            job_id="job-crash-after-cas",
            limit=100,
        )
        if record.event.event_type == "polisyos.runtime.diagnostic.cas_write.v1"
    ]
    assert len(cas_write_events) == 1
    assert cas_write_events[0].event.payload_ref == observed_refs[0]


def test_progress_update_before_cas_write_blocks_closeout_as_orphan_runtime_ref() -> None:
    runtime_refs = runtime_cas_refs()
    runtime_refs["policy_grounding_matrix_ref"] = (
        "sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    )
    events = [
        event
        for event in diagnostic_events(runtime_refs)
        if event["event_name"] != "policy_grounding_matrix_ref.persisted"
    ]

    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            runtime_refs=runtime_refs,
            details={"diagnostic_events": events},
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_event_reconciliation_failed" in blocking_codes(scorecard)
    assert any(
        failure["layer"] == "runtime_diagnostics"
        and failure["phase"] == "diagnostic_events"
        and "orphan" in failure["message"].casefold()
        for failure in scorecard["blocking_quality_failures"]
    )


def test_diagnostic_event_before_cas_payload_blocks_then_reconciles_after_recovery(
    tmp_path: Path,
) -> None:
    artifact_store, _, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    cas_ref = _cas_ref_for(payload)
    event = _diagnostic_event(event_id="evt-before-cas", cas_ref=cas_ref)

    event_log.append(event)

    with pytest.raises(AuthorityReconciliationError) as missing:
        reconcile_authority_event(
            artifact_store=artifact_store,
            event_log=event_log,
            event_id="evt-before-cas",
        )
    assert missing.value.code == "authority_cas_missing"

    result = write_authority_artifact(
        artifact_store,
        payload,
        _opts(str(source_ref.artifact_id)),
        **_authority_context(
            str(source_ref.artifact_id),
            event_id="evt-before-cas",
        ),
    )

    report = reconcile_authority_event(
        artifact_store=artifact_store,
        event_log=event_log,
        event_id="evt-before-cas",
    )
    assert report.status == "pass"
    assert report.cas_ref == str(result.cas_ref.artifact_id)


def test_cas_payload_before_durable_diagnostic_event_is_orphan_until_event_recovery(
    tmp_path: Path,
) -> None:
    artifact_store, _, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    result = write_authority_artifact(
        artifact_store,
        {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
        _opts(str(source_ref.artifact_id)),
        **_authority_context(
            str(source_ref.artifact_id),
            event_id="evt-after-cas",
        ),
    )

    with pytest.raises(AuthorityReconciliationError) as orphan:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=event_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert orphan.value.code == "authority_orphan_cas"

    event_payload = from_canonical_bytes(
        artifact_store.get_bytes(result.diagnostic_event_ref.artifact_id)
    )
    event_log.append(DiagnosticEvent.model_validate(event_payload))

    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(result.cas_ref.artifact_id),
    )
    assert report.status == "pass"
    assert report.durable_event_id == "evt-after-cas"


def test_stale_lease_takeover_increments_attempt_and_changes_owner(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job-stale-lease",
        kind="workflow_run",
        run_id="run-stale-lease",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    first = store.lease_next_job(worker_id="worker-a", lease_seconds=1)
    assert first is not None
    assert first.lease_owner == "worker-a"
    assert first.attempt == 1

    time.sleep(1.2)

    takeover = store.lease_next_job(worker_id="worker-b", lease_seconds=30)
    assert takeover is not None
    assert takeover.job_id == "job-stale-lease"
    assert takeover.lease_owner == "worker-b"
    assert takeover.attempt == 2
    assert takeover.lease_expires_at is not None
    assert takeover.lease_expires_at > first.lease_expires_at


def test_outbox_events_dedupe_by_topic_and_event_key(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    first = store.enqueue_outbox_event(
        topic="control.job.completed",
        event_key="job-52:job_completed",
        payload={"job_id": "job-52", "state": "completed"},
    )
    duplicate = store.enqueue_outbox_event(
        topic="control.job.completed",
        event_key="job-52:job_completed",
        payload={"job_id": "job-52", "state": "completed"},
    )

    assert duplicate.event_id == first.event_id
    matching = [
        event
        for event in store.list_outbox_events(state=None, limit=50)
        if event.topic == "control.job.completed"
        and event.event_key == "job-52:job_completed"
    ]
    assert len(matching) == 1


def test_duplicate_diagnostic_events_are_idempotent_only_for_full_retry_identity(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    cas_ref = sha("8")
    original = _diagnostic_event(
        event_id="evt-diagnostic-retry",
        cas_ref=cas_ref,
        input_refs=("same-input-closure:aaa",),
    )

    first = store.append_diagnostic_event(
        event=original,
        payload_ref=cas_ref,
        payload_sha256=sha("8"),
    )
    duplicate = store.append_diagnostic_event(
        event=original,
        payload_ref=cas_ref,
        payload_sha256=sha("8"),
    )
    assert duplicate.row_id == first.row_id

    with pytest.raises(DiagnosticEventContractError) as payload_collision:
        store.append_diagnostic_event(
            event=original,
            payload_ref=cas_ref,
            payload_sha256=sha("9"),
        )
    assert payload_collision.value.code == "authority_event_collision"

    closure_drift = original.model_copy(
        update={"input_refs": ("same-input-closure:bbb",)}
    )
    with pytest.raises(DiagnosticEventContractError) as closure_collision:
        store.append_diagnostic_event(
            event=closure_drift,
            payload_ref=cas_ref,
            payload_sha256=sha("8"),
        )
    assert closure_collision.value.code == "authority_event_collision"


def test_failed_lex_fabric_foundry_steps_with_partial_artifacts_emit_typed_blockers() -> None:
    evidence = complete_quality_evidence()
    evidence["normative_evidence"].update(
        {
            "status": "fail",
            "partial_artifact_refs": [sha("1")],
            "issues": [
                {
                    "code": "lex_partial_state_blocker",
                    "phase": "normative_authority",
                    "next_action": "Retry Lex after preserving partial normpack refs.",
                }
            ],
        }
    )
    evidence["fabric_retrieval_trace"].update(
        {
            "status": "fail",
            "partial_artifact_refs": [sha("2")],
            "issues": [
                {
                    "code": "fabric_partial_state_blocker",
                    "phase": "fabric_retrieval",
                    "next_action": "Retry Fabric source selection from the same inputs.",
                }
            ],
        }
    )
    evidence["foundry_method_report"].update(
        {
            "status": "fail",
            "partial_artifact_refs": [sha("3")],
            "issues": [
                {
                    "code": "foundry_partial_state_blocker",
                    "phase": "foundry_methods",
                    "next_action": "Retry Foundry after reconciling partial method refs.",
                }
            ],
        }
    )

    scorecard = scorecard_for(quality_evidence=evidence, normalize=False)
    codes = blocking_codes(scorecard)

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert {
        "lex_partial_state_blocker",
        "fabric_partial_state_blocker",
        "foundry_partial_state_blocker",
    } <= codes
    for failure in scorecard["blocking_quality_failures"]:
        if failure["code"] in {
            "lex_partial_state_blocker",
            "fabric_partial_state_blocker",
            "foundry_partial_state_blocker",
        }:
            assert failure["evidence_ref"]
            assert failure["next_action"]


def test_contradictory_retry_events_become_bounded_reconciliation_or_drift_blockers() -> None:
    runtime_refs = runtime_cas_refs()
    events = diagnostic_events(runtime_refs)
    contradictory_ref = "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    collision = dict(events[0])
    collision["artifact_ref"] = contradictory_ref
    collision["runtime_cas_ref"] = contradictory_ref
    events.append(collision)
    events.append(
        {
            "event_id": "evt-replay-drift-without-explanation",
            "event_name": "replay_manifest_ref.persisted",
            "event_type": "polisyos.runtime.diagnostic.replay_result.v1",
            "severity": "serious",
            "sampling": {"decision": "always_record", "rate": 1.0},
            "artifact_ref": runtime_refs["replay_manifest_ref"],
            "runtime_cas_ref": runtime_refs["replay_manifest_ref"],
            "replay_status": "drifted",
        }
    )

    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            runtime_refs=runtime_refs,
            details={"diagnostic_events": events},
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert {
        "hds_event_reconciliation_failed",
        "authority_replay_drift_unexplained",
    } <= blocking_codes(scorecard)
    bounded = [
        failure
        for failure in scorecard["blocking_quality_failures"]
        if failure["code"]
        in {"hds_event_reconciliation_failed", "authority_replay_drift_unexplained"}
    ]
    assert bounded
    assert all(failure["layer"] == "runtime_diagnostics" for failure in bounded)
    assert all(failure["phase"] == "diagnostic_events" for failure in bounded)
    assert all(failure["next_action"] for failure in bounded)
