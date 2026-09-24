"""Behavioral witnesses for candidate response custody and the WP-08 refusal."""

from __future__ import annotations

import importlib
import importlib.util
import json
import multiprocessing
import os
import signal
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


def _api():
    name = "polisyos.runtime.quality.adaptation_transition"
    assert importlib.util.find_spec(name) is not None, "CR1 durable candidate runtime is absent"
    return importlib.import_module(name)


def _request(api):
    return api.AdaptationTransitionRequest(
        request_id="operator-request-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
        contract_ref="candidate-monitoring-contract-1",
        signal_refs=("candidate-health-signal-1",),
        diagnosis_refs=(),
        observed_at=datetime(2026, 9, 9, 20, tzinfo=UTC),
        current_context={"E": "unknown", "X": "unknown", "V": "unknown", "C": "unknown"},
        requested_context={"E": "unknown", "X": "review", "V": "unknown", "C": "unknown"},
        charter=api.CandidateOperationCharter(
            action_description="Review protective response candidate after hours",
            required_signer_role="appointed_policy_rollback_authority",
            escalation_after_seconds=60,
            provenance_refs=("OPS-R5:FM-OPS-16",),
        ),
        intended_claim_consequence="withhold any protected-action authorization",
        provenance_refs=("test-independent-operator",),
    )


def _runtime(api, root: Path):
    return api.AdaptationTransitionRuntime.open(
        root=root, tenant_id="tenant-1", cell_id="cell-1"
    )


def test_unsigned_request_fails_safe_and_names_role(tmp_path: Path) -> None:
    """WP-08: persisted absence creates posture and clock, never a signer."""
    api = _api()
    runtime = _runtime(api, tmp_path)
    ticket = runtime.submit(_request(api))
    decision = runtime.process(ticket)
    assert decision.status == "failed_safe"
    assert decision.missing_role == "appointed_policy_rollback_authority"
    assert decision.appointed_signer is None
    assert decision.execution_authorized is False
    assert decision.conservative_posture == "no_authority_expansion"
    snapshot = runtime.snapshot(ticket, as_of=datetime.now(UTC) + timedelta(minutes=2))
    assert snapshot.status == "failed_safe"
    assert snapshot.escalation_due is True
    assert snapshot.appointed_signer is None
    assert snapshot.execution_authorized is False
    assert snapshot.authority_boundary.posture == "shadow"


def test_conflicting_duplicate_cannot_replace_original_request(tmp_path: Path) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    request = _request(api)
    ticket = runtime.submit(request)
    assert runtime.submit(request) == ticket
    with pytest.raises(ValueError, match="request_identity_conflict"):
        runtime.submit(request.model_copy(update={"contract_ref": "different-contract"}))
    assert runtime.process(ticket).missing_role == request.charter.required_signer_role


def test_concurrent_duplicate_delivery_has_one_publication(tmp_path: Path) -> None:
    api = _api()
    first, second = _runtime(api, tmp_path), _runtime(api, tmp_path)
    request = _request(api)
    barrier = threading.Barrier(2)

    def submit(runtime):
        barrier.wait()
        ticket = runtime.submit(request)
        runtime.process(ticket)
        return ticket

    with ThreadPoolExecutor(max_workers=2) as pool:
        tickets = list(pool.map(submit, (first, second)))
    assert tickets[0] == tickets[1]
    _assert_one_publication(tmp_path)


def test_concurrent_conflicting_requests_have_one_admitted_content(tmp_path: Path) -> None:
    api = _api()
    runtimes = [_runtime(api, tmp_path), _runtime(api, tmp_path)]
    request = _request(api)
    requests = [request, request.model_copy(update={"contract_ref": "competing-content"})]
    barrier = threading.Barrier(2)

    def submit(index):
        barrier.wait()
        try:
            return runtimes[index].submit(requests[index])
        except ValueError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, [0, 1]))
    errors = [result for result in results if isinstance(result, ValueError)]
    assert len(errors) == 1
    assert str(errors[0]) == "request_identity_conflict"
    ticket = next(result for result in results if isinstance(result, str))
    runtimes[0].process(ticket)
    _assert_one_publication(tmp_path)


