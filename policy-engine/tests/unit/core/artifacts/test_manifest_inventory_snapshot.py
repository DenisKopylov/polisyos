"""Behavioral tests for profile-complete metadata inventory selection."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactIntegrityError,
    ArtifactRef,
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
)


def test_manifest_snapshot_selects_every_kind_profile_without_opening_other_blobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scoped snapshot retains profile aliases and leaves payloads to consumers."""
    store = FileSystemCAS(tmp_path / "cas")
    payload = b'{"decision":"blocked"}'
    kind = "policyos.evaluation_safety.decision"
    schema = SchemaInfo(name="policyos.evaluation_safety.decision", version="1.0")
    default_ref = store.put_bytes(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            producer=ProducerInfo(component="test.owner.default", version="1"),
        ),
    )
    second_profile_ref = store.put_bytes(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            producer=ProducerInfo(component="test.owner.second", version="1"),
        ),
    )
    other_ref = store.put_bytes(
        b"X" * (8 * 1024 * 1024),
        PutOptions(kind="test.unrelated.large", media_type="application/octet-stream"),
    )
    assert default_ref.artifact_id == second_profile_ref.artifact_id
    assert default_ref.artifact_id != other_ref.artifact_id
    store._member_path(other_ref.artifact_id, "blob", None).write_bytes(b"corrupt non-target")

    original_open_member = store.open_member
    opened: list[tuple[str, str]] = []

    def guarded_open_member(ref: ArtifactID | ArtifactRef, member: str) -> object:
        artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref
        opened.append((str(artifact_id), member))
        if artifact_id == other_ref.artifact_id and member == "blob":
            raise AssertionError("non-target blob was opened")
        return original_open_member(ref, member)

    monkeypatch.setattr(store, "open_member", guarded_open_member)
    snapshot = store.manifest_inventory_snapshot(kind=kind)

    assert snapshot.verdict == "pass"
    assert len(snapshot.entries) == 3
    assert {entry.manifest.kind for entry in snapshot.entries} == {kind}
    assert all(entry.manifest_profile_sha256 for entry in snapshot.entries)
    canonical_profiles = {
        (str(entry.manifest.artifact_id), entry.manifest_profile_sha256)
        for entry in snapshot.entries
    }
    assert len(canonical_profiles) == 2
    assert len(snapshot.entries) - len(canonical_profiles) == 1
    assert all(not hasattr(entry, "blob_sha256") for entry in snapshot.entries)
    assert all(not hasattr(entry, "blob_byte_size") for entry in snapshot.entries)
    assert any("selected payload" in item for item in snapshot.unresolved_by_construction)
    assert (str(other_ref.artifact_id), "blob") not in opened

    selected_bytes = store.get_bytes(second_profile_ref)
    assert selected_bytes == payload
    selected_blob_path = store._member_path(second_profile_ref.artifact_id, "blob", None)
    selected_blob_path.write_bytes(b"corrupt selected target")
    with pytest.raises(ArtifactIntegrityError):
        store.get_bytes(second_profile_ref)


def test_manifest_snapshot_fails_on_malformed_visible_manifest(
    tmp_path: Path,
) -> None:
    """A malformed present manifest cannot disappear from a target selection."""
    store = FileSystemCAS(tmp_path / "cas")
    kind = "policyos.evaluation_safety.decision"
    ref = store.put_bytes(
        b'{"decision":"blocked"}',
        PutOptions(kind=kind, media_type="application/json"),
    )
    store._member_path(ref.artifact_id, "manifest", None).write_bytes(b"{malformed")

    snapshot = store.manifest_inventory_snapshot(kind=kind)

    assert snapshot.verdict == "fail"
    assert snapshot.reason is not None


def test_manifest_snapshot_returns_unrun_when_member_set_changes_between_captures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A concurrent CAS member is detected instead of becoming an omitted target."""
    store = FileSystemCAS(tmp_path / "cas")
    store.put_bytes(
        b"initial",
        PutOptions(kind="policyos.evaluation_safety.decision", media_type="application/json"),
    )
    coordinator = store._coordinator
    original_root_exclusive = coordinator.root_exclusive
    capture_count = 0

    @contextmanager
    def root_exclusive() -> Iterator[None]:
        nonlocal capture_count
        with original_root_exclusive():
            yield
        if capture_count == 0:
            capture_count += 1
            store.put_bytes(
                b"concurrent member",
                PutOptions(kind="test.concurrent", media_type="text/plain"),
            )

    monkeypatch.setattr(coordinator, "root_exclusive", root_exclusive)

    snapshot = store.manifest_inventory_snapshot(kind="policyos.evaluation_safety.decision")

    monkeypatch.setattr(coordinator, "root_exclusive", original_root_exclusive)
    assert snapshot.verdict == "UNRUN"
    assert snapshot.reason == "manifest_inventory_changed_during_scan"


def test_manifest_snapshot_returns_unrun_when_owner_generation_changes_without_new_cas_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The root-owner generation is part of the stable manifest denominator."""
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    target_ref = store.put_bytes(
        b"existing owned target",
        PutOptions(kind="policyos.evaluation_safety.decision", media_type="application/json"),
    )
    coordinator = store._coordinator
    original_root_exclusive = coordinator.root_exclusive
    capture_count = 0

    @contextmanager
    def root_exclusive() -> Iterator[None]:
        nonlocal capture_count
        with original_root_exclusive():
            yield
        if capture_count == 0:
            capture_count += 1
            store._ownership_index.record_owner(
                target_ref.artifact_id,
                tenant_id="tenant-b",
            )

    original_names, original_views, _generation = store._capture_inventory_membership()
    monkeypatch.setattr(coordinator, "root_exclusive", root_exclusive)

    snapshot = store.manifest_inventory_snapshot(kind="policyos.evaluation_safety.decision")

    monkeypatch.setattr(coordinator, "root_exclusive", original_root_exclusive)
    names_after, views_after, _generation_after = store._capture_inventory_membership()
    assert names_after == original_names
    assert tuple((row[0], row[1], row[3]) for row in views_after) == tuple(
        (row[0], row[1], row[3]) for row in original_views
    )
    assert snapshot.verdict == "UNRUN"
    assert snapshot.reason == "manifest_inventory_changed_during_scan"
