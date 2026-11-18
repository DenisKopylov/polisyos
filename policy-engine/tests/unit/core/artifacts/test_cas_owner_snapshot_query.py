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
from polisyos.core.artifacts import ArtifactIntegrityError
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
        captured_operations = capture.serialized_operation_refs()
        assert {entry["operation"] for entry in captured_operations} == {
            "get_bytes",
            "get_manifest",
        }
        assert all(
            entry["artifact_id"] == str(source.artifact_id)
            and entry["manifest_profile_sha256"] == source.manifest_profile_sha256
            for entry in captured_operations
        )
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


def test_selected_manifest_reads_reuse_one_current_ownership_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scoped selected reads authorize blob and view from one freshly loaded generation."""
    root = tmp_path / "cas"
    tenant_a = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    tenant_b = FileSystemCAS(root).for_tenant("tenant-b", cell_id="cell-b")
    a_view = _source(tenant_a, b"shared source bytes", "1.0")
    b_view = _source(tenant_b, b"shared source bytes", "2.0")
    assert a_view.artifact_id == b_view.artifact_id
    assert a_view.manifest_profile_sha256 is not None
    assert b_view.manifest_profile_sha256 is not None

    index = tenant_a._ownership_index
    generation_loads = 0
    original_load = index._load_generation_snapshot

    def observe_load(pointer_bytes: bytes):
        nonlocal generation_loads
        generation_loads += 1
        return original_load(pointer_bytes)

    monkeypatch.setattr(index, "_load_generation_snapshot", observe_load)
    assert tenant_a.get_raw_manifest_bytes(a_view)
    assert generation_loads == 1

    generation_loads = 0
    selected_manifest = tenant_a.get_manifest_by_profile(
        a_view.artifact_id, a_view.manifest_profile_sha256
    )
    assert selected_manifest.kind == a_view.kind
    assert generation_loads == 1

    generation_loads = 0
    assert tenant_a.get_bytes(a_view) == b"shared source bytes"
    assert generation_loads == 1
    schema = tenant_a.get_manifest(a_view).artifact_schema
    assert schema is not None and schema.version == "1.0"

    generation_loads = 0
    with pytest.raises(ArtifactOwnershipError, match="Manifest view"):
        tenant_a.get_raw_manifest_bytes(b_view)
    assert generation_loads == 1

    generation_loads = 0
    with pytest.raises(ArtifactOwnershipError, match="Manifest view"):
        tenant_a.get_manifest_by_profile(b_view.artifact_id, b_view.manifest_profile_sha256)
    assert generation_loads == 1

    tenant_c = FileSystemCAS(root).for_tenant("tenant-c", cell_id="cell-c")
    tenant_c._ownership_index.record_view_owner(
        b_view.artifact_id,
        b_view.manifest_profile_sha256,
        tenant_id="tenant-c",
        cell_id="cell-c",
    )
    with pytest.raises(ArtifactOwnershipError, match="payload is not readable"):
        tenant_c.get_raw_manifest_bytes(b_view)
    with pytest.raises(ArtifactOwnershipError, match="payload is not readable"):
        tenant_c.get_manifest_by_profile(b_view.artifact_id, b_view.manifest_profile_sha256)

    # Tenant B has a blob grant and selected-view claim, but no default-view claim.
    assert tenant_b.get_manifest_by_profile(b_view.artifact_id, b_view.manifest_profile_sha256)
    with pytest.raises(ArtifactOwnershipError, match="not owned"):
        tenant_b.get_raw_manifest_bytes(b_view.artifact_id)

    tenant_a._ownership_index.record_view_owner(
        a_view.artifact_id,
        b_view.manifest_profile_sha256,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    fresh_index = ArtifactOwnershipIndex(root)
    fresh_reader = FileSystemCAS(
        root,
        tenant_id="tenant-a",
        cell_id="cell-a",
        ownership_enforced=True,
        ownership_requires_scope=True,
        ownership_index=fresh_index,
    )
    fresh_loads = 0
    original_fresh_load = fresh_index._load_generation_snapshot

    def observe_fresh_load(pointer_bytes: bytes):
        nonlocal fresh_loads
        fresh_loads += 1
        return original_fresh_load(pointer_bytes)

    monkeypatch.setattr(fresh_index, "_load_generation_snapshot", observe_fresh_load)
    assert fresh_reader.get_raw_manifest_bytes(b_view)
    assert fresh_loads == 1
    fresh_loads = 0
    assert fresh_reader.get_manifest_by_profile(b_view.artifact_id, b_view.manifest_profile_sha256)
    assert fresh_loads == 1

    # The blob-only/default path remains available through its existing authorization route.
    default = tenant_a.put_bytes(
        b"default-view payload",
        PutOptions(kind="test.default", media_type="application/octet-stream"),
    )
    assert tenant_a.get_bytes(default) == b"default-view payload"


@pytest.mark.parametrize(
    ("member_state", "expected_error"),
    [
        ("missing_blob", FileNotFoundError),
        ("missing_manifest", FileNotFoundError),
        ("same_byte_blob_symlink", ArtifactIntegrityError),
    ],
)
def test_tenant_scoped_selected_get_bytes_refuses_missing_or_symlinked_members(
    tmp_path: Path, member_state: str, expected_error: type[Exception]
) -> None:
    """The optimized selected read still requires the exact on-disk members."""
    root = tmp_path / "cas"
    store = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    payload = b"tenant-scoped selected read member control"
    default_view = _source(store, payload, "1.0")
    selected = _source(store, payload, "2.0")
    assert selected.artifact_id == default_view.artifact_id
    assert selected.manifest_profile_sha256 != default_view.manifest_profile_sha256
    blob_path = _target_blob(root, payload)
    default_manifest_path = store._manifest_path_for_ref(
        default_view.artifact_id, default_view.manifest_profile_sha256
    )
    selected_manifest_path = store._manifest_path_for_ref(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    assert default_manifest_path != selected_manifest_path

    if member_state == "missing_blob":
        blob_path.unlink()
    elif member_state == "missing_manifest":
        assert default_manifest_path.is_file()
        selected_manifest_path.unlink()
    else:
        external_blob = tmp_path / "same-byte-external-blob.bin"
        external_blob.write_bytes(payload)
        blob_path.unlink()
        blob_path.symlink_to(external_blob)

    with pytest.raises(expected_error):
        store.get_bytes(selected)

    if member_state == "same_byte_blob_symlink":
        assert external_blob.read_bytes() == payload


def test_runtime_style_optional_scope_reuses_only_for_present_tenant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Runtime base store shares the snapshot only while a tenant owns the read."""
    runtime_store = FileSystemCAS(
        tmp_path / "cas", ownership_enforced=True, ownership_requires_scope=False
    )
    writer = runtime_store.for_tenant("tenant-a", cell_id="cell-a")
    selected = _source(writer, b"scoped primary bytes", "1.0")
    loads = []
    original = runtime_store._ownership_index._load_generation_snapshot

    def observe(pointer_bytes: bytes):
        loads.append(pointer_bytes)
        return original(pointer_bytes)

    monkeypatch.setattr(runtime_store._ownership_index, "_load_generation_snapshot", observe)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert runtime_store.get_raw_manifest_bytes(selected)
    assert len(loads) == 1
    loads.clear()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert runtime_store.get_manifest_by_profile(
            selected.artifact_id, selected.manifest_profile_sha256
        )
    assert len(loads) == 1
    with pytest.raises(ArtifactOwnershipError):
        runtime_store.get_raw_manifest_bytes(selected)
    with pytest.raises(ArtifactOwnershipError):
        runtime_store.get_manifest_by_profile(
            selected.artifact_id, selected.manifest_profile_sha256
        )


