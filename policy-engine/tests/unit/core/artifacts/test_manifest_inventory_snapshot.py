"""Behavioral tests for profile-complete metadata inventory selection."""

from __future__ import annotations

import os
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


def test_artifact_snapshot_scans_only_the_selected_shard_and_all_subject_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The subject API verifies every profile without traversing unrelated shards."""
    store = FileSystemCAS(tmp_path / "cas")
    payload = b'{"decision":"limited"}'
    kind = "policyos.evaluation_safety.decision"
    schema = SchemaInfo(name=kind, version="1.0")
    default_ref = store.put_bytes(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema,
            producer=ProducerInfo(component="test.subject.default", version="1"),
        ),
    )
    profile_refs = tuple(
        store.put_bytes(
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=schema,
                producer=ProducerInfo(component=f"test.subject.profile-{index}", version="1"),
            ),
        )
        for index in range(2)
    )
    assert all(ref.artifact_id == default_ref.artifact_id for ref in profile_refs)
    unrelated_ref = store.put_bytes(
        b"unrelated", PutOptions(kind="test.unrelated", media_type="text/plain")
    )
    unrelated_shard = store._paths(unrelated_ref.artifact_id)[0].parent
    (unrelated_shard / "malformed-unrelated-member").write_bytes(b"ignored by subject scan")

    real_scandir = os.scandir
    scanned_subject_shards: list[Path] = []

    def record_scandir(path_arg):
        candidate = Path(path_arg)
        if candidate == store.base or candidate.is_relative_to(store.base):
            scanned_subject_shards.append(candidate)
        return real_scandir(path_arg)

    monkeypatch.setattr("polisyos.core.artifacts.store.os.scandir", record_scandir)
    snapshot = store.artifact_inventory_snapshot(default_ref.artifact_id)

    assert snapshot.verdict == "pass"
    assert len(snapshot.entries) >= 3
    assert {str(entry.manifest.artifact_id) for entry in snapshot.entries} == {
        str(default_ref.artifact_id)
    }
    visible_profiles = {
        entry.artifact_ref.manifest_profile_sha256
        if isinstance(entry.artifact_ref, ArtifactRef)
        else None
        for entry in snapshot.entries
    }
    assert len(visible_profiles) == len(snapshot.entries)
    assert sum("same-ID member names" in item for item in snapshot.inputs) == 1
    assert any(
        "outside the selected subject" in item for item in snapshot.unresolved_by_construction
    )
    assert scanned_subject_shards == [store._paths(default_ref.artifact_id)[0].parent] * 2

    global_snapshot = store.inventory_snapshot(artifact_id=default_ref.artifact_id)
    assert global_snapshot.verdict == "fail"
    assert global_snapshot.reason == "cas_inventory_member_name_invalid"


def test_artifact_snapshot_refuses_a_symlink_within_the_selected_subject(
    tmp_path: Path,
) -> None:
    """A same-ID symlink cannot be omitted from the subject denominator."""
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(b"subject", PutOptions(kind="test.subject", media_type="text/plain"))
    profile = "a" * 64
    alias = store._member_path(ref.artifact_id, "manifest", None).with_name(
        f"{ref.artifact_id.hex}.view.{profile}.manifest.json"
    )
    alias.symlink_to(store._member_path(ref.artifact_id, "manifest", None))

    snapshot = store.artifact_inventory_snapshot(ref.artifact_id)

    assert snapshot.verdict == "fail"
    assert snapshot.reason == "cas_inventory_symlink_member"


@pytest.mark.parametrize("movement", ["profile", "owner"])
def test_artifact_snapshot_rejects_movement_between_subject_cuts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, movement: str
) -> None:
    """A changed subject or signed owner generation invalidates the read."""
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    payload = b"subject with moving custody"
    original = store.put_bytes(payload, PutOptions(kind="test.subject", media_type="text/plain"))
    lease = store._coordinator.artifact_lease
    moved = False

    @contextmanager
    def move_after_first_cut(artifact_id, **kwargs):
        nonlocal moved
        with lease(artifact_id, **kwargs) as held:
            yield held
        if artifact_id != original.artifact_id or moved:
            return
        moved = True
        if movement == "profile":
            store.put_bytes(
                payload, PutOptions(kind="test.additional-view", media_type="text/plain")
            )
        else:
            store._ownership_index.record_owner(artifact_id, tenant_id="tenant-b")

    monkeypatch.setattr(store._coordinator, "artifact_lease", move_after_first_cut)
    snapshot = store.artifact_inventory_snapshot(original.artifact_id)

    assert moved
    assert snapshot.verdict == "UNRUN"
    assert snapshot.reason == "inventory_changed_during_scan"


def test_artifact_snapshot_requires_a_valid_artifact_id(tmp_path: Path) -> None:
    """Existing ID model instances are validated before choosing a shard."""
    store = FileSystemCAS(tmp_path / "cas")
    malformed = ArtifactID.from_sha256_hex("a" * 64).model_copy(update={"root": "invalid"})
    with pytest.raises(ValueError, match="ArtifactID must start"):
        store.artifact_inventory_snapshot(malformed)
