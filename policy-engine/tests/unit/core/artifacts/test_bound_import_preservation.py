"""Verify bound import custody through real persisted receiver reads."""

import hashlib
import json
import os
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts import _transfer_ops as transfer
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

PAYLOAD = b"existing bound artifact remains readable"


def _options(tenant: str, cell: str | None) -> PutOptions:
    return PutOptions(
        kind="tests.bound_import.preservation",
        media_type="application/octet-stream",
        tenant_context=ArtifactTenantContextInfo(tenant_id=tenant, cell_id=cell),
    )


def _persisted_bytes(root: Path) -> dict[str, bytes]:
    # Empty lock files are synchronization resources, not published custody.
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    }


def _byte_inventory(snapshot: dict[str, bytes]) -> dict[str, dict[str, int | str]]:
    return {
        name: {"byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in snapshot.items()
    }


def _fresh_readback(store: FileSystemCAS, ref: ArtifactRef) -> dict[str, Any]:
    """Capture genuine public reads before the defining assertion can stop a test."""
    observation: dict[str, Any] = {
        "ref": ref.model_dump(mode="json"),
        "data_hex": None,
        "manifest_hex": None,
        "verification_ok": None,
        "error": None,
    }
    try:
        observation["data_hex"] = store.get_bytes(ref).hex()
        observation["manifest_hex"] = store.get_manifest_bytes(ref).hex()
        observation["verification_ok"] = store.verify(ref).ok
    except Exception as exc:
        observation["error"] = {"type": type(exc).__name__, "message": str(exc)}
    return observation


@pytest.fixture(autouse=True)
def _matched_admission_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("E02_B_PROPERTY_REMOVAL") == "bound-import-claimed-admission":
        monkeypatch.setattr(
            FileSystemCAS, "_admit_import_members", removed_claimed_import_admission
        )


@pytest.mark.parametrize("consumer", ["directory", "archive", "exact"])
@pytest.mark.parametrize("cell", [None, "cell-a"])
def test_matching_bound_import_cannot_reclaim_an_existing_foreign_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, cell: str | None
) -> None:
    """Matching incoming context cannot erase a distinct durable owner claim."""
    owner = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a", cell_id=cell)
    owned = owner.put_bytes(PAYLOAD, _options("tenant-a", cell))
    old_manifest = owner.get_manifest_bytes(owned)
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-b", cell_id=cell)
    incoming = source.put_bytes(PAYLOAD, _options("tenant-b", cell))
    incoming_manifest = source.get_manifest(incoming)
    assert incoming_manifest.tenant_context == ArtifactTenantContextInfo(
        tenant_id="tenant-b", cell_id=cell
    )
    selected_incoming = ArtifactRef(
        artifact_id=incoming.artifact_id,
        kind=incoming.kind,
        media_type=incoming.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(incoming_manifest),
    )
    target = FileSystemCAS(owner.root, tenant_id="tenant-b", cell_id=cell)
    before = _persisted_bytes(owner.root)
    stages: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            stages.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    result: Any = None
    error: Exception | None = None
    returned_refs: tuple[ArtifactRef, ...] = ()
    try:
        if consumer == "exact":
            result = target.import_exact_view(
                PAYLOAD, source.get_manifest_bytes(incoming), artifact_id=incoming
            )
            returned_refs = (result,)
        else:
            exported = source.export_subgraph(
                [incoming], tmp_path / "package", compress=consumer == "archive"
            )
            result = target.import_subgraph(exported.output_path, verify_integrity=True)
            returned_refs = result.imported_refs
    except Exception as exc:
        error = exc

    # Retain effects before asserting refusal. An admission removal can preserve
    # default owner A while publishing a new selected view and reader for B.
    after = _persisted_bytes(owner.root)
    reopened_a = FileSystemCAS(owner.root, tenant_id="tenant-a", cell_id=cell)
    reopened_b = FileSystemCAS(owner.root, tenant_id="tenant-b", cell_id=cell)
    assert selected_incoming.manifest_profile_sha256 is not None
    claims_b = reopened_b._ownership_index._transaction_claims_for(
        owned.artifact_id,
        tenant_id="tenant-b",
        cell_id=cell,
        manifest_profile_sha256=selected_incoming.manifest_profile_sha256,
    )
    old_readback = _fresh_readback(reopened_a, owned)
    selected_readback = _fresh_readback(reopened_b, selected_incoming)
    returned_readbacks = [_fresh_readback(reopened_b, ref) for ref in returned_refs]
    observation = {
        "consumer": consumer,
        "cell": cell,
        "removal": os.environ.get("E02_B_PROPERTY_REMOVAL"),
        "actual_result_type": type(result).__name__ if result is not None else None,
        "actual_error": (
            {"type": type(error).__name__, "message": str(error)} if error is not None else None
        ),
        "returned_refs": [ref.model_dump(mode="json") for ref in returned_refs],
        "private_stages": [str(path) for path in stages],
        "persisted_before": _byte_inventory(before),
        "persisted_after": _byte_inventory(after),
        "changed_paths": sorted(
            name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
        ),
        "tenant_b_exact_claims": claims_b,
        "tenant_a_original_readback": old_readback,
        "tenant_b_selected_readback": selected_readback,
        "tenant_b_returned_readbacks": returned_readbacks,
    }
    encoded = json.dumps(observation, sort_keys=True)
    (tmp_path / "foreign-owner-observation.json").write_text(encoded + "\n", encoding="utf-8")
    print(encoded)

    assert isinstance(error, ArtifactOwnershipError), observation
    assert "exact view is not owned" in str(error), observation
    assert returned_refs == ()
    assert stages == []
    assert after == before
    assert old_readback["error"] is None
    assert old_readback["data_hex"] == PAYLOAD.hex()
    assert old_readback["manifest_hex"] == old_manifest.hex()
    assert old_readback["verification_ok"] is True
    assert selected_readback["error"] is not None
    assert claims_b == {"default_owner": False, "blob_reader": False, "view_owners": []}
    assert not target._ownership_index.is_owned_by(
        owned.artifact_id, tenant_id="tenant-b", cell_id=cell
    )


