"""A timed-out real DS9 writer retains its fence and may commit after acknowledgement loss."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from polisyos.core import canon
from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.http.services.human_decisions import HumanDecisionPersistenceError
from tests.unit.runtime.http import test_human_decision_service as cases


def test_guarded_ds9_timeout_retains_fence_until_late_signed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = cases._signed_current_gate_fixture(tmp_path)
    sink = fixture.service.authority_sink
    raw_store = sink._reservation_store
    guarded = guard_runtime_control_store(raw_store)
    sink._reservation_store = guarded
    sink._event_log._store = guarded
    paused, release, worker_finished = Event(), Event(), Event()
    recovery_started, recovery_finished, contender_entered = Event(), Event(), Event()
    captured = {}
    original_sign = type(sink).sign_artifact
    original_operation = type(sink).run_custody_operation
    original_recovery = raw_store.mark_human_decision_recovery_required
    original_reserve = raw_store._reserve_human_decision_sqlite

    def pause_signed_writer(owner, ref, signer, *, signer_identity):
        signature = original_sign(owner, ref, signer, signer_identity=signer_identity)
        if owner is sink:
            assert raw_store._human_decision_transaction.active is True
            raw = fixture.store.get_bytes(ref)
            captured.update(ref=ref, raw=raw, record=canon.from_canonical_bytes(raw))
            paused.set()
            assert release.wait(30), "test did not release the signed writer"
        return signature

    def observe_operation(owner, operation):
        def completed():
            try:
                return operation()
            finally:
                worker_finished.set()

        return original_operation(owner, completed if owner is sink else operation)

    def observe_recovery(**kwargs):
        recovery_started.set()
        try:
            return original_recovery(**kwargs)
        finally:
            recovery_finished.set()

    def observe_reservation(**kwargs):
        if kwargs["reservation_id"] == "timeout-overlap":
            contender_entered.set()
        return original_reserve(**kwargs)

    monkeypatch.setattr(type(sink), "sign_artifact", pause_signed_writer)
    monkeypatch.setattr(type(sink), "run_custody_operation", observe_operation)
    monkeypatch.setattr(raw_store, "mark_human_decision_recovery_required", observe_recovery)
    monkeypatch.setattr(raw_store, "_reserve_human_decision_sqlite", observe_reservation)
    command = cases._contracts().HumanDecisionCreateCommand(
        gate_input=fixture.adapter_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept accountability for this bounded action.",
        dissent_statement="Disconfirming evidence was reviewed and retained.",
    )
    callers = ThreadPoolExecutor(max_workers=2)
    writer = callers.submit(
        cases._create_record_with_bound_mutation,
        fixture.service,
        command,
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )
    contender = None
    try:
        assert paused.wait(30), "real writer never reached signed, fenced custody"
        with pytest.raises(HumanDecisionPersistenceError) as unknown:
            writer.result(timeout=15)
        assert isinstance(unknown.value.__cause__, RuntimeDependencyTimeoutError)
        assert not worker_finished.is_set()
        assert not release.is_set()
        record = captured["record"]
        # A new real reservation reaches the same store while the old SQL fence
        # is held. It cannot finish or mint another generation/effect before release.
        contender = callers.submit(
            guarded.reserve_human_decision_action,
            tenant_id=record["tenant_id"],
            governed_action_key=record["governed_action_key"],
            reservation_id="timeout-overlap",
            binding_sha256=record["binding_sha256"],
            now=cases.NOW,
            lease_seconds=60,
            record_valid_until=cases._contracts()
            .HumanDecisionRecord.model_validate(record)
            .valid_until,
        )
        assert contender_entered.wait(10)
        assert not contender.done()
        assert fixture.effects == []
        release.set()
        assert worker_finished.wait(30)
        if recovery_started.is_set():
            assert recovery_finished.wait(30)
        denied = contender.result(timeout=15)
        assert denied.acquired is False
        assert denied.issue_code == "DS9-OVERLAPPING-REISSUE"
        current = guarded.get_human_decision_reservation(
            tenant_id=record["tenant_id"], governed_action_key=record["governed_action_key"]
        )
        # Fixed fixture time keeps the real lease/validity live. The late worker
        # commits; timeout was lost acknowledgement, never proof of cancellation.
        assert current.state == "committed"
        assert current.reservation_id == record["reservation_id"]
        assert current.reservation_version == record["reservation_version"]
        assert current.record_ref == captured["ref"]
        assert current.record_sha256 == captured["ref"]
        assert current == denied.reservation
        loaded = fixture.service.read_record(
            current.record_ref, tenant_id=record["tenant_id"], run_id=record["run_id"]
        )
        assert loaded.model_dump(mode="json") == record
        assert fixture.store.get_bytes(current.record_ref) == captured["raw"]
        assert (
            fixture.store.get_signature(current.record_ref).signer_identity
            == fixture.custody_identity
        )
        reconciled = sink.reconcile_authority_artifact(
            current.record_ref,
            expected_tenant_id=fixture.write_context.tenant_id,
            expected_cell_id=fixture.write_context.cell_id,
            expected_run_id=fixture.write_context.run_id,
            expected_job_id=fixture.write_context.job_id,
        )
        assert reconciled.durable_event_id == current.durable_event_id
        assert cases._human_decision_record_ids(fixture.store) == {current.record_ref}
        assert fixture.effects == []
    finally:
        release.set()
        callers.shutdown(wait=True, cancel_futures=True)
        # The guarded worker outlives its caller's Future. Join it separately
        # before closing the guard or restoring any method used by its transaction.
        if paused.is_set():
            assert worker_finished.wait(30)
        if recovery_started.is_set():
            assert recovery_finished.wait(30)
        guarded._guard.close()
