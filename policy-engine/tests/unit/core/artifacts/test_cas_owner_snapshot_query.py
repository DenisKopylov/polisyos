"""Real CAS writes preserve every lineage role while bounding repeated owner checks."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import pytest

import polisyos.core.artifacts.ownership as ownership_module
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.ownership import (
    ArtifactOwnershipError,
    ArtifactOwnershipIndex,
    ArtifactPublicReadClosureUnavailableError,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope


def _source(store: FileSystemCAS, data: bytes, version: str) -> ArtifactRef:
    return store.put_bytes(
        data,
        PutOptions(
            kind="test.input_source",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="test.input_source", version=version),
        ),
        return_selected_profile=True,
    )


def _edge(ref: ArtifactRef, role: str, profile: str | None) -> InputRef:
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=profile,
    )


def _target_blob(root: Path, payload: bytes) -> Path:
    digest = hashlib.sha256(payload).hexdigest()
    return root / "artifacts" / "sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"


def test_repeated_input_views_recheck_all_roles_without_thawing_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every role is authorized without copying an already validated whole index."""
    writer = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        _assert_repeated_views_preserve_roles(writer, monkeypatch)


def _assert_repeated_views_preserve_roles(
    writer: FileSystemCAS, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _source(writer, b"one shared source", "1.0")
    alternate = _source(writer, b"one shared source", "2.0")
    other = _source(writer, b"second source", "1.0")
    assert first.artifact_id == alternate.artifact_id
    assert first.manifest_profile_sha256 != alternate.manifest_profile_sha256
    assert first.manifest_profile_sha256 is not None
    assert alternate.manifest_profile_sha256 is not None
    assert other.manifest_profile_sha256 is not None
    choices = (
        (first, None),
        (first, first.manifest_profile_sha256),
        (alternate, alternate.manifest_profile_sha256),
        (other, other.manifest_profile_sha256),
    )
    inputs = [
        _edge(choices[index % 4][0], f"source.{index:03d}", choices[index % 4][1])
        for index in range(192)
    ]
    blob_calls: list[str] = []
    view_calls: list[tuple[str, str | None]] = []
    input_check_depth = 0
    whole_index_thaws = 0
    real_thaw = ownership_module._thaw_json

    def observe_thaw(value):
        nonlocal whole_index_thaws
        if input_check_depth and isinstance(value, Mapping) and "artifacts" in value:
            whole_index_thaws += 1
        return real_thaw(value)

    monkeypatch.setattr(ownership_module, "_thaw_json", observe_thaw)
    real_blob_check = writer._require_blob_owner
    real_view_check = writer._require_manifest_view_owner

    def observe_blob(artifact_id, *, operation, ref=None):
        nonlocal input_check_depth
        checking_input = operation.startswith("write input:")
        if checking_input:
            blob_calls.append(str(artifact_id))
            input_check_depth += 1
        try:
            return real_blob_check(artifact_id, operation=operation, ref=ref)
        finally:
            if checking_input:
                input_check_depth -= 1

    def observe_view(artifact_id, profile, *, operation, ref=None):
        nonlocal input_check_depth
        checking_input = operation.startswith("write input manifest:")
        if checking_input:
            view_calls.append((str(artifact_id), profile))
            input_check_depth += 1
        try:
            return real_view_check(artifact_id, profile, operation=operation, ref=ref)
        finally:
            if checking_input:
                input_check_depth -= 1

    monkeypatch.setattr(writer, "_require_blob_owner", observe_blob)
    monkeypatch.setattr(writer, "_require_manifest_view_owner", observe_view)
    published = writer.put_bytes(
        b"complete role-qualified result",
        PutOptions(kind="test.result", media_type="application/octet-stream", inputs=inputs),
        return_selected_profile=True,
    )
    manifest = writer.get_manifest(published)
    assert [(str(x.artifact_id), x.manifest_profile_sha256, x.role) for x in manifest.inputs] == [
        (str(x.artifact_id), x.manifest_profile_sha256, x.role) for x in inputs
    ]
    assert len(manifest.inputs) == 192
    expected_views = {
        (str(first.artifact_id), None): 96,
        (str(first.artifact_id), first.manifest_profile_sha256): 96,
        (str(first.artifact_id), alternate.manifest_profile_sha256): 96,
        (str(other.artifact_id), other.manifest_profile_sha256): 96,
    }
    assert Counter(view_calls) == expected_views
    assert Counter(blob_calls) == {str(first.artifact_id): 288, str(other.artifact_id): 96}
    assert whole_index_thaws == 0


def test_unowned_later_profile_and_default_view_cannot_hide_behind_same_blob(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cas"
    tenant_a = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    tenant_b = FileSystemCAS(root).for_tenant("tenant-b", cell_id="cell-b")
    a_view = _source(tenant_a, b"shared source bytes", "1.0")
    b_view = _source(tenant_b, b"shared source bytes", "2.0")
    assert a_view.artifact_id == b_view.artifact_id
    assert a_view.manifest_profile_sha256 != b_view.manifest_profile_sha256
    assert b_view.manifest_profile_sha256 is not None

    foreign_payload = b"must not publish foreign profile"
    with pytest.raises(ArtifactOwnershipError):
        tenant_a.put_bytes(
            foreign_payload,
            PutOptions(
                kind="test.foreign_profile_result",
                media_type="application/octet-stream",
                inputs=[
                    _edge(a_view, "selected.one", a_view.manifest_profile_sha256),
                    _edge(a_view, "selected.two", a_view.manifest_profile_sha256),
                    _edge(b_view, "selected.last", b_view.manifest_profile_sha256),
                ],
            ),
        )
    assert not _target_blob(root, foreign_payload).exists()

    default_payload = b"must not publish unowned default"
    with pytest.raises(ArtifactOwnershipError):
        tenant_b.put_bytes(
            default_payload,
            PutOptions(
                kind="test.foreign_default_result",
                media_type="application/octet-stream",
                inputs=[
                    _edge(b_view, "selected.one", b_view.manifest_profile_sha256),
                    _edge(b_view, "selected.two", b_view.manifest_profile_sha256),
                    _edge(b_view, "default.last", None),
                ],
            ),
        )
    assert not _target_blob(root, default_payload).exists()


def test_same_selected_view_is_not_reused_for_another_tenant_or_cell(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    source_owner = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    source = _source(source_owner, b"source owned by a single cell", "1.0")
    for tenant, cell in (("tenant-b", "cell-a"), ("tenant-a", "cell-b")):
        outsider = FileSystemCAS(root).for_tenant(tenant, cell_id=cell)
        data = f"denied target for {tenant}/{cell}".encode()
        with pytest.raises(ArtifactOwnershipError):
            outsider.put_bytes(
                data,
                PutOptions(
                    kind="test.foreign_owner_result",
                    media_type="application/octet-stream",
                    inputs=[_edge(source, "one", source.manifest_profile_sha256)],
                ),
            )
        assert not _target_blob(root, data).exists()


def test_unscoped_claim_between_duplicate_inputs_is_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An owner added after the first check must invalidate the next unscoped check."""
    root = tmp_path / "cas"
    writer = FileSystemCAS(root).with_ambient_ownership_enforcement()
    source = writer.put_bytes(
        b"initially unclaimed source",
        PutOptions(kind="test.source", media_type="application/octet-stream"),
    )
    owner = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    original = writer._require_manifest_view_owner
    checks = 0

    def claim_after_first_view(artifact_id, profile, *, operation, ref=None):
        nonlocal checks
        result = original(artifact_id, profile, operation=operation, ref=ref)
        if operation.startswith("write input manifest:"):
            checks += 1
            if checks == 1:
                owner.record_artifact_owner(artifact_id)
        return result

    monkeypatch.setattr(writer, "_require_manifest_view_owner", claim_after_first_view)
    target = b"must refuse a newly claimed input"
    with pytest.raises(ArtifactOwnershipError):
        writer.put_bytes(
            target,
            PutOptions(
                kind="test.unscoped_race_result",
                media_type="application/octet-stream",
                inputs=[_edge(source, "first", None), _edge(source, "second", None)],
            ),
        )
    assert not _target_blob(root, target).exists()


def test_unscoped_claim_between_preflight_and_publication_is_rechecked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh inner pass must observe a claim made after the outer pass."""
    root = tmp_path / "cas"
    writer = FileSystemCAS(root).with_ambient_ownership_enforcement()
    source = writer.put_bytes(
        b"unclaimed preflight source",
        PutOptions(kind="test.source", media_type="application/octet-stream"),
    )
    owner = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    original = writer._put_blob_and_manifest_once

    def claim_before_publication(**kwargs):
        owner.record_artifact_owner(source.artifact_id)
        return original(**kwargs)

    monkeypatch.setattr(writer, "_put_blob_and_manifest_once", claim_before_publication)
    target = b"must recheck source inside publication lease"
    with pytest.raises(ArtifactOwnershipError):
        writer.put_bytes(
            target,
            PutOptions(
                kind="test.unscoped_recheck_result",
                media_type="application/octet-stream",
                inputs=[_edge(source, "one", None), _edge(source, "two", None)],
            ),
        )
    assert not _target_blob(root, target).exists()


def test_scoped_owner_is_rechecked_in_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The inner pass must use the current tenant rather than the earlier success."""
    root = tmp_path / "cas"
    writer = FileSystemCAS(root).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        source = _source(writer, b"source for the first tenant", "1.0")
    original = writer._put_blob_and_manifest_once

    def switch_tenant_before_publication(**kwargs):
        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            return original(**kwargs)

    monkeypatch.setattr(writer, "_put_blob_and_manifest_once", switch_tenant_before_publication)
    target = b"must not reuse the earlier tenant's check"
    with (
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(ArtifactOwnershipError),
    ):
        writer.put_bytes(
            target,
            PutOptions(
                kind="test.scoped_recheck_result",
                media_type="application/octet-stream",
                inputs=[_edge(source, "one", None), _edge(source, "two", None)],
            ),
        )
    assert not _target_blob(root, target).exists()


def test_governed_read_capability_does_not_authorize_lineage_write(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root).with_ambient_ownership_enforcement()
    owner_token = store._register_governed_public_read_owner()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        source = _source(store, b"governed read only", "1.0")
        with store._capture_public_read_set() as capture:
            assert store.get_bytes(source) == b"governed read only"
        store._record_governed_public_read_closure(
            "gpr_" + "a" * 32, capture, owner_token=owner_token
        )
    target = b"governed read cannot grant this write"
    with (
        store._authorize_governed_public_read("gpr_" + "a" * 32, owner_token=owner_token),
        tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"),
        pytest.raises(ArtifactPublicReadClosureUnavailableError),
    ):
        store.put_bytes(
            target,
            PutOptions(
                kind="test.public_read_not_write",
                media_type="application/octet-stream",
                inputs=[_edge(source, "one", source.manifest_profile_sha256)],
            ),
        )
    assert not _target_blob(root, target).exists()


def test_callback_carrier_may_update_owner_without_lock_reentry(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    writer = FileSystemCAS(root).with_ambient_ownership_enforcement()
    owner = writer.for_tenant("tenant-a", cell_id="cell-a")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        source = _source(writer, b"callback carrier source", "1.0")
        carrier_calls = 0

        class Carrier:
            def model_dump(self, *, mode: str) -> dict[str, str | None]:
                nonlocal carrier_calls
                carrier_calls += 1
                if carrier_calls == 1:
                    owner.record_artifact_owner(source.artifact_id)
                return {
                    "artifact_id": str(source.artifact_id),
                    "role": "callback",
                    "manifest_profile_sha256": source.manifest_profile_sha256,
                }

        result = writer.put_bytes(
            b"callback carrier target",
            PutOptions(
                kind="test.callback_result",
                media_type="application/octet-stream",
                inputs=[_edge(source, "typed", source.manifest_profile_sha256), Carrier()],
            ),
        )
        manifest = writer.get_manifest(result)
    assert [edge.role for edge in manifest.inputs] == ["typed", "callback"]
    assert carrier_calls >= 3


def test_owner_queries_revalidate_content_and_return_detached_rows(tmp_path: Path) -> None:
    index = ArtifactOwnershipIndex(tmp_path / "cas")
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    profile = "sha256:" + "b" * 64
    index.record_owner(artifact_id, tenant_id="tenant-a", cell_id="cell-a")
    index.record_view_owner(artifact_id, profile, tenant_id="tenant-a", cell_id="cell-a")
    assert index.is_owned_by(artifact_id, tenant_id="tenant-a", cell_id="cell-a")
    assert index.is_view_owned_by(artifact_id, profile, tenant_id="tenant-a", cell_id="cell-a")
    rows = index.owners_for(artifact_id)
    rows[0]["tenant_id"] = "mutated-in-public-copy"
    assert index.is_owned_by(artifact_id, tenant_id="tenant-a", cell_id="cell-a")
    assert not index.is_owned_by(artifact_id, tenant_id="tenant-b", cell_id="cell-a")
    assert not index.is_view_owned_by(artifact_id, profile, tenant_id="tenant-a", cell_id="cell-b")

    pointer = json.loads(index.path.read_bytes())
    generation_path = index._generation_path(pointer["generation_sha256"])
    original = generation_path.read_bytes()
    metadata = generation_path.stat()
    tampered = bytearray(original)
    tampered[0] = ord(" ")
    generation_path.write_bytes(tampered)
    os.utime(generation_path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    with pytest.raises(ValueError, match="ownership_index_generation_invalid"):
        index.is_view_owned_by(artifact_id, profile, tenant_id="tenant-a", cell_id="cell-a")
    generation_path.write_bytes(original)
    os.utime(generation_path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    assert index.is_view_owned_by(artifact_id, profile, tenant_id="tenant-a", cell_id="cell-a")


def test_owner_query_observes_new_generation_from_another_index(tmp_path: Path) -> None:
    root = tmp_path / "cas"
    first = ArtifactOwnershipIndex(root)
    second = ArtifactOwnershipIndex(root)
    initial = ArtifactID.from_sha256_hex("c" * 64)
    newly_claimed = ArtifactID.from_sha256_hex("d" * 64)
    first.record_owner(initial, tenant_id="tenant-a", cell_id="cell-a")
    assert not first.is_owned_by(newly_claimed, tenant_id="tenant-a", cell_id="cell-a")
    second.record_owner(newly_claimed, tenant_id="tenant-a", cell_id="cell-a")
    assert first.is_owned_by(newly_claimed, tenant_id="tenant-a", cell_id="cell-a")
