"""Exercise import admission before staging and exact same-owner no-op."""

import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import _transfer_ops as transfer
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.manifest import (
    ArtifactTenantContextInfo,
    ProducerInfo,
    SchemaInfo,
)
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
@pytest.mark.parametrize("case", ["claimed_unbound", "foreign", "cell"])
def test_scoped_import_refuses_before_any_stage_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, case: str
) -> None:
    """Foreign or already-claimed mismatched imports leave receiver state untouched."""
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
def test_unbound_first_claim_preserves_source_context_and_records_local_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    """A first local claim leaves absent producer context absent and unasserted."""
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(PAYLOAD, _options(None))
    source_manifest = source.get_manifest_bytes(ref)
    assert source.get_manifest(ref).tenant_context is None

    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    stages: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            stages.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    if consumer == "exact":
        imported = target.import_exact_view(PAYLOAD, source_manifest, artifact_id=ref)
    else:
        export = source.export_subgraph([ref], tmp_path / "package", compress=consumer == "archive")
        report = target.import_subgraph(export.output_path, verify_integrity=True)
        assert report.verification_failed == []
        imported = next(
            imported_ref for imported_ref in report.imported_refs if imported_ref == ref
        )

    reopened = FileSystemCAS(target.root, tenant_id="tenant-a")
    assert stages
    assert source.get_manifest_bytes(ref) == source_manifest
    assert source.get_manifest(ref).tenant_context is None
    assert reopened.get_manifest_bytes(imported) == source_manifest
    assert reopened.get_manifest(imported).tenant_context is None
    assert reopened._ownership_index.is_owned_by(
        ref.artifact_id, tenant_id="tenant-a", cell_id=None
    )
    assert not source._ownership_index.has_any_tenant_claim(ref.artifact_id)
    assert reopened.get_bytes(imported) == PAYLOAD
    assert reopened.verify(imported).ok


