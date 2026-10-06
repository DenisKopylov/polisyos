"""Bound import metadata must agree with the active scoped write owner."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope


def _opts(context: ArtifactTenantContextInfo | None) -> PutOptions:
    return PutOptions(
        kind="test.bound_import", media_type="application/octet-stream", tenant_context=context
    )


def _import(
    source: FileSystemCAS, target: FileSystemCAS, ref: ArtifactRef, route: str, output: Path
):
    if route == "exact-view":
        manifest = source.get_manifest(ref)
        selected = ref.model_copy(
            update={"manifest_profile_sha256": ManifestLifecycle.profile_sha256(manifest)}
        )
        return target.import_exact_view(
            source.get_bytes(ref), source.get_manifest_bytes(ref), artifact_id=selected
        )
    exported = source.export_subgraph([ref], output, compress=route == "archive")
    return target.import_subgraph(exported.output_path, verify_integrity=True).imported_refs[0]


@pytest.mark.parametrize("route", ["archive", "directory", "exact-view"])
@pytest.mark.parametrize(
    ("bound_tenant", "bound_cell", "owner_tenant", "owner_cell"),
    [
        ("tenant-a", None, "tenant-b", None),
        ("tenant-a", "cell-a", "tenant-a", "cell-b"),
        ("tenant-a", None, "tenant-a", "cell-a"),
        ("tenant-a", "cell-a", "tenant-a", None),
    ],
    ids=["foreign-tenant", "foreign-cell", "none-to-cell", "cell-to-none"],
)
def test_scoped_import_refuses_bound_identity_mismatch_before_intent_or_claims(
    tmp_path, monkeypatch, route, bound_tenant, bound_cell, owner_tenant, owner_cell
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(
        b"bound imported bytes",
        _opts(ArtifactTenantContextInfo(tenant_id=bound_tenant, cell_id=bound_cell)),
    )
    target = FileSystemCAS(tmp_path / "target").for_tenant(owner_tenant, cell_id=owner_cell)
    sentinel = target.put_bytes(b"old readable generation", _opts(None))
    before_manifest = target.get_manifest_bytes(sentinel)
    calls = []
    write_intent = target._ownership_index.write_transaction_intent

    def capture_intent(*args, **kwargs):
        calls.append(args)
        return write_intent(*args, **kwargs)

    monkeypatch.setattr(target._ownership_index, "write_transaction_intent", capture_intent)
    with pytest.raises(ArtifactOwnershipError, match=r"bound to a different (tenant|cell)"):
        _import(source, target, ref, route, tmp_path / "package")

    assert calls == []
    assert not target._ownership_index.has_any_tenant_claim(ref.artifact_id)
    assert target._ownership_index._read_transaction_intent(ref.artifact_id) is None
    assert not target.has(ref)
    reopened = FileSystemCAS(target.root).for_tenant(owner_tenant, cell_id=owner_cell)
    assert reopened.get_bytes(sentinel) == b"old readable generation"
    assert reopened.get_manifest_bytes(sentinel) == before_manifest


@pytest.mark.parametrize("route", ["archive", "directory", "exact-view"])
@pytest.mark.parametrize("cell", [None, "cell-a"])
def test_matching_bound_import_preserves_exact_manifest_and_claims(tmp_path, route, cell) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(
        b"matching bound bytes",
        _opts(ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id=cell)),
    )
    manifest_bytes = source.get_manifest_bytes(ref)
    target = FileSystemCAS(tmp_path / "target").for_tenant("tenant-a", cell_id=cell)
    imported = _import(source, target, ref, route, tmp_path / "package")
    reopened = FileSystemCAS(target.root).for_tenant("tenant-a", cell_id=cell)

    assert reopened.get_bytes(imported) == b"matching bound bytes"
    assert reopened.get_manifest_bytes(imported) == manifest_bytes
    assert reopened._ownership_index.is_view_owned_by(
        ref.artifact_id,
        ManifestLifecycle.profile_sha256(source.get_manifest(ref)),
        tenant_id="tenant-a",
        cell_id=cell,
    )


@pytest.mark.parametrize("route", ["archive", "directory", "exact-view"])
def test_unbound_import_can_admit_an_independent_view_of_foreign_owned_bytes(
    tmp_path, route
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(b"legitimate shared bytes", _opts(None))
    root = tmp_path / "shared"
    first = FileSystemCAS(root).for_tenant("tenant-a", cell_id="cell-a")
    old_ref = first.put_bytes(b"legitimate shared bytes", _opts(None))
    old_manifest = first.get_manifest_bytes(old_ref)
    target = FileSystemCAS(root).for_tenant("tenant-b", cell_id="cell-b")
    imported = _import(source, target, ref, route, tmp_path / "package")

    assert imported.manifest_profile_sha256 is not None
    assert target.get_bytes(imported) == b"legitimate shared bytes"
    assert target.has(old_ref.artifact_id) is False
    assert first.get_manifest_bytes(old_ref) == old_manifest
    assert first.get_bytes(old_ref) == b"legitimate shared bytes"


@pytest.mark.parametrize("route", ["archive", "directory", "exact-view"])
def test_unscoped_custody_preserves_bound_context_without_tenant_admission(tmp_path, route) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(
        b"passive bound custody",
        _opts(ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")),
    )
    target = FileSystemCAS(tmp_path / "passive")
    # An ambient scope does not turn an intentionally unscoped byte cache into
    # a durable tenant owner. Its runtime caller must still authorize the read.
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        imported = _import(source, target, ref, route, tmp_path / "package")

    assert target.get_bytes(imported) == b"passive bound custody"
    assert target.get_manifest_bytes(imported) == source.get_manifest_bytes(ref)
    assert not target._ownership_index.has_any_tenant_claim(ref.artifact_id)


@pytest.mark.parametrize("route", ["archive", "directory"])
def test_mixed_import_refuses_all_new_claims_before_publishing_a_valid_first_member(
    tmp_path, monkeypatch, route
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    # Import publication is sorted by content ID. Put a valid member first so
    # a per-artifact guard would leave its durable claim behind before refusing.
    payloads = sorted(
        (f"mixed-{n}".encode() for n in range(2)),
        key=lambda value: hashlib.sha256(value).hexdigest(),
    )
    valid = source.put_bytes(payloads[0], _opts(ArtifactTenantContextInfo(tenant_id="tenant-a")))
    foreign = source.put_bytes(payloads[1], _opts(ArtifactTenantContextInfo(tenant_id="tenant-b")))
    exported = source.export_subgraph(
        [valid, foreign], tmp_path / "package", compress=route == "archive"
    )
    target = FileSystemCAS(tmp_path / "target").for_tenant("tenant-a")
    calls = []
    write_intent = target._ownership_index.write_transaction_intent

    def capture_intent(*args, **kwargs):
        calls.append(args)
        return write_intent(*args, **kwargs)

    monkeypatch.setattr(target._ownership_index, "write_transaction_intent", capture_intent)
    with pytest.raises(ArtifactOwnershipError, match="bound to a different tenant"):
        target.import_subgraph(exported.output_path, verify_integrity=True)

    assert calls == []
    for ref in (valid, foreign):
        assert not target._ownership_index.has_any_tenant_claim(ref.artifact_id)
        assert not target.has(ref)


def test_ambient_scoped_import_refuses_foreign_bound_context(tmp_path) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(
        b"ambient bound bytes", _opts(ArtifactTenantContextInfo(tenant_id="tenant-a"))
    )
    target = FileSystemCAS(tmp_path / "target").with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-b"):
        with pytest.raises(ArtifactOwnershipError, match="bound to a different tenant"):
            _import(source, target, ref, "exact-view", tmp_path / "package")
    assert not target._ownership_index.has_any_tenant_claim(ref.artifact_id)


@pytest.mark.parametrize("json_write", [False, True], ids=["bytes", "json"])
@pytest.mark.parametrize(
    ("bound_tenant", "bound_cell", "owner_cell"),
    [
        ("tenant-b", None, None),
        ("tenant-a", "cell-b", "cell-a"),
        ("tenant-a", None, "cell-a"),
        ("tenant-a", "cell-a", None),
    ],
    ids=["foreign-tenant", "foreign-cell", "none-to-cell", "cell-to-none"],
)
def test_scoped_put_refuses_bound_identity_mismatch_before_intent_or_claims(
    tmp_path, monkeypatch, json_write, bound_tenant, bound_cell, owner_cell
) -> None:
    target = FileSystemCAS(tmp_path / "target").for_tenant("tenant-a", cell_id=owner_cell)
    calls = []
    write_intent = target._ownership_index.write_transaction_intent

    def capture_intent(*args, **kwargs):
        calls.append(args)
        return write_intent(*args, **kwargs)

    monkeypatch.setattr(target._ownership_index, "write_transaction_intent", capture_intent)
    options = _opts(ArtifactTenantContextInfo(tenant_id=bound_tenant, cell_id=bound_cell))
    with pytest.raises(ArtifactOwnershipError, match=r"bound to a different (tenant|cell)"):
        if json_write:
            target.put_json({"bound": "mismatch"}, options)
        else:
            target.put_bytes(b"bound mismatch", options)
    assert calls == []
    assert target.iter_artifact_ids() == []


def test_pending_legacy_bound_mismatch_is_refused_before_put_recovery_mutates_state(
    tmp_path, monkeypatch
) -> None:
    target = FileSystemCAS(tmp_path / "target").for_tenant("tenant-b")
    data = b"legacy mismatched pending publication"
    options = _opts(ArtifactTenantContextInfo(tenant_id="tenant-a"))
    publish_member = target._publish_transaction_member

    def interrupt_member(*args, **kwargs):
        raise RuntimeError("paused after durable intent")

    # Seed a real pre-fix pending transaction without rewriting intent bytes or
    # owner files. The scoped admission helper is disabled only for this seed.
    with monkeypatch.context() as seed:
        seed.setattr(target, "_require_bound_context_owner", lambda *args: None, raising=False)
        seed.setattr(target, "_publish_transaction_member", interrupt_member)
        with pytest.raises(RuntimeError, match="paused after durable intent"):
            target.put_bytes(data, options)

    from polisyos.core.artifacts.ids import ArtifactID

    artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest())
    before = target._ownership_index._read_transaction_intent(artifact_id)
    assert before is not None and before["status"] == "pending"
    monkeypatch.setattr(target, "_publish_transaction_member", publish_member)
    with pytest.raises(ArtifactOwnershipError, match="bound to a different tenant"):
        target.put_bytes(data, options)

    assert target._ownership_index._read_transaction_intent(artifact_id) == before
    assert not target._ownership_index.has_any_tenant_claim(artifact_id)
    assert not target._paths(artifact_id)[0].exists()


@pytest.mark.parametrize("route", ["archive", "directory"])
def test_mixed_manifest_views_of_one_blob_are_all_checked_before_any_admission(
    tmp_path, route
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    matching = source.put_bytes(
        b"one blob two bound views", _opts(ArtifactTenantContextInfo(tenant_id="tenant-a"))
    )
    foreign = source.put_bytes(
        b"one blob two bound views", _opts(ArtifactTenantContextInfo(tenant_id="tenant-b"))
    )
    assert matching.artifact_id == foreign.artifact_id
    assert foreign.manifest_profile_sha256 is not None
    exported = source.export_subgraph(
        [matching, foreign], tmp_path / "package", compress=route == "archive"
    )
    target = FileSystemCAS(tmp_path / "target").for_tenant("tenant-a")

    with pytest.raises(ArtifactOwnershipError, match="bound to a different tenant"):
        target.import_subgraph(exported.output_path, verify_integrity=True)
    assert not target._ownership_index.has_any_tenant_claim(matching.artifact_id)
    assert not target.has(matching)


def test_pending_legacy_bound_mismatch_is_refused_before_import_recovery_mutates_state(
    tmp_path, monkeypatch
) -> None:
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(
        b"legacy pending bound import", _opts(ArtifactTenantContextInfo(tenant_id="tenant-a"))
    )
    exported = source.export_subgraph([ref], tmp_path / "package")
    target = FileSystemCAS(tmp_path / "target").for_tenant("tenant-b")

    def interrupt_member(*args, **kwargs):
        raise RuntimeError("paused after durable intent")

    with monkeypatch.context() as seed:
        seed.setattr(target, "_require_bound_context_owner", lambda *args: None, raising=False)
        seed.setattr(target, "_publish_transaction_member", interrupt_member)
        with pytest.raises(RuntimeError, match="paused after durable intent"):
            target.import_subgraph(exported.output_path, verify_integrity=True)
    before = target._ownership_index._read_transaction_intent(ref.artifact_id)
    assert before is not None and before["status"] == "pending"

    with pytest.raises(ArtifactOwnershipError, match="bound to a different tenant"):
        target.import_subgraph(exported.output_path, verify_integrity=True)
    assert target._ownership_index._read_transaction_intent(ref.artifact_id) == before
    assert not target._ownership_index.has_any_tenant_claim(ref.artifact_id)
    assert not target._paths(ref.artifact_id)[0].exists()