def _assert_one_publication(root: Path) -> None:
    with sqlite3.connect(root / "control.sqlite") as connection:
        rows = connection.execute(
            "SELECT payload_json FROM control_outbox_events WHERE topic = ?",
            ("polisyos.runtime.adaptation.decision.v1",),
        ).fetchall()
        request_rows = connection.execute(
            "SELECT event_id FROM control_outbox_events WHERE topic = ?",
            ("polisyos.runtime.adaptation.request.v1",),
        ).fetchall()
    assert len(rows) == 1  # Complete SQL result, no LIMIT or owner-produced summary.
    assert len(request_rows) == 1
    manifests = [json.loads(path.read_text()) for path in (root / "cas").rglob("*.manifest.json")]
    decisions = {
        manifest["artifact_id"] for manifest in manifests
        if manifest["kind"] == "runtime.adaptation_decision_record"
    }
    assert decisions == {json.loads(rows[0][0])["artifact_ref"]}
    sys.stdout.write(json.dumps({
        "complete_sql_request_count": len(request_rows),
        "complete_sql_decision_count": len(rows),
        "independent_cas_decision_refs": sorted(decisions),
        "request_ticket": request_rows[0][0],
    }) + "\n")
    api = _api()
    runtime = _runtime(api, root)
    snapshot = runtime.snapshot(request_rows[0][0], as_of=datetime.now(UTC))
    assert snapshot.decision_ref == json.loads(rows[0][0])["artifact_ref"]
    assert snapshot.status == "failed_safe"


def _interrupted_worker(root: Path, ticket: str, boundary: str, ready) -> None:
    api = _api()
    runtime = _runtime(api, root)
    original = getattr(runtime, boundary)

    def pause(*args, **kwargs):
        if boundary == "_checkpoint":
            # Real decision publication has committed; its checkpoint has not.
            ready.send(os.getpid())
            signal.pause()
        result = original(*args, **kwargs)
        if boundary == "_read_request":
            ready.send(os.getpid())
            signal.pause()
        return result

    setattr(runtime, boundary, pause)
    runtime.process(ticket)


@pytest.mark.parametrize("boundary", ["_read_request", "_checkpoint"])
def test_actual_sigkill_and_duplicate_preserve_single_custody_publication(
    tmp_path: Path, boundary: str
) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    request = _request(api)
    ticket = runtime.submit(request)
    context = multiprocessing.get_context("fork")
    receive, send = context.Pipe(duplex=False)
    worker = context.Process(target=_interrupted_worker, args=(tmp_path, ticket, boundary, send))
    worker.start()
    try:
        assert receive.poll(30), "worker never reached actual durable boundary"
        pid = receive.recv()
        assert pid == worker.pid
        os.kill(pid, signal.SIGKILL)
        worker.join(timeout=30)
        assert worker.exitcode == -signal.SIGKILL
        sys.stdout.write(json.dumps({
            "killed_pid": pid, "boundary": boundary, "exitcode": worker.exitcode,
            "request_ticket": ticket,
        }) + "\n")
    finally:
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=5)
        receive.close()
        send.close()
    recovered = _runtime(api, tmp_path)
    decision = recovered.process(ticket)
    assert recovered.submit(request) == ticket  # Actual duplicate delivery after restart.
    assert recovered.process(ticket) == decision
    _assert_one_publication(tmp_path)


def test_forged_signer_and_boundary_fail_at_consumer(tmp_path: Path) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    request = _request(api)
    forged = request.charter.model_copy(update={"appointed_signer": "system"})
    with pytest.raises(ValueError):
        runtime.submit(request.model_copy(update={"charter": forged}))
    widened = request.authority_boundary.model_copy(update={"posture": "production"})
    with pytest.raises(ValueError, match="candidate_authority_boundary_required"):
        runtime.submit(request.model_copy(update={"authority_boundary": widened}))


def test_corrupt_persisted_request_fails_closed(tmp_path: Path) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    ticket = runtime.submit(_request(api))
    with sqlite3.connect(tmp_path / "control.sqlite") as connection:
        payload = json.loads(connection.execute(
            "SELECT payload_json FROM control_outbox_events WHERE event_id = ?", (ticket,)
        ).fetchone()[0])
    digest = payload["artifact_ref"].removeprefix("sha256:")
    blob = tmp_path / "cas/artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    blob.write_text('{"appointed_signer":"system"}')
    with pytest.raises((ValueError, RuntimeError)):
        runtime.process(ticket)


