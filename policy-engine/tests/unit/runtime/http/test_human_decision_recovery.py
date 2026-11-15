"""Actual custody producer to read-only lost-ack recovery, without another decision."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event

import pytest
from pydantic import TypeAdapter, ValidationError

from polisyos.core.artifacts import artifact_ref_for_manifest
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    ResourceBindingSpec,
    RouteAuthorizationRequirement,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.human_decision_contracts import HumanDecisionRecoveryResponse
from polisyos.runtime.quality.authority_reconciliation import resolve_authority_diagnostic_event_ref
from tests.unit.runtime.http import test_human_decision_service as cases


def _case(tmp_path):
    fixture = cases._signed_current_gate_fixture(tmp_path)
    command = cases._contracts().HumanDecisionCreateCommand(
        gate_input=fixture.adapter_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept this exact action.",
        dissent_statement="Disconfirming evidence remains retained.",
    )
    return fixture, command


def _permission(fixture, command, *, subject=None):
    previous = fixture.bound_permission
    requirement = RouteAuthorizationRequirement(
        permission=RuntimePermission.RUNS_REVIEW,
        resource_binding=ResourceBindingSpec(
            source=ResourceBindingSource.OWNED_EXISTING_PATH,
            resource_kind="runtime.run.human_decision_recovery",
            path_parameter="run_id",
            allow_empty_body=False,
        ),
    )
    verification = replace(
        previous.verification,
        requirement=requirement,
        subject=subject or previous.verification.subject,
        granted_permissions=(RuntimePermission.RUNS_REVIEW,),
    )
    proof = type(previous)(
        verification=verification,
        bound_resource=previous.bound_resource,
        _seal=previous._seal,
    )
    return cases._bound_mutation_permission(proof, command, recovery=True)


def _create(fixture, command):
    return cases._create_record_with_bound_mutation(
        fixture.service,
        command,
        bound_permission=fixture.bound_permission,
        write_context=fixture.write_context,
    )


def _recover(fixture, command):
    return fixture.service.recover_record(
        command,
        bound_permission=_permission(fixture, command),
        cell_id=fixture.write_context.cell_id,
    )


def _bytes(fixture):
    return {
        str(path): path.read_bytes() for path in fixture.store.base.rglob("*") if path.is_file()
    }


def test_committed_recovery_is_selected_history_and_does_not_write(tmp_path: Path):
    fixture, command = _case(tmp_path)
    receipt = _create(fixture, command)
    before = _bytes(fixture)
    result = _recover(fixture, command)
    assert result.status == "committed", result
    assert str(result.record_ref.artifact_id) == receipt.record_ref
    assert result.record_ref.manifest_profile_sha256 is not None
    assert result.durable_event_id == receipt.durable_event_id
    assert result.reservation_id == receipt.reservation_id
    assert result.binding_rule == "policyos.runtime.human_decision_submission_binding.v2"
    assert result.operational_authority is False
    assert _bytes(fixture) == before
    assert fixture.effects == []
    adapter = TypeAdapter(HumanDecisionRecoveryResponse)
    assert adapter.validate_python(result.model_dump()) == result
    with pytest.raises(ValidationError):
        adapter.validate_python({**result.model_dump(), "status": "pending"})


def test_actual_reservation_can_be_pending_before_custody_completes(tmp_path: Path, monkeypatch):
    fixture, command = _case(tmp_path)
    sink = fixture.service.authority_sink
    paused, release = Event(), Event()
    original = type(sink).run_custody_operation

    def hold_before_custody(owner, operation):
        if owner is sink:
            paused.set()
            assert release.wait(15)
        return original(owner, operation)

    monkeypatch.setattr(type(sink), "run_custody_operation", hold_before_custody)
    with ThreadPoolExecutor(max_workers=1) as executor:
        writer = executor.submit(_create, fixture, command)
        try:
            assert paused.wait(10)
            result = _recover(fixture, command)
            assert result.status == "pending", result
            assert result.operational_authority is False
            assert not cases._human_decision_record_ids(fixture.store)
        finally:
            release.set()
        receipt = writer.result(timeout=20)
    recovered = _recover(fixture, command)
    assert recovered.status == "committed", recovered
    assert recovered.reservation_id == result.reservation_id == receipt.reservation_id
    assert len(cases._human_decision_record_ids(fixture.store)) == 1


@pytest.mark.parametrize(
    "field", ["accountability_statement", "dissent_statement", "decision_action"]
)
def test_different_logical_submission_cannot_recover_original_receipt(tmp_path: Path, field):
    fixture, command = _case(tmp_path)
    receipt = _create(fixture, command)
    changed = command.model_copy(
        update={
            field: "request_evidence" if field == "decision_action" else "Different decision input."
        }
    )
    result = _recover(fixture, changed)
    assert result.status == "not_established"
    assert cases._human_decision_record_ids(fixture.store) == {receipt.record_ref}
    assert _recover(fixture, command).status == "committed"


def test_foreign_current_subject_cannot_discover_receipt(tmp_path: Path):
    fixture, command = _case(tmp_path)
    _create(fixture, command)
    with pytest.raises(cases._service_module().HumanDecisionOperationalResolutionError) as refused:
        fixture.service.recover_record(
            command,
            bound_permission=_permission(fixture, command, subject="different-reviewer"),
            cell_id=fixture.write_context.cell_id,
        )
    assert refused.value.code == "DS9-RECOVERY-SUBJECT-MISMATCH"


def test_different_signed_exposure_cannot_recover_receipt(tmp_path: Path):
    fixture, command = _case(tmp_path)
    _create(fixture, command)
    replacement = fixture.resign_request_bundle(
        fixture.source_decision.human_decision_request,
        session_update={"actor_ref": "actor://different-reviewer"},
    )
    changed = command.model_copy(
        update={
            "gate_input": command.gate_input.model_copy(
                update={"exposure_session_ref": replacement["exposure_session_ref"]}
            )
        }
    )
    assert _recover(fixture, changed).status == "not_established"
    assert _recover(fixture, command).status == "committed"


@pytest.mark.parametrize("member", ["profile", "signature", "event"])
def test_real_custody_removal_limits_recovery_then_restore_replays(tmp_path: Path, member):
    fixture, command = _case(tmp_path)
    receipt = _create(fixture, command)
    ref = artifact_ref_for_manifest(fixture.store.get_manifest(receipt.record_ref))
    manifest = fixture.store.get_manifest(ref)
    if member == "profile":
        paths = {
            fixture.store._paths(ref.artifact_id)[1],
            fixture.store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256),
        }
    elif member == "signature":
        paths = {fixture.store._sig_path(ref.artifact_id)}
    else:
        event_ref = resolve_authority_diagnostic_event_ref(fixture.store, manifest.authority)
        paths = {fixture.store._paths(event_ref.artifact_id)[0]}
    withheld = []
    try:
        for index, path in enumerate(sorted(paths)):
            saved = tmp_path / f"withheld-{index}-{path.name}"
            path.replace(saved)
            withheld.append((path, saved))
        assert _recover(fixture, command).status == "not_established"
    finally:
        for path, saved in reversed(withheld):
            saved.replace(path)
    assert _recover(fixture, command).status == "committed"


def test_later_real_reservation_does_not_hide_expired_committed_generation(
    tmp_path: Path, monkeypatch
):
    fixture, command = _case(tmp_path)
    receipt = _create(fixture, command)
    later = receipt.record.valid_until + timedelta(seconds=1)
    sink = fixture.service.authority_sink
    second = sink.reserve_action(
        tenant_id=command.gate_input.tenant_id,
        governed_action_key=receipt.record.governed_action_key,
        reservation_id="later-independent-reservation",
        binding_sha256="sha256:" + "b" * 64,
        now=later,
        lease_seconds=60,
        record_valid_until=later + timedelta(hours=1),
    )
    assert second.acquired and second.reservation.reservation_version == 2
    monkeypatch.setattr(fixture.service, "_clock", lambda: later)
    result = _recover(fixture, command)
    assert result.status == "committed", result
    assert result.reservation_id == receipt.reservation_id
    assert result.reservation_version == 1
    assert result.reservation_state == "expired"
    assert result.operational_authority is False
    assert (
        sink.get_reservation(
            tenant_id=command.gate_input.tenant_id,
            governed_action_key=receipt.record.governed_action_key,
        )
        == second.reservation
    )


def test_recovery_consumes_the_original_frozen_submission(tmp_path: Path):
    fixture, command = _case(tmp_path)
    _create(fixture, command)
    changed = command.model_copy(update={"accountability_statement": "Changed after OPA."})
    with pytest.raises(cases._service_module().HumanDecisionOperationalResolutionError) as refused:
        fixture.service.recover_record(
            changed,
            bound_permission=_permission(fixture, command),
            cell_id=fixture.write_context.cell_id,
        )
    assert refused.value.code == "DS9-DECISION-PERMISSION-UNVERIFIED"


def test_recovery_permission_does_not_authorize_another_record(tmp_path: Path):
    fixture, command = _case(tmp_path)
    with pytest.raises(cases._service_module().HumanDecisionOperationalResolutionError) as refused:
        fixture.service.create_record(
            command,
            bound_permission=_permission(fixture, command),
            write_context=fixture.write_context,
        )
    assert refused.value.code == "DS9-DECISION-PERMISSION-UNVERIFIED"
    assert cases._human_decision_record_ids(fixture.store) == set()
    assert fixture.effects == []


def test_legacy_unbound_pending_row_cannot_claim_this_actor_submission(tmp_path: Path):
    fixture, command = _case(tmp_path)
    gate = fixture.resolve()
    row = fixture.service.authority_sink.reserve_action(
        tenant_id=command.gate_input.tenant_id,
        governed_action_key=gate.governed_action_key,
        reservation_id="legacy-reserved-no-record",
        binding_sha256="sha256:" + "c" * 64,
        now=cases.NOW,
        lease_seconds=60,
        record_valid_until=cases.NOW + timedelta(minutes=10),
    )
    assert row.acquired
    assert _recover(fixture, command).status == "not_established"
    assert cases._human_decision_record_ids(fixture.store) == set()