def test_selected_read_preserves_custom_ownership_index_dispatch(tmp_path: Path) -> None:
    """A custom ownership index keeps the existing separate virtual authorization calls."""

    class DispatchIndex(ArtifactOwnershipIndex):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.blob_checks = 0
            self.view_checks = 0

        def require_blob_reader(
            self,
            artifact_id: ArtifactID | str,
            *,
            tenant_id: str,
            cell_id: str | None = None,
            operation: str = "read",
        ) -> None:
            self.blob_checks += 1
            return super().require_blob_reader(
                artifact_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                operation=operation,
            )

        def require_view_owner(
            self,
            artifact_id: ArtifactID | str,
            manifest_profile_sha256: str,
            *,
            tenant_id: str,
            cell_id: str | None = None,
            operation: str = "read",
        ) -> None:
            self.view_checks += 1
            return super().require_view_owner(
                artifact_id,
                manifest_profile_sha256,
                tenant_id=tenant_id,
                cell_id=cell_id,
                operation=operation,
            )

    root = tmp_path / "cas"
    stock_writer = FileSystemCAS(root)
    scoped_writer = stock_writer.for_tenant("tenant-a", cell_id="cell-a")
    selected = _source(scoped_writer, b"subclass dispatch", "1.0")
    assert selected.manifest_profile_sha256 is not None

    index = DispatchIndex(root)
    scoped_reader = FileSystemCAS(
        root,
        tenant_id="tenant-a",
        cell_id="cell-a",
        ownership_enforced=True,
        ownership_requires_scope=True,
        ownership_index=index,
    )
    assert scoped_reader.get_raw_manifest_bytes(selected)
    assert index.blob_checks == 1
    assert index.view_checks == 1
    assert scoped_reader.get_manifest_by_profile(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    assert index.blob_checks == 2
    assert index.view_checks == 2
