from __future__ import annotations

import hashlib
import os
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

import polisyos.core.artifacts.ownership as ownership_module
from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.artifacts import ArtifactID as IRArtifactID
from polisyos.ir.artifacts.contracts import StorePutOptions
from polisyos.runtime.http.services.control.artifacts import write_authority_artifact
from polisyos.runtime.quality.authority import GovernanceMetadata


def test_core_artifact_id_accepts_foreign_artifact_id_wrapper() -> None:
    foreign_artifact_id = IRArtifactID.model_validate("sha256:" + "a" * 64)

    ref = ArtifactRef(
        artifact_id=foreign_artifact_id,
        kind="scientist.workflow_report",
        media_type="application/json",
    )

    assert isinstance(ref.artifact_id, CoreArtifactID)
    assert ref.model_dump(mode="json")["artifact_id"] == "sha256:" + "a" * 64


def test_constructed_artifact_ref_serializes_foreign_artifact_id_without_warning() -> None:
    foreign_artifact_id = IRArtifactID.model_validate("sha256:" + "b" * 64)
    ref = ArtifactRef.model_construct(
        artifact_id=foreign_artifact_id,
        kind="scientist.workflow_report",
        media_type="application/json",
    )

    for mode in ("python", "json"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            payload = ref.model_dump(mode=mode)

        assert payload["artifact_id"] == "sha256:" + "b" * 64
        assert not [
            warning
            for warning in caught
            if "PydanticSerializationUnexpectedValue" in str(warning.message)
        ]


def test_tenant_scoped_cas_keeps_canonical_content_hashes_without_cross_tenant_reads(
    tmp_path,
) -> None:
    store_a = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    store_b = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-b")
    opts = PutOptions(kind="test.tenant_payload", media_type="application/json")

    ref_a = store_a.put_json({"same": "payload"}, opts)

    assert str(ref_a.artifact_id).startswith("sha256:")
    assert store_a.has(ref_a.artifact_id) is True
    assert store_b.has(ref_a.artifact_id) is False
    with pytest.raises(ArtifactOwnershipError):
        store_b.get_bytes(ref_a.artifact_id)

    ref_b = store_b.put_json({"same": "payload"}, opts)

    assert ref_b.artifact_id == ref_a.artifact_id
    assert store_b.has(ref_b) is True
    assert store_b.has(ref_a.artifact_id) is False
    assert store_b.get_bytes(ref_b) == store_a.get_bytes(ref_a.artifact_id)


def test_view_only_tenant_never_reads_foreign_default_manifest(tmp_path, monkeypatch) -> None:
    shared_root = tmp_path / "cas"
    store_a = FileSystemCAS(shared_root).for_tenant("tenant-a")
    store_b = FileSystemCAS(shared_root).for_tenant("tenant-b")
    payload = b"shared bytes with independently owned typed manifests"
    owner_opts = PutOptions(kind="test.tenant_a_default", media_type="text/plain")
    view_opts = PutOptions(kind="test.tenant_b_view", media_type="text/plain")

    ref_a = store_a.put_bytes(payload, owner_opts)
    default_path = store_b._manifest_path_for_ref(ref_a.artifact_id, None)
    default_bytes_before = default_path.read_bytes()

    original_read = store_b._manifests.read
    default_reads = []
    selected_reads = []
    selected_paths = []

    def spy_read(path):
        resolved_path = Path(path)
        if resolved_path == default_path:
            default_reads.append(resolved_path)
        if selected_paths and resolved_path == selected_paths[0]:
            selected_reads.append(resolved_path)
        return original_read(path)

    monkeypatch.setattr(store_b._manifests, "read", spy_read)

    ref_b = store_b.put_bytes(payload, view_opts)
    assert ref_b.manifest_profile_sha256 is not None
    selected_path = store_b._manifest_path_for_ref(
        ref_b.artifact_id,
        ref_b.manifest_profile_sha256,
    )
    selected_paths.append(selected_path)
    assert selected_path != default_path
    default_reads_after_put = tuple(default_reads)
    assert default_path.read_bytes() == default_bytes_before
    default_reads.clear()

    has_default = store_b.has(ref_a.artifact_id)
    default_reads_after_has = tuple(default_reads)

    direct_read_refused = False
    try:
        store_b.get_manifest(ref_a.artifact_id)
    except ArtifactOwnershipError:
        direct_read_refused = True
    default_reads_after_get_manifest = tuple(default_reads)

    raw_path_api_absent = not hasattr(store_b, "get_paths")
    default_reads_after_path_api_check = tuple(default_reads)

    exact_view_available = store_b.has(ref_b)
    exact_view_manifest = store_b.get_manifest(ref_b)

    owner_reads = []
    original_owner_read = store_a._manifests.read

    def owner_read_spy(path):
        resolved_path = Path(path)
        if resolved_path == default_path:
            owner_reads.append(resolved_path)
        return original_owner_read(path)

    monkeypatch.setattr(store_a._manifests, "read", owner_read_spy)
    repeated_default_ref = store_a.put_bytes(payload, owner_opts)

    assert has_default is False
    assert default_reads_after_put == ()
    assert default_reads_after_has == ()
    assert direct_read_refused is True
    assert default_reads_after_get_manifest == ()
    assert raw_path_api_absent is True
    assert default_reads_after_path_api_check == ()
    assert exact_view_available is True
    assert selected_reads
    assert exact_view_manifest.kind == view_opts.kind
    assert repeated_default_ref.manifest_profile_sha256 is None
    assert owner_reads
    assert default_path.read_bytes() == default_bytes_before

    tampered_manifest = store_a.get_manifest(ref_a).model_copy(
        update={
            "artifact_id": CoreArtifactID.model_validate(
                "sha256:" + "0" * 64,
            )
        }
    )
    default_path.write_bytes(store_a._manifests.to_bytes(tampered_manifest))
    with pytest.raises(ValueError, match="Manifest artifact_id mismatch"):
        store_a.put_bytes(payload, owner_opts)


def test_unscoped_cas_loser_refuses_default_claimed_during_write(
    tmp_path,
    monkeypatch,
) -> None:
    """A same-ID ambient contender waits for publication, then sees the tenant claim."""
    shared_root = tmp_path / "shared"
    ambient = FileSystemCAS(shared_root).with_ambient_ownership_enforcement()
    tenant_a = FileSystemCAS(shared_root, tenant_id="tenant-a")
    payload = b"ambient write loses default-view ownership race"
    ambient_opts = PutOptions(kind="test.ambient_candidate", media_type="text/plain")
    owner_opts = PutOptions(kind="test.tenant_a_default", media_type="text/plain")
    artifact_id = CoreArtifactID.from_sha256_hex(hashlib.sha256(payload).hexdigest())
    default_path = ambient._manifest_path_for_ref(artifact_id, None)

    tenant_publication_ready = threading.Event()
    release_tenant_publication = threading.Event()
    ambient_lease_attempted = threading.Event()
    ambient_lease_entered = threading.Event()
    outcomes: dict[str, ArtifactRef | Exception] = {}
    coordinator = ambient._coordinator
    original_artifact_lease = coordinator.artifact_lease
    lease_removal_probe = os.environ.get(
        "POLISYOS_ARTIFACT_ID_REMOVE_SAME_ID_LEASE_PROBE"
    )
    if lease_removal_probe not in {None, "1"}:
        raise ValueError(
            "POLISYOS_ARTIFACT_ID_REMOVE_SAME_ID_LEASE_PROBE must be unset or 1"
        )

    if lease_removal_probe == "1":
        original_stripe = coordinator._stripe

        def route_contender_to_another_stripe(candidate_id: CoreArtifactID) -> int:
            stripe = original_stripe(candidate_id)
            if (
                candidate_id == artifact_id
                and threading.current_thread().name == "ambient-contender"
            ):
                return (stripe + 1) % len(coordinator._artifact_locks)
            return stripe

        monkeypatch.setattr(coordinator, "_stripe", route_contender_to_another_stripe)

    @contextmanager
    def observe_contender_lease(candidate_id, *, exclusive):
        is_contender = (
            candidate_id == artifact_id
            and threading.current_thread().name == "ambient-contender"
        )
        if is_contender:
            ambient_lease_attempted.set()
        with original_artifact_lease(candidate_id, exclusive=exclusive) as lease:
            if is_contender:
                ambient_lease_entered.set()
            yield lease

    monkeypatch.setattr(coordinator, "artifact_lease", observe_contender_lease)

    original_publish = tenant_a._publish_transaction_member

    def pause_at_default_publication(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        if (
            final_path == default_path
            and threading.current_thread().name == "tenant-owner"
        ):
            intent = tenant_a._ownership_index._read_transaction_intent(artifact_id)
            assert intent is not None
            assert intent["status"] == "pending"
            tenant_publication_ready.set()
            if not release_tenant_publication.wait(timeout=5):
                raise AssertionError("tenant publication was never released")
        return original_publish(
            stage_path,
            final_path,
            expected_sha256=expected_sha256,
        )

    monkeypatch.setattr(
        tenant_a,
        "_publish_transaction_member",
        pause_at_default_publication,
    )

    def run_tenant_owner() -> None:
        try:
            outcomes["tenant"] = tenant_a.put_bytes(payload, owner_opts)
        except Exception as exc:  # surfaced below after both workers are joined
            outcomes["tenant"] = exc

    def run_ambient_contender() -> None:
        try:
            outcomes["ambient"] = ambient.put_bytes(payload, ambient_opts)
        except Exception as exc:  # surfaced below after both workers are joined
            outcomes["ambient"] = exc

    tenant_thread = threading.Thread(
        target=run_tenant_owner,
        name="tenant-owner",
        daemon=True,
    )
    ambient_thread = threading.Thread(
        target=run_ambient_contender,
        name="ambient-contender",
        daemon=True,
    )
    tenant_thread.start()
    try:
        assert tenant_publication_ready.wait(timeout=5)
        assert not default_path.exists()
        ambient_thread.start()
        assert ambient_lease_attempted.wait(timeout=5)
        if lease_removal_probe == "1":
            assert ambient_lease_entered.wait(timeout=2)
        assert not ambient_lease_entered.wait(timeout=0.1)
    finally:
        release_tenant_publication.set()
        tenant_thread.join(timeout=6)
        if ambient_thread.ident is not None:
            ambient_thread.join(timeout=6)

    assert not tenant_thread.is_alive()
    assert not ambient_thread.is_alive()
    owner_result = outcomes.get("tenant")
    ambient_result = outcomes.get("ambient")
    assert isinstance(owner_result, ArtifactRef)
    assert owner_result.manifest_profile_sha256 is None
    assert isinstance(ambient_result, ArtifactOwnershipError)
    assert tenant_a._ownership_index.is_owned_by(
        artifact_id,
        tenant_id="tenant-a",
        cell_id=None,
    )
    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(artifact_id)
    assert tenant_a.get_bytes(owner_result) == payload

    unclaimed_ref = ambient.put_bytes(
        b"separate anonymous candidate remains available",
        ambient_opts,
    )
    assert ambient.has(unclaimed_ref.artifact_id)
    assert ambient.get_bytes(unclaimed_ref.artifact_id) == (
        b"separate anonymous candidate remains available"
    )


def test_ambient_cas_rejects_foreign_tenant_and_cell_claims(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    ref = None
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ref = store.put_bytes(
            b"tenant-a ambient artifact",
            PutOptions(kind="test.ambient_payload", media_type="text/plain"),
        )

    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
        assert store.has(ref.artifact_id) is False
        with pytest.raises(ArtifactOwnershipError):
            store.get_bytes(ref.artifact_id)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-b"):
        assert store.has(ref.artifact_id) is False
        with pytest.raises(ArtifactOwnershipError):
            store.get_bytes(ref.artifact_id)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert store.get_bytes(ref.artifact_id) == b"tenant-a ambient artifact"


def test_ambient_cas_unscoped_claim_check_covers_read_metadata_enumeration_and_paths(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    payload = b"tenant-owned selected-view artifact"
    opts = PutOptions(kind="test.ambient_default", media_type="text/plain")
    view_opts = PutOptions(kind="test.ambient_view", media_type="text/plain")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        default_ref = store.put_bytes(payload, opts)
        view_ref = store.put_bytes(payload, view_opts)
        assert view_ref.manifest_profile_sha256 is not None
        archive = store.export_subgraph(
            [view_ref],
            tmp_path / "tenant-view.tar.gz",
            compress=True,
        )

    with pytest.raises(ArtifactOwnershipError):
        store.get_bytes(default_ref.artifact_id)
    with pytest.raises(ArtifactOwnershipError):
        store.get_manifest(default_ref.artifact_id)
    with pytest.raises(ArtifactOwnershipError):
        store.get_manifest_bytes(view_ref)
    with pytest.raises(ArtifactOwnershipError):
        store.get_signature(view_ref)
    assert not hasattr(store, "get_paths")
    assert store.has(default_ref.artifact_id) is False
    assert store.has_manifest_view(
        view_ref.artifact_id,
        view_ref.manifest_profile_sha256,
    ) is False
    assert default_ref.artifact_id not in store.iter_artifact_ids()
    with pytest.raises(ArtifactOwnershipError):
        store.export_subgraph(
            [view_ref],
            tmp_path / "unscoped-export.tar.gz",
            compress=True,
        )
    assert not (tmp_path / "unscoped-export.tar.gz").exists()
    assert archive.output_path.exists()


def test_ambient_cas_unscoped_candidate_is_preserved_but_claimed_targets_and_inputs_are_denied(
    tmp_path,
) -> None:
    shared_root = tmp_path / "shared"
    store = FileSystemCAS(shared_root).with_ambient_ownership_enforcement()
    owned_data = b"tenant-owned immutable target"
    owned_opts = PutOptions(kind="test.owned_default", media_type="text/plain")
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        owned_ref = store.put_bytes(owned_data, owned_opts)
        owned_manifest_bytes = store.get_manifest_bytes(owned_ref)
        owner_export = store.export_subgraph(
            [owned_ref],
            tmp_path / "owner-export.tar.gz",
            compress=True,
        )

    candidate_ref = store.put_bytes(
        b"unclaimed candidate bytes",
        PutOptions(kind="test.candidate", media_type="text/plain"),
    )
    assert store.get_bytes(candidate_ref.artifact_id) == b"unclaimed candidate bytes"
    assert store.has(candidate_ref.artifact_id)
    assert candidate_ref.artifact_id in store.iter_artifact_ids()

    with pytest.raises(ArtifactOwnershipError):
        store.put_bytes(
            owned_data,
            PutOptions(kind="test.unscoped_second_view", media_type="text/plain"),
        )
    with pytest.raises(ArtifactOwnershipError):
        store.put_bytes(
            b"candidate with foreign lineage",
            PutOptions(
                kind="test.foreign_lineage",
                media_type="text/plain",
                inputs=[{"artifact_id": str(owned_ref.artifact_id), "role": "source"}],
            ),
        )
    with pytest.raises(ArtifactOwnershipError):
        store.import_exact_view(
            owned_data,
            owned_manifest_bytes,
            artifact_id=owned_ref,
        )
    with pytest.raises(ArtifactOwnershipError):
        store.import_subgraph(owner_export.output_path, verify_integrity=True)

    archive_source = FileSystemCAS(tmp_path / "archive-source")
    child = archive_source.put_bytes(
        b"child with claimed input",
        PutOptions(
            kind="test.imported_child",
            media_type="text/plain",
            inputs=[{"artifact_id": str(owned_ref.artifact_id), "role": "source"}],
        ),
    )
    child_export = archive_source.export_subgraph(
        [child],
        tmp_path / "child-export.tar.gz",
        compress=True,
    )
    with pytest.raises(ArtifactOwnershipError):
        store.import_subgraph(child_export.output_path, verify_integrity=True)
    assert not store.has(child.artifact_id)


def test_independent_tenant_writers_preserve_claims_and_ambient_reads_refuse(
    tmp_path,
    monkeypatch,
) -> None:
    shared_root = tmp_path / "shared"
    raw_store = FileSystemCAS(shared_root)
    ambient = FileSystemCAS(shared_root).with_ambient_ownership_enforcement()
    opts = PutOptions(kind="test.concurrent_claim", media_type="text/plain")
    ref_a = raw_store.put_bytes(b"tenant A race payload", opts)
    ref_b = raw_store.put_bytes(b"tenant B race payload", opts)
    index_a = ownership_module.ArtifactOwnershipIndex(shared_root)
    index_b = ownership_module.ArtifactOwnershipIndex(shared_root)
    store_a = FileSystemCAS(
        shared_root,
        tenant_id="tenant-a",
        ownership_index=index_a,
    )
    store_b = FileSystemCAS(
        shared_root,
        tenant_id="tenant-b",
        ownership_index=index_b,
    )
    first_loaded = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    second_loaded = threading.Event()
    original_load = ownership_module.ArtifactOwnershipIndex._load_payload

    def pause_first_snapshot(index: ownership_module.ArtifactOwnershipIndex):
        payload = original_load(index)
        if index is index_a:
            first_loaded.set()
            if not release_first.wait(timeout=5):
                raise AssertionError("first ownership write was not released")
        elif index is index_b:
            second_loaded.set()
        return payload

    monkeypatch.setattr(
        ownership_module.ArtifactOwnershipIndex,
        "_load_payload",
        pause_first_snapshot,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(
            index_a.record_owner,
            ref_a.artifact_id,
            tenant_id="tenant-a",
        )
        assert first_loaded.wait(timeout=5)

        def claim_from_second_index() -> None:
            second_started.set()
            index_b.record_owner(ref_b.artifact_id, tenant_id="tenant-b")

        future_b = executor.submit(claim_from_second_index)
        assert second_started.wait(timeout=5)
        second_loaded_before_commit = second_loaded.wait(timeout=1)
        release_first.set()
        future_a.result(timeout=5)
        future_b.result(timeout=5)

    assert not second_loaded_before_commit, (
        "a second index instance read a stale claim snapshot before the first commit"
    )
    assert ref_a.artifact_id != ref_b.artifact_id
    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(ref_a.artifact_id)
    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(ref_b.artifact_id)
    assert store_a.get_bytes(ref_a.artifact_id) == b"tenant A race payload"
    assert store_b.get_bytes(ref_b.artifact_id) == b"tenant B race payload"


def test_ambient_claim_cache_revalidates_after_separate_instance_claim(
    tmp_path,
    monkeypatch,
) -> None:
    shared_root = tmp_path / "shared"
    store_a = FileSystemCAS(shared_root, tenant_id="tenant-a")
    ref_a = store_a.put_bytes(
        b"tenant A cached claim",
        PutOptions(kind="test.cache_claim", media_type="text/plain"),
    )
    ambient = FileSystemCAS(shared_root).with_ambient_ownership_enforcement()

    ambient_candidate = ambient.put_bytes(
        b"unclaimed ambient candidate remains readable",
        PutOptions(kind="test.ambient_candidate", media_type="text/plain"),
    )
    assert ambient.get_bytes(ambient_candidate.artifact_id) == (
        b"unclaimed ambient candidate remains readable"
    )

    for _ in range(4):
        with pytest.raises(ArtifactOwnershipError):
            ambient.get_bytes(ref_a.artifact_id)

    cached_claims = ambient._ownership_index.claimed_artifact_ids()
    assert str(ref_a.artifact_id) in cached_claims

    store_b = FileSystemCAS(shared_root, tenant_id="tenant-b")
    payload_b = b"tenant B newly claimed bytes"
    expected_id_b = CoreArtifactID.from_sha256_hex(
        hashlib.sha256(payload_b).hexdigest()
    )
    assert str(expected_id_b) not in cached_claims
    cached_file_identities = ambient._ownership_index._claim_file_identities
    assert cached_file_identities is not None
    invalidation_removal_probe = os.environ.get(
        "POLISYOS_ARTIFACT_ID_REMOVE_CLAIM_IDENTITY_REFRESH_PROBE"
    )
    if invalidation_removal_probe not in {None, "1"}:
        raise ValueError(
            "POLISYOS_ARTIFACT_ID_REMOVE_CLAIM_IDENTITY_REFRESH_PROBE "
            "must be unset or 1"
        )
    if invalidation_removal_probe == "1":
        monkeypatch.setattr(
            ambient._ownership_index,
            "_current_file_identities",
            lambda: cached_file_identities,
        )

    ref_b = store_b.put_bytes(
        payload_b,
        PutOptions(kind="test.cache_claim", media_type="text/plain"),
    )
    assert ref_b.artifact_id == expected_id_b

    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(ref_b.artifact_id)

    assert store_b.get_bytes(ref_b) == payload_b


def test_tenant_scoped_cas_accepts_ir_dict_lineage_inputs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a")
    parent = store.put_json(
        {"parent": True},
        PutOptions(kind="test.parent", media_type="application/json"),
    )

    child = store.put_json(
        {"child": True},
        StorePutOptions(
            kind="test.child",
            media_type="application/json",
            inputs=[
                {
                    "artifact_id": str(parent.artifact_id),
                    "role": "parent",
                }
            ],
        ),
    )

    manifest = store.get_manifest(child.artifact_id)
    assert manifest.inputs[0].artifact_id == parent.artifact_id
    assert manifest.inputs[0].role == "parent"


def test_authority_write_helper_links_quality_artifact_manifest_metadata(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-1", cell_id="cell-a")
    source_ref = store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    result = write_authority_artifact(
        store,
        {"status": "pass", "checks": [{"name": "schema_drift", "status": "pass"}]},
        PutOptions(
            kind="runtime_quality.production_data_quality",
            media_type="application/json",
            schema=SchemaInfo(name="runtime_quality.production_data_quality", version="1.0"),
            producer=ProducerInfo(
                component="polisyos.runtime.quality.production_data",
                version="2026.05.15+hds-phase21",
            ),
            governance=ArtifactGovernanceInfo(classification="internal"),
            inputs=[
                {
                    "artifact_id": str(source_ref.artifact_id),
                    "role": "source_quality_input",
                }
            ],
        ),
        evidence_id="evidence-production-data-quality",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime",
        reader_contract="runtime_quality.production_data_quality.reader",
        reader_contract_version="1.0",
        tenant_id="tenant-1",
        cell_id="cell-a",
        run_id="run-hds-21",
        job_id="job-hds-21",
        trace_id="trace-hds-21",
        span_id="span-cas-write",
        parent_span_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        phase="quality_evidence",
        generated_at="2026-05-15T09:30:00+00:00",
        as_of_time="2026-05-15T09:30:00+00:00",
        same_input_closure={
            "closure_id": "closure-hds-21",
            "status": "closed",
            "run_id": "run-hds-21",
            "job_id": "job-hds-21",
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "evidence_input_refs": [str(source_ref.artifact_id)],
            "closure_sha256": "1" * 64,
        },
        input_refs=[str(source_ref.artifact_id)],
        effective_mode_ref="sha256:" + "2" * 64,
        degradation_ledger_ref="sha256:" + "3" * 64,
        validation_status="pass",
        blocking_status="non_blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
    )

    manifest = store.get_manifest(result.cas_ref.artifact_id)
    assert str(result.cas_ref.artifact_id).startswith("sha256:")
    assert result.payload_sha256 == manifest.integrity.sha256
    assert result.manifest_ref.startswith("cas-manifest://sha256:")
    assert str(result.authority_envelope_ref.artifact_id).startswith("sha256:")
    assert str(result.diagnostic_event_ref.artifact_id).startswith("sha256:")

    assert manifest.producer is not None
    assert str(manifest.producer.component) == "polisyos.runtime.quality.production_data"
    assert manifest.governance is not None
    assert manifest.governance.classification == "internal"
    assert manifest.inputs[0].artifact_id == source_ref.artifact_id
    assert manifest.inputs[0].role == "source_quality_input"
    assert manifest.artifact_schema == SchemaInfo(
        name="runtime_quality.production_data_quality",
        version="1.0",
    )
    assert manifest.tenant_context is not None
    assert manifest.tenant_context.tenant_id == "tenant-1"
    assert manifest.tenant_context.cell_id == "cell-a"
    assert manifest.same_input_closure is not None
    assert manifest.same_input_closure.closure_id == "closure-hds-21"
    assert manifest.same_input_closure.status == "closed"
    assert manifest.same_input_closure.closure_sha256 == "1" * 64
    assert manifest.authority is not None
    assert manifest.authority.payload_sha256 == result.payload_sha256
    assert manifest.authority.manifest_ref == result.manifest_ref
    assert manifest.authority.authority_envelope_ref == str(
        result.authority_envelope_ref.artifact_id
    )
    assert manifest.authority.diagnostic_event_ref == str(result.diagnostic_event_ref.artifact_id)
