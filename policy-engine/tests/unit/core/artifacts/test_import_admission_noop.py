"""Exercise import admission before staging and exact same-owner no-op."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions

PAYLOAD = b"bound admission payload"


@pytest.fixture(autouse=True)
def _remove_lease_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("E02_B_PROPERTY_REMOVAL") != "cas-import-admission":
        return

    @contextmanager
    def allow_every_member(self: FileSystemCAS, members: dict[str, Any]) -> Any:
        yield transfer.TransferAdmission(
            (), frozenset(str(transfer.artifact_id_from_member(member)) for member in members)
        )

    monkeypatch.setattr(FileSystemCAS, "_admit_import_members", allow_every_member)


def _options(tenant: str | None, cell: str | None = None) -> PutOptions:
    return PutOptions(
        kind="tests.import.admission",
        media_type="application/octet-stream",
        tenant_context=(
            ArtifactTenantContextInfo(tenant_id=tenant, cell_id=cell) if tenant else None
        ),
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    # Persistent empty lock files are synchronization resources, not authority
    # members. Every blob, sidecar, claim, signature and generation stays bound.
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and not p.name.endswith(".lock")
    }


@pytest.mark.parametrize("consumer", ["directory", "archive", "exact"])
@pytest.mark.parametrize("case", ["unclaimed_unbound", "claimed_unbound", "foreign", "cell"])
def test_scoped_import_refuses_before_any_stage_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, case: str
) -> None:
    """Actual foreign/unbound imports leave every receiving member and claim untouched."""
    source_tenant = None if "unbound" in case else "tenant-a"
    source_cell = "cell-a" if case == "cell" else None
    source = FileSystemCAS(tmp_path / "source", tenant_id=source_tenant, cell_id=source_cell)
    ref = source.put_bytes(PAYLOAD, _options(source_tenant, source_cell))
    root = tmp_path / "target"
    target_tenant = "tenant-b" if case == "foreign" else "tenant-a"
    target_cell = "cell-b" if case == "cell" else None
    target = FileSystemCAS(root, tenant_id=target_tenant, cell_id=target_cell)
    if case == "claimed_unbound":
        target.put_bytes(PAYLOAD, _options(target_tenant))
    before = _snapshot(root)
    staged: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            staged.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    with pytest.raises(ArtifactOwnershipError):
        if consumer == "exact":
            target.import_exact_view(PAYLOAD, source.get_manifest_bytes(ref), artifact_id=ref)
        else:
            export = source.export_subgraph(
                [ref], tmp_path / "package", compress=consumer == "archive"
            )
            target.import_subgraph(export.output_path, verify_integrity=True)
    assert staged == [], "authority admission occurred after private filesystem staging"
    assert _snapshot(root) == before


@pytest.mark.parametrize("consumer", ["directory", "archive", "exact"])
@pytest.mark.parametrize("cell", [None, "cell-a"])
def test_exact_same_owner_import_is_a_real_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, cell: str | None
) -> None:
    """A real owner reimport returns a readable exact view without staging/generation change."""
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a", cell_id=cell)
    ref = target.put_bytes(PAYLOAD, _options("tenant-a", cell))
    data, manifest = target.get_bytes(ref), target.get_manifest_bytes(ref)
    export = target.export_subgraph([ref], tmp_path / "package", compress=consumer == "archive")
    before = _snapshot(target.root)
    make_stage = store_module.tempfile.mkdtemp
    staged: list[Path] = []

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            staged.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    if consumer == "exact":
        imported = target.import_exact_view(data, manifest, artifact_id=ref)
    else:
        report = target.import_subgraph(export.output_path, verify_integrity=True)
        assert not report.verification_failed
        assert report.imported_files == 0
        imported = next(r for r in report.imported_refs if r == ref)
    assert staged == []
    assert _snapshot(target.root) == before
    reopened = FileSystemCAS(target.root, tenant_id="tenant-a", cell_id=cell)
    assert reopened.get_bytes(imported) == PAYLOAD
    assert reopened.get_manifest_bytes(imported) == manifest
    assert reopened.verify(imported).ok


@pytest.mark.parametrize("consumer", ["directory", "archive", "exact"])
@pytest.mark.parametrize("mutation", ["new_manifest_bytes", "omitted_signature"])
def test_claimed_view_requires_exact_metadata_and_signature(
    tmp_path: Path, consumer: str, mutation: str
) -> None:
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    ref = target.put_bytes(PAYLOAD, _options("tenant-a"))
    signer = Ed25519Signer.from_pem(KeyPair.generate().private_pem())
    target.sign_artifact(ref, signer, signer_identity="existing-owner")
    source = FileSystemCAS(tmp_path / "source-cache")
    if mutation == "new_manifest_bytes":
        changed = target.get_manifest(ref).model_copy(
            update={"created_at": target.get_manifest(ref).created_at + timedelta(seconds=1)}
        )
        source_ref = source.import_exact_view(
            PAYLOAD, target._manifests.to_bytes(changed), artifact_id=ref
        )
        assert source.get_manifest_bytes(source_ref) != target.get_manifest_bytes(ref)
        assert source_ref.manifest_profile_sha256 == ref.manifest_profile_sha256
    else:
        # Reuse the exact owned manifest, but possession without its existing
        # detached signature is not a complete claimed-view no-op.
        source_ref = source.import_exact_view(
            PAYLOAD, target.get_manifest_bytes(ref), artifact_id=ref
        )
    before = _snapshot(target.root)
    with pytest.raises(ArtifactOwnershipError):
        if consumer == "exact":
            target.import_exact_view(
                PAYLOAD, source.get_manifest_bytes(source_ref), artifact_id=ref
            )
        else:
            export = source.export_subgraph(
                [source_ref], tmp_path / "package", compress=consumer == "archive"
            )
            target.import_subgraph(export.output_path, verify_integrity=True)
    assert _snapshot(target.root) == before
    assert FileSystemCAS(target.root, tenant_id="tenant-a").get_bytes(ref) == PAYLOAD


@pytest.mark.parametrize("consumer", ["archive", "exact"])
def test_bound_unclaimed_import_recovers_exact_durable_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-a")
    ref = source.put_bytes(PAYLOAD, _options("tenant-a"))
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    export = source.export_subgraph([ref], tmp_path / "package")

    def import_once() -> Any:
        if consumer == "exact":
            return target.import_exact_view(
                PAYLOAD, source.get_manifest_bytes(ref), artifact_id=ref
            )
        return target.import_subgraph(export.output_path, verify_integrity=True)

    publish = target._publish_transaction_member

    def interrupt(*args: Any, **kwargs: Any) -> Any:
        raise OSError("injected interruption after durable import intent")

    monkeypatch.setattr(target, "_publish_transaction_member", interrupt)
    with pytest.raises(OSError, match="after durable import intent"):
        import_once()
    with pytest.raises(ArtifactOwnershipError) as error:
        target.get_bytes(ref)
    assert getattr(error.value, "code", None) == "artifact_transaction_pending"
    monkeypatch.setattr(target, "_publish_transaction_member", publish)
    result = import_once()
    imported = result if consumer == "exact" else next(r for r in result.imported_refs if r == ref)
    reopened = FileSystemCAS(target.root, tenant_id="tenant-a")
    assert reopened.get_bytes(imported) == PAYLOAD
    assert reopened.get_manifest_bytes(imported) == source.get_manifest_bytes(ref)
    assert reopened.verify(imported).ok


@pytest.mark.parametrize("source_bound", [False, True])
def test_passive_unscoped_cache_is_not_scoped_admission(tmp_path: Path, source_bound: bool) -> None:
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-a" if source_bound else None)
    ref = source.put_bytes(PAYLOAD, _options("tenant-a" if source_bound else None))
    cache = FileSystemCAS(tmp_path / "cache")
    imported = cache.import_exact_view(PAYLOAD, source.get_manifest_bytes(ref), artifact_id=ref)
    assert cache.get_bytes(imported) == PAYLOAD
    assert cache.get_manifest_bytes(imported) == source.get_manifest_bytes(ref)
    assert not cache._ownership_index.has_any_tenant_claim(ref.artifact_id)


@pytest.mark.parametrize(("source_cell", "target_cell"), [(None, "cell-a"), ("cell-a", None)])
def test_cell_none_is_exact_identity_not_a_query_wildcard(
    tmp_path: Path, source_cell: str | None, target_cell: str | None
) -> None:
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-a", cell_id=source_cell)
    ref = source.put_bytes(PAYLOAD, _options("tenant-a", source_cell))
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a", cell_id=target_cell)
    before = _snapshot(target.root)
    with pytest.raises(ArtifactOwnershipError, match="different cell"):
        target.import_exact_view(PAYLOAD, source.get_manifest_bytes(ref), artifact_id=ref)
    assert _snapshot(target.root) == before


@pytest.mark.parametrize("context", [_options("tenant-b"), _options("tenant-a", "foreign-cell")])
def test_generic_put_refuses_explicit_bound_identity_mismatch_before_intent(
    tmp_path: Path, context: PutOptions
) -> None:
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    before = _snapshot(target.root)
    with pytest.raises(ArtifactOwnershipError, match="bound to a different"):
        target.put_bytes(PAYLOAD, context)
    assert _snapshot(target.root) == before


def test_import_keeps_its_actual_artifact_lease_through_staging_and_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FileSystemCAS(tmp_path / "source", tenant_id="tenant-a")
    ref = source.put_bytes(PAYLOAD, _options("tenant-a"))
    export = source.export_subgraph([ref], tmp_path / "package")
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    competitor = FileSystemCAS(target.root, tenant_id="tenant-a")
    staging = threading.Event()
    release = threading.Event()
    competing = threading.Event()
    completed = threading.Event()
    make_stage = store_module.tempfile.mkdtemp

    def pause_stage(*args: Any, **kwargs: Any) -> str:
        path = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            staging.set()
            assert release.wait(10)
        return path

    def competing_put() -> Any:
        competing.set()
        try:
            return competitor.put_bytes(PAYLOAD, _options("tenant-a"))
        finally:
            completed.set()

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", pause_stage)
    with ThreadPoolExecutor(max_workers=2) as executor:
        importing = executor.submit(
            target.import_subgraph, export.output_path, verify_integrity=True
        )
        assert staging.wait(10)
        writing = executor.submit(competing_put)
        try:
            assert competing.wait(10)
            assert not completed.wait(0.1), "competing writer escaped the admitted artifact lease"
        finally:
            release.set()
        report = importing.result(timeout=10)
        competing_ref = writing.result(timeout=10)
    imported = next(r for r in report.imported_refs if r == ref)
    reopened = FileSystemCAS(target.root, tenant_id="tenant-a")
    assert reopened.get_bytes(imported) == PAYLOAD
    assert reopened.get_manifest_bytes(imported) == source.get_manifest_bytes(ref)
    assert reopened.get_bytes(competing_ref) == PAYLOAD


def test_mixed_package_stages_only_unclaimed_artifact_members(tmp_path: Path) -> None:
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    existing = target.put_bytes(PAYLOAD, _options("tenant-a"))
    source = FileSystemCAS(tmp_path / "passive-source")
    copied = source.import_exact_view(
        PAYLOAD, target.get_manifest_bytes(existing), artifact_id=existing
    )
    new = source.put_bytes(b"unclaimed payload", _options("tenant-a"))
    old_members = {
        str(path.relative_to(target.root)): path.read_bytes()
        for path in target.root.rglob("*")
        if path.is_file() and existing.artifact_id.hex in path.name
    }
    export = source.export_subgraph([copied, new], tmp_path / "package")
    report = target.import_subgraph(export.output_path, verify_integrity=True)
    assert report.imported_files == 2
    assert report.imported_artifacts == 2
    assert existing in report.imported_refs
    assert target.get_bytes(new) == b"unclaimed payload"
    for member, content in old_members.items():
        assert (target.root / member).read_bytes() == content


from polisyos.core.artifacts import _transfer_ops as transfer
from polisyos.core.artifacts import store as store_module