@pytest.mark.parametrize("consumer", ["directory", "archive"])
@pytest.mark.parametrize("damage", ["different_bytes", "truncated"])
def test_bad_bound_inventory_preserves_the_readable_claimed_view(
    tmp_path: Path, consumer: str, damage: str
) -> None:
    """Content failure reports no publication and retains the exact bound view."""
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a", cell_id="cell-a")
    owned = target.put_bytes(PAYLOAD, _options("tenant-a", "cell-a"))
    old_manifest = target.get_manifest_bytes(owned)
    exported = target.export_subgraph([owned], tmp_path / "package", compress=False)
    blob = exported.output_path / target._paths(owned.artifact_id)[0].relative_to(target.root)
    damaged = b"x" * len(PAYLOAD) if damage == "different_bytes" else PAYLOAD[:3]
    assert damaged != PAYLOAD
    blob.write_bytes(damaged)
    source = exported.output_path
    if consumer == "archive":
        source = tmp_path / "damaged.tar.gz"
        with tarfile.open(source, "w:gz") as archive:
            for member in sorted(exported.output_path.rglob("*")):
                if member.is_file():
                    archive.add(member, arcname=member.relative_to(exported.output_path).as_posix())
    before = _persisted_bytes(target.root)
    report = target.import_subgraph(source, verify_integrity=True)
    assert report.imported_files == 0
    assert report.imported_refs == ()
    assert report.verification_failed == [str(owned.artifact_id)]
    assert _persisted_bytes(target.root) == before
    reopened = FileSystemCAS(target.root, tenant_id="tenant-a", cell_id="cell-a")
    assert reopened.get_bytes(owned) == PAYLOAD
    assert reopened.get_manifest_bytes(owned) == old_manifest
    assert reopened.verify(owned).ok


def test_physically_interrupted_bound_archive_read_preserves_existing_custody(
    tmp_path: Path,
) -> None:
    """A truncated real gzip member stream cannot replace an acknowledged view."""
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    owned = target.put_bytes(PAYLOAD, _options("tenant-a", None))
    old_manifest = target.get_manifest_bytes(owned)
    exported = target.export_subgraph([owned], tmp_path / "package", compress=True)
    archive_bytes = exported.output_path.read_bytes()
    exported.output_path.write_bytes(archive_bytes[: len(archive_bytes) // 2])
    before = _persisted_bytes(target.root)
    with pytest.raises((EOFError, tarfile.TarError, OSError)):
        target.import_subgraph(exported.output_path, verify_integrity=True)
    assert _persisted_bytes(target.root) == before
    reopened = FileSystemCAS(target.root, tenant_id="tenant-a")
    assert reopened.get_bytes(owned) == PAYLOAD
    assert reopened.get_manifest_bytes(owned) == old_manifest
    assert reopened.verify(owned).ok


def test_changed_directory_bytes_after_intake_never_publish_a_scoped_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real source change between intake and staging preserves prior custody."""
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    owned = target.put_bytes(PAYLOAD, _options("tenant-a", None))
    old_manifest = target.get_manifest_bytes(owned)
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-a")
    new_payload = b"new bound source bytes"
    incoming = source.put_bytes(new_payload, _options("tenant-a", None))
    exported = source.export_subgraph([incoming], tmp_path / "package", compress=False)
    incoming_blob = exported.output_path / source._paths(incoming.artifact_id)[0].relative_to(
        source.root
    )
    before = _persisted_bytes(target.root)
    stages: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def alter_source_after_admission(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            stages.append(Path(result))
            assert incoming_blob.read_bytes() == new_payload
            incoming_blob.write_bytes(new_payload[:3])
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", alter_source_after_admission)
    report = target.import_subgraph(exported.output_path, verify_integrity=True)
    assert len(stages) == 1, "source mutation did not reach the post-intake stage boundary"
    assert report.imported_files == 0
    assert report.imported_refs == ()
    assert report.verification_failed == [str(incoming.artifact_id)]
    assert _persisted_bytes(target.root) == before
    reopened = FileSystemCAS(target.root, tenant_id="tenant-a")
    assert reopened.get_bytes(owned) == PAYLOAD
    assert reopened.get_manifest_bytes(owned) == old_manifest
    assert reopened.verify(owned).ok
    assert not reopened.has(incoming)


@contextmanager
def removed_claimed_import_admission(
    self: FileSystemCAS, members: dict[str, transfer.TransferMemberSnapshot]
) -> Iterator[transfer.TransferAdmission]:
    """Matched in-memory removal retains real inventory, digest and publication."""
    yield transfer.TransferAdmission(
        (),
        frozenset(str(transfer.artifact_id_from_member(member)) for member in members),
    )
