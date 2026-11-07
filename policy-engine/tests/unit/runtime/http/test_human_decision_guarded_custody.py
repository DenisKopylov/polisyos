"""Real DS9 custody and crash recovery with the deployed control-store guard."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.quality.authority_reconciliation import resolve_authority_diagnostic_event_ref
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from tests.unit.runtime.http import test_human_decision_service as cases


@pytest.mark.parametrize("recovery", [False, True])
def test_guarded_store_custodies_record_and_recovers_signed_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recovery: bool
) -> None:
    fixture = cases._signed_current_gate_fixture(tmp_path)
    sink = fixture.service.authority_sink
    guarded = guard_runtime_control_store(sink._reservation_store)
    sink._reservation_store = guarded
    sink._event_log._store = guarded
    monkeypatch.setattr(cases, "_signed_current_gate_fixture", lambda _: fixture)
    try:
        if recovery:
            cases.test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2(
                tmp_path, monkeypatch
            )
        else:
            cases.test_human_decision_persists_custody_signature_not_actor_signature(tmp_path)
    finally:
        guarded._guard.close()


@pytest.mark.parametrize("view", ["default", "owned_secondary"])
def test_human_decision_recovery_rejects_profileless_owned_record_view(
    tmp_path: Path,
    view: str,
) -> None:
    """Only matching record kinds require strict Core profiles in the full CAS census."""
    fixture = cases._signed_current_gate_fixture(tmp_path)
    kind = "runtime_quality.agent_action_human_decision"
    payload = b'{"reservation_id":"untrusted-test-payload","reservation_version":1}'

    if view == "default":
        scoped_store = fixture.store
        selected = scoped_store.put_bytes(
            payload,
            ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )
    else:
        shared_store = FileSystemCAS(fixture.store.root)
        foreign_default = shared_store.put_bytes(
            payload,
            ArtifactWriteOptions(
                kind="test.foreign_default.human_decision_payload",
                media_type="application/json",
            ),
        )
        scoped_store = shared_store.for_tenant("tenant-a", cell_id="cell-a")
        selected = scoped_store.put_bytes(
            payload,
            ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )
        assert selected.artifact_id == foreign_default.artifact_id
        assert selected.manifest_profile_sha256 is not None
        assert selected.manifest_profile_sha256 != foreign_default.manifest_profile_sha256
        assert shared_store.get_manifest(foreign_default).kind == (
            "test.foreign_default.human_decision_payload"
        )

    snapshot = scoped_store.manifest_inventory_snapshot(kind=kind)
    assert snapshot.verdict == "pass"
    matching = [
        entry
        for entry in snapshot.entries
        if entry.manifest.artifact_id == selected.artifact_id
        and entry.manifest_profile_sha256 == selected.manifest_profile_sha256
    ]
    assert matching
    selected_identity = artifact_ref_identity_key(selected)
    assert {
        artifact_ref_identity_key(artifact_ref_for_manifest(entry.manifest)) for entry in matching
    } == {selected_identity}
    if view == "owned_secondary":
        assert any(isinstance(entry.artifact_ref, ArtifactRef) for entry in matching)
    assert all(entry.manifest.canon is None for entry in matching)

    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        fixture.service.authority_sink._human_decision_record_manifest_views()


def _prepare_crashed_signed_orphan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, Any, Any, Any, ArtifactRef, str]:
    """Produce the actual signed record/event state immediately before DS9 recovery."""
    contracts = cases._contracts()
    services = cases._service_module()
    fixture = cases._signed_current_gate_fixture(tmp_path)
    sink = fixture.service.authority_sink
    from polisyos.runtime.http.services.control_plane_store import HumanDecisionWriteFence

    class _SimulatedProcessDeath(BaseException):
        pass

    def _die_after_signature(*_args: object, **_kwargs: object) -> None:
        raise _SimulatedProcessDeath

    command = contracts.HumanDecisionCreateCommand(
        gate_input=fixture.adapter_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept accountability for this bounded action.",
        dissent_statement="Disconfirming evidence was reviewed and retained.",
        override_reason=None,
        blocking_reason=None,
    )
    with monkeypatch.context() as crash:
        crash.setattr(HumanDecisionWriteFence, "commit", _die_after_signature)
        with pytest.raises(_SimulatedProcessDeath):
            cases._create_record_with_bound_mutation(
                fixture.service,
                command,
                bound_permission=fixture.bound_permission,
                write_context=fixture.write_context,
            )

    gate = fixture.resolve()
    assert gate.governed_action_key is not None
    crashed = sink.get_reservation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
    )
    assert crashed is not None
    assert crashed.state == "reserved"
    assert crashed.record_ref is None

    recovery_time = cases.NOW + timedelta(seconds=61)
    monkeypatch.setattr(fixture.service, "_clock", lambda: recovery_time)
    with pytest.raises(
        services.HumanDecisionOperationalResolutionError,
        match="DS9-RESERVATION-RECOVERY-REQUIRED",
    ):
        cases._create_record_with_bound_mutation(
            fixture.service,
            command,
            bound_permission=fixture.bound_permission,
            write_context=fixture.write_context,
        )
    recovery_required = sink.get_reservation(
        tenant_id="tenant-a",
        governed_action_key=gate.governed_action_key,
    )
    assert recovery_required is not None
    assert recovery_required.state == "recovery_required"
    record_ids = cases._human_decision_record_ids(fixture.store)
    assert len(record_ids) == 1
    record_id = next(iter(record_ids))
    record_ref = artifact_ref_for_manifest(fixture.store.get_manifest(record_id))
    record_manifest = fixture.store.get_manifest(record_ref)
    assert record_manifest.authority is not None
    event_ref = resolve_authority_diagnostic_event_ref(fixture.store, record_manifest.authority)
    event = DiagnosticEvent.model_validate_json(fixture.store.get_bytes(event_ref))
    assert fixture.harness.event_log.list_events(event_id=event.event_id) == []
    return fixture, gate, crashed, recovery_time, record_ref, event.event_id


def _secondary_orphan_store(
    fixture: Any,
    record_ref: ArtifactRef,
    root: Path,
    *,
    selected_signer: Ed25519Signer | None,
) -> tuple[FileSystemCAS, ArtifactRef, ArtifactRef]:
    """Put a foreign default view beside the exact tenant-bound signed record view."""
    source = fixture.store
    record_manifest = source.get_manifest(record_ref)
    assert record_manifest.tenant_context is not None
    assert record_manifest.tenant_context.tenant_id == "tenant-a"
    assert record_manifest.tenant_context.cell_id == "cell-a"
    assert record_manifest.authority is not None

    payload = source.get_bytes(record_ref)
    selected_manifest_bytes = source.get_manifest_bytes(record_ref)
    if selected_signer is None:
        selected_signature = None
    else:
        source.sign_artifact(
            record_ref,
            selected_signer,
            signer_identity=fixture.custody_identity,
        )
        selected_signature = source.get_signature_bytes(record_ref)

    target = FileSystemCAS(root, ownership_enforced=False)
    foreign_default = target.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.foreign_default.human_decision_payload",
            media_type="application/json",
        ),
    )
    target.sign_artifact(
        foreign_default.artifact_id,
        fixture.service.custody.signer,
        signer_identity=fixture.custody_identity,
    )
    selected = target.import_exact_view(
        payload,
        selected_manifest_bytes,
        artifact_id=record_ref,
        signature_bytes=selected_signature,
    )
    assert selected == record_ref
    assert target.get_manifest(foreign_default).kind == (
        "test.foreign_default.human_decision_payload"
    )
    assert target.get_manifest(selected).kind == "runtime_quality.agent_action_human_decision"

    event_ref = resolve_authority_diagnostic_event_ref(source, record_manifest.authority)
    event_signature: bytes | None
    try:
        event_signature = source.get_signature_bytes(event_ref)
    except FileNotFoundError:
        event_signature = None
    target.import_exact_view(
        source.get_bytes(event_ref),
        source.get_manifest_bytes(event_ref),
        artifact_id=event_ref,
        signature_bytes=event_signature,
    )
    return target, selected, foreign_default


@pytest.mark.parametrize("selected_key", ["trusted", "wrong", "unsigned"])
def test_null_ref_recovery_preserves_selected_signed_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_key: str,
) -> None:
    """Recovery uses owned profile A despite a same-byte foreign default profile B."""
    fixture, gate, crashed, recovery_time, record_ref, event_id = _prepare_crashed_signed_orphan(
        tmp_path, monkeypatch
    )
    selected_signer: Ed25519Signer | None
    if selected_key == "trusted":
        selected_signer = fixture.service.custody.signer
    elif selected_key == "wrong":
        selected_signer = Ed25519Signer(KeyPair.generate().private_key)
    else:
        selected_signer = None
    target, selected, foreign_default = _secondary_orphan_store(
        fixture,
        record_ref,
        tmp_path / "profile-separated-cas",
        selected_signer=selected_signer,
    )
    sink = fixture.service.authority_sink
    sink._artifact_store = target

    assert selected.artifact_id == foreign_default.artifact_id
    assert selected.manifest_profile_sha256 is not None
    assert selected.manifest_profile_sha256 != foreign_default.manifest_profile_sha256
    assert target.get_manifest_bytes(selected) != target.get_manifest_bytes(foreign_default)
    assert foreign_default.manifest_profile_sha256 is None

    if selected_key == "trusted":
        assert target.verify_signature(
            selected,
            fixture.service.custody.verifier,
            strict_identity=True,
        ).ok
        reconciled = sink.reconcile_null_ref_reservation(
            tenant_id="tenant-a",
            governed_action_key=gate.governed_action_key,
            reservation_id=crashed.reservation_id,
            reservation_version=crashed.reservation_version,
            verifier=fixture.service.custody.verifier,
            expected_signer_identity=fixture.custody_identity,
            expected_key_id=fixture.custody_key_id,
            expected_cell_id=fixture.write_context.cell_id,
            expected_run_id=fixture.write_context.run_id,
            expected_job_id=fixture.write_context.job_id,
            reconciled_at=recovery_time,
        )
        assert reconciled.state == "reconciled_orphan"
        assert reconciled.record_ref == str(selected.artifact_id)
        assert reconciled.record_sha256 == str(selected.artifact_id)
        assert len(fixture.harness.event_log.list_events(event_id=event_id)) == 1
    else:
        assert not target.verify_signature(
            selected,
            fixture.service.custody.verifier,
            strict_identity=True,
        ).ok
        with pytest.raises(ValueError, match="DS9-RESERVATION-RECOVERY-REQUIRED"):
            sink.reconcile_null_ref_reservation(
                tenant_id="tenant-a",
                governed_action_key=gate.governed_action_key,
                reservation_id=crashed.reservation_id,
                reservation_version=crashed.reservation_version,
                verifier=fixture.service.custody.verifier,
                expected_signer_identity=fixture.custody_identity,
                expected_key_id=fixture.custody_key_id,
                expected_cell_id=fixture.write_context.cell_id,
                expected_run_id=fixture.write_context.run_id,
                expected_job_id=fixture.write_context.job_id,
                reconciled_at=recovery_time,
            )
        assert fixture.harness.event_log.list_events(event_id=event_id) == []
        pending = sink.get_reservation_generation(
            tenant_id="tenant-a",
            governed_action_key=gate.governed_action_key,
            reservation_version=crashed.reservation_version,
        )
        assert pending is not None
        assert pending.state == "recovery_required"