def test_two_tenant_first_unbound_import_race_has_one_local_default_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first scoped import owns locally; a real contender waits at the CAS lease."""
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(PAYLOAD, _options(None))
    source_manifest = source.get_manifest_bytes(ref)
    assert source.get_manifest(ref).tenant_context is None
    package = source.export_subgraph([ref], tmp_path / "package")

    target_root = tmp_path / "target"
    shared = FileSystemCAS(target_root)
    tenants = {
        "tenant-a": shared.for_tenant("tenant-a"),
        "tenant-b": shared.for_tenant("tenant-b"),
    }
    start = threading.Barrier(3)
    worker = threading.local()
    stage_labels: list[str | None] = []
    publication_labels: list[str | None] = []
    publication_snapshots: dict[str | None, dict[str, bytes]] = {}
    publication_attempted = {label: threading.Event() for label in tenants}
    publication_entered = {label: threading.Event() for label in tenants}
    pending_intent_written = threading.Event()
    release_publication = threading.Event()
    coordination_lock = threading.Lock()
    publication_candidate: dict[str, str | None] = {"label": None}
    publication_owner: dict[str, str | None] = {"label": None}
    make_stage = store_module.tempfile.mkdtemp
    publish = FileSystemCAS._publish_staged_import
    publish_transaction_member = FileSystemCAS._publish_transaction_member
    coordinator = shared._coordinator
    original_artifact_leases = coordinator.artifact_leases
    original_stripe = coordinator._stripe
    default_path = shared._manifest_path_for_ref(ref.artifact_id, None)
    remove_lock_probe = os.environ.get("POLISYOS_B148_REMOVE_FIRST_CLAIM_LOCK_PROBE")
    if remove_lock_probe not in {None, "1"}:
        raise ValueError("POLISYOS_B148_REMOVE_FIRST_CLAIM_LOCK_PROBE must be unset or 1")

    if remove_lock_probe == "1":

        def route_contender_around_publication_lock(candidate_id: Any) -> int:
            if (
                getattr(worker, "route_around_publication_lock", False)
                and candidate_id == ref.artifact_id
            ):
                return (original_stripe(candidate_id) + 1) % len(coordinator._artifact_locks)
            return original_stripe(candidate_id)

        monkeypatch.setattr(coordinator, "_stripe", route_contender_around_publication_lock)

    @contextmanager
    def observe_artifact_leases(artifact_ids: Any, *, exclusive: bool) -> Any:
        ids = tuple(artifact_ids)
        tracked = (
            getattr(worker, "in_import", False)
            and getattr(worker, "lease_depth", 0) == 0
            and exclusive
            and ref.artifact_id in ids
        )
        if not tracked:
            with original_artifact_leases(ids, exclusive=exclusive) as leases:
                yield leases
            return

        label = getattr(worker, "tenant", None)
        assert label in publication_attempted
        with coordination_lock:
            if publication_candidate["label"] is None:
                publication_candidate["label"] = label
            is_candidate = publication_candidate["label"] == label
        publication_attempted[label].set()
        if remove_lock_probe == "1" and not is_candidate:
            if not pending_intent_written.wait(timeout=10):
                raise AssertionError("first import never reached its pending transaction intent")
            worker.route_around_publication_lock = True
        try:
            with original_artifact_leases(ids, exclusive=exclusive) as leases:
                with coordination_lock:
                    if publication_owner["label"] is None:
                        publication_owner["label"] = label
                    is_owner = publication_owner["label"] == label
                if not is_owner:
                    publication_entered[label].set()
                worker.lease_depth = 1
                try:
                    yield leases
                finally:
                    worker.lease_depth = 0
        finally:
            worker.route_around_publication_lock = False

    def persisted_snapshot() -> dict[str, bytes]:
        return {
            path.relative_to(target_root).as_posix(): path.read_bytes()
            for path in target_root.rglob("*")
            if path.is_file()
            and not path.name.endswith(".lock")
            and not any(
                part.startswith(".cas-import-") for part in path.relative_to(target_root).parts
            )
        }

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        path = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            stage_labels.append(getattr(worker, "tenant", None))
        return path

    def observe_publication(
        store: FileSystemCAS,
        staging_root: Path,
        members: set[str],
        artifact_ids: set[str],
    ) -> Any:
        label = getattr(worker, "tenant", None)
        publication_labels.append(label)
        try:
            return publish(store, staging_root, members, artifact_ids)
        finally:
            publication_snapshots[label] = persisted_snapshot()

    def pause_before_default_manifest(
        store: FileSystemCAS,
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        label = getattr(worker, "tenant", None)
        if final_path == default_path and label == publication_owner["label"]:
            intent = store._ownership_index._read_transaction_intent(ref.artifact_id)
            assert intent is not None
            assert intent["status"] == "pending"
            assert intent["owner"] == {"tenant_id": label, "cell_id": None}
            pending_intent_written.set()
            if not release_publication.wait(timeout=10):
                raise AssertionError("the first-owner publication was never released")
        return publish_transaction_member(
            store,
            stage_path,
            final_path,
            expected_sha256=expected_sha256,
        )

    monkeypatch.setattr(coordinator, "artifact_leases", observe_artifact_leases)
    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    monkeypatch.setattr(FileSystemCAS, "_publish_staged_import", observe_publication)
    monkeypatch.setattr(FileSystemCAS, "_publish_transaction_member", pause_before_default_manifest)

    def import_for_tenant(label: str) -> tuple[str, Any]:
        worker.tenant = label
        worker.in_import = True
        worker.lease_depth = 0
        worker.route_around_publication_lock = False
        try:
            start.wait(timeout=10)
            report = tenants[label].import_subgraph(package.output_path, verify_integrity=True)
            return ("published", report)
        except ArtifactOwnershipError as exc:
            return ("refused", exc)
        finally:
            worker.in_import = False
            worker.lease_depth = 0
            worker.route_around_publication_lock = False

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {label: pool.submit(import_for_tenant, label) for label in tenants}
        start.wait(timeout=10)
        try:
            assert pending_intent_written.wait(timeout=10)
            winner = publication_owner["label"]
            assert winner in tenants
            loser = next(label for label in tenants if label != winner)
            assert publication_attempted[loser].wait(timeout=10)
            stripe_lock = coordinator._artifact_locks[original_stripe(ref.artifact_id)]
            acquired_unexpectedly = stripe_lock.acquire(blocking=False)
            if acquired_unexpectedly:
                stripe_lock.release()
            assert not acquired_unexpectedly, "the first import must hold the actual CAS stripe"
            assert not publication_entered[loser].wait(timeout=0.1), (
                "the losing import entered the first-claim lease before publication completed"
            )
        finally:
            release_publication.set()
        outcomes = {label: future.result(timeout=20) for label, future in futures.items()}

    winners = [
        (label, result)
        for label, (status, result) in outcomes.items()
        if status == "published" and isinstance(result, transfer.ImportReport)
    ]
    losers = [
        (label, result)
        for label, (status, result) in outcomes.items()
        if status == "refused" and isinstance(result, ArtifactOwnershipError)
    ]
    assert len(winners) == len(losers) == 1
    winner, report = winners[0]
    loser, refusal = losers[0]
    assert winner == publication_owner["label"]
    assert winner != loser
    assert len(report.published_refs) == 1
    assert report.published_refs[0].artifact_id == ref.artifact_id
    # Publication receipts identify immutable manifest bytes; default selection
    # remains available separately through imported_refs and the fresh receiver.
    assert ref in report.imported_refs
    published = report.published_refs[0]
    assert published.manifest_profile_sha256 == source._manifests.profile_sha256(
        source.get_manifest(ref)
    )
    assert len(stage_labels) == len(publication_labels) == 1
    assert stage_labels == publication_labels == [winner]
    assert set(publication_snapshots) == {winner}
    assert persisted_snapshot() == publication_snapshots[winner]
    assert "exact view is not owned" in str(refusal)

    fresh_winner = FileSystemCAS(target_root, tenant_id=winner)
    fresh_loser = FileSystemCAS(target_root, tenant_id=loser)
    assert fresh_winner.get_bytes(ref) == PAYLOAD
    assert fresh_winner.get_manifest_bytes(ref) == source_manifest
    assert fresh_winner.get_manifest_bytes(published) == source_manifest
    assert fresh_winner.get_bytes(published) == PAYLOAD
    assert fresh_winner.verify(published).ok
    assert fresh_winner.get_manifest(ref).tenant_context is None
    assert fresh_winner.verify(ref).ok
    assert fresh_winner._ownership_index.is_owned_by(
        ref.artifact_id, tenant_id=winner, cell_id=None
    )
    assert not fresh_loser._ownership_index.is_owned_by(
        ref.artifact_id, tenant_id=loser, cell_id=None
    )
    assert not fresh_loser.has(ref)
    with pytest.raises(ArtifactOwnershipError):
        fresh_loser.get_bytes(ref)


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


@pytest.mark.parametrize("pause_at", ["staging", "publication"])
@pytest.mark.parametrize("package_format", ["directory", "tar"])
def test_import_lease_rejects_same_blob_competing_selected_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pause_at: str,
    package_format: str,
    record_property: Any,
) -> None:
    """A competing manifest profile waits through import staging and publication."""
    tenant_id = "tenant-b148"

    def options(owner: str) -> PutOptions:
        return PutOptions(
            kind=f"tests.b148.owner-{owner}",
            media_type="application/octet-stream",
            schema=SchemaInfo(name=f"tests.b148.owner-{owner}", version="1"),
            producer=ProducerInfo(component=f"tests.b148.owner-{owner}", version="1"),
            tenant_context=ArtifactTenantContextInfo(tenant_id=tenant_id),
        )

    source_a = FileSystemCAS(tmp_path / "source-a", tenant_id=tenant_id)
    ref_a = source_a.put_bytes(PAYLOAD, options("a"), return_selected_profile=True)
    source_b = FileSystemCAS(tmp_path / "source-b", tenant_id=tenant_id)
    ref_b = source_b.put_bytes(PAYLOAD, options("b"), return_selected_profile=True)
    assert ref_a.artifact_id == ref_b.artifact_id
    assert ref_a.manifest_profile_sha256 is not None
    assert ref_b.manifest_profile_sha256 is not None
    assert ref_a.manifest_profile_sha256 != ref_b.manifest_profile_sha256
    assert ref_a.kind != ref_b.kind
    assert source_a.get_bytes(ref_a) == source_b.get_bytes(ref_b) == PAYLOAD
    manifest_a = source_a.get_manifest_bytes(ref_a)
    manifest_b = source_b.get_manifest_bytes(ref_b)
    assert manifest_a != manifest_b
    record_property("b148_pause_at", pause_at)
    record_property("b148_package_format", package_format)
    record_property("b148_backend", "FileSystemCAS")
    record_property("b148_tenant_id", tenant_id)
    record_property("b148_payload_sha256", ref_a.artifact_id.hex)
    record_property("b148_source_a_selected_ref", ref_a.model_dump_json())
    record_property("b148_source_b_selected_ref", ref_b.model_dump_json())
    record_property("b148_source_a_manifest_sha256", hashlib.sha256(manifest_a).hexdigest())
    record_property("b148_source_b_manifest_sha256", hashlib.sha256(manifest_b).hexdigest())

    compress = package_format == "tar"
    package_a = source_a.export_subgraph([ref_a], tmp_path / "package-a", compress=compress)
    package_b = source_b.export_subgraph([ref_b], tmp_path / "package-b", compress=compress)
    target_root = tmp_path / "target"
    target = FileSystemCAS(target_root, tenant_id=tenant_id)

    first_stage_entered = threading.Event()
    first_publication_entered = threading.Event()
    release_first = threading.Event()
    competing_admission_attempted = threading.Event()
    competing_admission_acquired = threading.Event()
    competing_stage_entered = threading.Event()
    competing_done = threading.Event()
    first_snapshot: dict[str, dict[str, bytes]] = {}
    stage_threads: list[str] = []
    stage_threads_lock = threading.Lock()

    def durable_snapshot() -> dict[str, bytes]:
        return {
            str(path.relative_to(target_root)): path.read_bytes()
            for path in target_root.rglob("*")
            if path.is_file()
            and not path.name.endswith(".lock")
            and not any(
                part.startswith(".cas-import-") for part in path.relative_to(target_root).parts
            )
        }

    current_admit = target._admit_import_members

    @contextmanager
    def observe_admission(members: dict[str, Any]) -> Any:
        is_competitor = threading.current_thread().name.startswith("b148-competitor")
        if is_competitor:
            competing_admission_attempted.set()
        with current_admit(members) as admission:
            if is_competitor:
                competing_admission_acquired.set()
            yield admission

    monkeypatch.setattr(target, "_admit_import_members", observe_admission)

    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        path = make_stage(*args, **kwargs)
        if not str(kwargs.get("prefix", "")).startswith(".cas-import"):
            return path
        thread_name = threading.current_thread().name
        with stage_threads_lock:
            stage_threads.append(thread_name)
        if thread_name.startswith("b148-competitor"):
            competing_stage_entered.set()
        elif thread_name.startswith("b148-first"):
            first_stage_entered.set()
            if pause_at == "staging":
                assert release_first.wait(10)
        return path

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)

    publish_staged = target._publish_staged_import

    def observe_publication(staging_root: Path, members: set[str], artifact_refs: set[str]) -> Any:
        is_first = threading.current_thread().name.startswith("b148-first")
        if is_first:
            first_publication_entered.set()
            if pause_at == "publication":
                assert release_first.wait(10)
        result = publish_staged(staging_root, members, artifact_refs)
        if is_first:
            first_snapshot["value"] = durable_snapshot()
        return result

    monkeypatch.setattr(target, "_publish_staged_import", observe_publication)

    def import_competitor() -> Any:
        try:
            return target.import_subgraph(package_b.output_path, verify_integrity=True)
        finally:
            competing_done.set()

    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="b148-first") as first_pool,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="b148-competitor") as competitor_pool,
    ):
        first_import = first_pool.submit(
            target.import_subgraph, package_a.output_path, verify_integrity=True
        )
        first_pause = first_stage_entered if pause_at == "staging" else first_publication_entered
        competing_import: Any | None = None
        try:
            assert first_pause.wait(10), "first import did not reach the requested lease boundary"
            competing_import = competitor_pool.submit(import_competitor)
            assert competing_admission_attempted.wait(10), (
                "competing import did not reach its actual admission boundary"
            )
            admitted_before_release = competing_admission_acquired.wait(0.2)
            staged_before_release = competing_stage_entered.wait(0.2)
            completed_before_release = competing_done.wait(0.2)
        finally:
            release_first.set()

        try:
            first_result = first_import.result(timeout=20)
        except Exception as exc:
            first_result = exc
        try:
            competing_result = competing_import.result(timeout=20) if competing_import else None
        except Exception as exc:
            competing_result = exc

    assert not (admitted_before_release or staged_before_release or completed_before_release), (
        "competing selected view crossed the held import lease: "
        f"admitted={admitted_before_release}, staged={staged_before_release}, "
        f"completed={completed_before_release}"
    )
    assert isinstance(competing_result, ArtifactOwnershipError)
    assert "exact view is not owned" in str(competing_result)
    assert isinstance(first_result, transfer.ImportReport)
    assert first_result.published_refs == (ref_a,)
    assert first_snapshot["value"] == durable_snapshot()
    assert not any(name.startswith("b148-competitor") for name in stage_threads)

    assert target.get_bytes(ref_a) == PAYLOAD
    assert target.get_manifest_bytes(ref_a) == source_a.get_manifest_bytes(ref_a)
    assert target.get_manifest(ref_a).kind == ref_a.kind
    assert target.verify(ref_a).ok


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


@pytest.mark.parametrize("consumer", ["directory", "archive"])
@pytest.mark.parametrize("foreign_scope", ["tenant", "cell"])
def test_mixed_package_with_foreign_member_refuses_before_stage_and_preserves_prior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
    foreign_scope: str,
) -> None:
    """A valid new member cannot publish alongside a foreign tenant/cell member."""
    tenant_id, cell_id = "tenant-a", "cell-a"
    target = FileSystemCAS(tmp_path / "target", tenant_id=tenant_id, cell_id=cell_id)
    prior_payload = b"previously readable tenant-a cell-a artifact"
    prior = target.put_bytes(prior_payload, _options(tenant_id, cell_id))
    prior_manifest = target.get_manifest_bytes(prior)

    # The ordinary exporter sorts members by content id. Choose authentic
    # payloads with the valid member first, so an incremental admission/stage
    # implementation cannot pass merely because the foreign member arrived first.
    for index in range(128):
        valid_payload = f"valid-new-{index}".encode()
        foreign_payload = f"foreign-member-{index}".encode()
        valid_digest = hashlib.sha256(valid_payload).hexdigest()
        foreign_digest = hashlib.sha256(foreign_payload).hexdigest()
        if valid_digest < foreign_digest:
            break
    else:
        pytest.fail("could not construct deterministic valid-first transfer input")

    valid_source = FileSystemCAS(tmp_path / "valid-source", tenant_id=tenant_id, cell_id=cell_id)
    valid_new = valid_source.put_bytes(valid_payload, _options(tenant_id, cell_id))
    foreign_tenant, foreign_cell = (
        ("tenant-b", cell_id) if foreign_scope == "tenant" else (tenant_id, "cell-b")
    )
    foreign_source = FileSystemCAS(
        tmp_path / "foreign-source", tenant_id=foreign_tenant, cell_id=foreign_cell
    )
    foreign = foreign_source.put_bytes(foreign_payload, _options(foreign_tenant, foreign_cell))
    assert valid_source._ownership_index.is_owned_by(
        valid_new.artifact_id, tenant_id=tenant_id, cell_id=cell_id
    )
    assert foreign_source._ownership_index.is_owned_by(
        foreign.artifact_id, tenant_id=foreign_tenant, cell_id=foreign_cell
    )
    assert valid_new.artifact_id.hex < foreign.artifact_id.hex

    # Rebuild one authentic transfer set from the two scoped producer views. The
    # unscoped bundle is only a byte-preserving transport cache; it has no owner
    # claim and cannot turn either producer's manifest into a local assertion.
    bundle = FileSystemCAS(tmp_path / "bundle")
    valid_manifest = valid_source.get_manifest_bytes(valid_new)
    foreign_manifest = foreign_source.get_manifest_bytes(foreign)
    bundle.import_exact_view(valid_payload, valid_manifest, artifact_id=valid_new)
    bundle.import_exact_view(foreign_payload, foreign_manifest, artifact_id=foreign)
    assert bundle.get_manifest_bytes(valid_new) == valid_manifest
    assert bundle.get_manifest_bytes(foreign) == foreign_manifest
    assert not bundle._ownership_index.has_any_tenant_claim(valid_new.artifact_id)
    assert not bundle._ownership_index.has_any_tenant_claim(foreign.artifact_id)
    package = bundle.export_subgraph(
        [valid_new, foreign],
        tmp_path / "mixed-package",
        compress=consumer == "archive",
    )

    before = _snapshot(target.root)
    staged: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            staged.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    with pytest.raises(ArtifactOwnershipError):
        target.import_subgraph(package.output_path, verify_integrity=True)

    assert staged == [], "mixed-set admission occurred after private filesystem staging"
    assert _snapshot(target.root) == before
    reopened = FileSystemCAS(target.root, tenant_id=tenant_id, cell_id=cell_id)
    assert reopened.get_bytes(prior) == prior_payload
    assert reopened.get_manifest_bytes(prior) == prior_manifest
    assert reopened.verify(prior).ok
    assert not reopened.has(valid_new.artifact_id)
    assert not reopened.has(foreign.artifact_id)


def test_mixed_import_reports_profile_identity_and_actual_manifest_disposition(
    tmp_path: Path,
) -> None:
    """Default aliases collapse by profile; only the new selected profile is published."""
    payload = b"same blob with two immutable manifest profiles"
    source = FileSystemCAS(tmp_path / "source")
    default = source.put_bytes(payload, _options(None))
    alias = source.put_bytes(payload, _options(None), return_selected_profile=True)
    distinct = source.put_bytes(
        payload,
        PutOptions(
            kind="tests.import.distinct-profile",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="tests.import.distinct-profile", version="1"),
            producer=ProducerInfo(component="tests.import", version="1"),
        ),
        return_selected_profile=True,
    )
    default_profile = source._manifests.profile_sha256(source.get_manifest(default))
    distinct_profile = distinct.manifest_profile_sha256
    assert alias.manifest_profile_sha256 == default_profile
    assert distinct_profile is not None and distinct_profile != default_profile

    target = FileSystemCAS(tmp_path / "target")
    first_bundle = source.export_subgraph([default], tmp_path / "default-only", compress=False)
    first = target.import_subgraph(first_bundle.output_path, verify_integrity=True)
    assert first.published_refs == (
        type(default)(
            artifact_id=default.artifact_id,
            kind=default.kind,
            media_type=default.media_type,
            manifest_profile_sha256=default_profile,
        ),
    )
    assert first.reused_refs == ()
    assert first.integrity_verified_refs == first.published_refs
    assert first.disposition_basis == "durable_owner_manifest_stage_intent"

    full_bundle = source.export_subgraph(
        [default, alias, distinct], tmp_path / "all-profiles", compress=False
    )
    report = target.import_subgraph(full_bundle.output_path, verify_integrity=True)
    assert report.imported_artifacts == 1
    assert report.received_artifact_ids == (str(default.artifact_id),)
    assert len(report.imported_refs) == 3  # Compatibility: preserve request selectors.
    assert {ref.manifest_profile_sha256 for ref in report.published_refs} == {distinct_profile}
    assert {ref.manifest_profile_sha256 for ref in report.reused_refs} == {default_profile}
    assert {ref.manifest_profile_sha256 for ref in report.integrity_verified_refs} == {
        default_profile,
        distinct_profile,
    }
    assert target.get_manifest(distinct).kind == "tests.import.distinct-profile"


def test_exact_noop_verification_is_real_and_false_is_not_a_positive(
    tmp_path: Path,
) -> None:
    """A requested no-op verifies the stored pair; an unrequested one stays unverified."""
    target = FileSystemCAS(tmp_path / "target", tenant_id="tenant-a")
    ref = target.put_bytes(b"same-owner no-op", _options("tenant-a"))
    export = target.export_subgraph([ref], tmp_path / "package", compress=False)

    verified = target.import_subgraph(export.output_path, verify_integrity=True)
    assert verified.imported_refs == (ref,)
    assert verified.published_refs == ()
    assert len(verified.reused_refs) == 1
    assert len(verified.integrity_verified_refs) == 1
    assert verified.integrity_verification_requested is True
    assert verified.disposition_basis == "exact_owned_view_admission"

    unverified = target.import_subgraph(export.output_path, verify_integrity=False)
    assert unverified.reused_refs == verified.reused_refs
    assert unverified.integrity_verified_refs == ()
    assert unverified.integrity_verification_requested is False
