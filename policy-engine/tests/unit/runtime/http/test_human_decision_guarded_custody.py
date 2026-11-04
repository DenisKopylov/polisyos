"""Real DS9 custody and crash recovery with the deployed control-store guard."""

from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
)
from polisyos.runtime.http.resilience import guard_runtime_control_store
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