def test_corrupt_decision_and_unknown_topic_fail_at_audit_reader(tmp_path: Path) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    unrelated = runtime._store.enqueue_outbox_event(
        topic="unrelated-owner", event_key="fake", payload={"artifact_ref": "fake"}
    )
    with pytest.raises(ValueError, match="request_receipt_missing"):
        runtime.process(unrelated.event_id)
    ticket = runtime.submit(_request(api))
    runtime.process(ticket)
    snapshot = runtime.snapshot(ticket, as_of=datetime.now(UTC))
    digest = snapshot.decision_ref.removeprefix("sha256:")
    blob = tmp_path / "cas/artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    blob.write_text('{"execution_authorized":true}')
    with pytest.raises(ValueError):
        runtime.snapshot(ticket, as_of=datetime.now(UTC))


def test_restart_is_bound_candidate_evidence_and_never_reopens(tmp_path: Path) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    ticket = runtime.submit(_request(api))
    runtime.process(ticket)
    snapshot = runtime.snapshot(ticket, as_of=datetime.now(UTC))
    restart = api.RestartEvidenceRecord(
        prior_decision_ref=snapshot.decision_ref,
        repair_ref="external-repair-candidate-1",
        test_refs=("bounded-probe-candidate-1",),
        measurement_health_ref="measurement-health-candidate-1",
        residual_harm_refs=("unquantified-harm-1",),
        historical_claim_status="withheld",
        observed_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        provenance_refs=("external-candidate-evidence",),
    )
    restart_ref = runtime.record_restart(ticket, restart)
    replay = _runtime(api, tmp_path).snapshot(
        ticket, as_of=datetime.now(UTC), restart_ref=restart_ref
    )
    assert replay.restart_ref == restart_ref
    assert replay.status == "failed_safe" and replay.execution_authorized is False
    with pytest.raises(ValueError, match="restart_decision_mismatch"):
        runtime.record_restart(ticket, restart.model_copy(update={"prior_decision_ref": "other"}))


def test_snapshot_refuses_future_decision_and_request_observation(tmp_path, monkeypatch) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    store_module = importlib.import_module("polisyos.runtime.http.services.control_plane_store")
    t0 = datetime.now(UTC) - timedelta(hours=2)
    clock = [t0]
    monkeypatch.setattr(store_module, "_utc_now", lambda: clock[0])
    ticket = runtime.submit(_request(api))
    clock[0] = t0 + timedelta(minutes=1)
    runtime.process(ticket)
    with pytest.raises(ValueError, match="decision_not_available_as_of"):
        runtime.snapshot(ticket, as_of=t0 + timedelta(seconds=30))
    future = _request(api).model_copy(update={
        "request_id": "future-observation", "observed_at": t0 + timedelta(days=1),
    })
    future_ticket = runtime.submit(future)
    with pytest.raises(ValueError, match="request_observation_after_snapshot"):
        runtime.snapshot(future_ticket, as_of=t0 + timedelta(minutes=2))


def test_restart_projection_distinguishes_availability_and_expiry(tmp_path, monkeypatch) -> None:
    api = _api()
    runtime = _runtime(api, tmp_path)
    store_module = importlib.import_module("polisyos.runtime.http.services.control_plane_store")
    t0 = datetime.now(UTC) - timedelta(hours=2)
    clock = [t0]
    monkeypatch.setattr(store_module, "_utc_now", lambda: clock[0])
    ticket = runtime.submit(_request(api))
    runtime.process(ticket)
    snapshot = runtime.snapshot(ticket, as_of=t0)
    restart = api.RestartEvidenceRecord(
        prior_decision_ref=snapshot.decision_ref,
        repair_ref="candidate-repair", test_refs=("candidate-test",),
        measurement_health_ref="candidate-health", residual_harm_refs=("unknown",),
        historical_claim_status="withheld", observed_at=t0 + timedelta(minutes=1),
        expires_at=t0 + timedelta(hours=1), provenance_refs=("external-candidate",),
    )
    clock[0] = t0 + timedelta(minutes=2)
    restart_ref = runtime.record_restart(ticket, restart)
    with pytest.raises(ValueError, match="restart_evidence_not_available_as_of"):
        runtime.snapshot(ticket, as_of=t0 + timedelta(seconds=30), restart_ref=restart_ref)
    current = runtime.snapshot(ticket, as_of=t0 + timedelta(minutes=3), restart_ref=restart_ref)
    expired = runtime.snapshot(ticket, as_of=t0 + timedelta(hours=2), restart_ref=restart_ref)
    assert current.restart_disposition == "current_candidate"
    assert expired.restart_disposition == "expired_candidate"
    assert current.status == expired.status == "failed_safe"
    assert current.execution_authorized is expired.execution_authorized is False
