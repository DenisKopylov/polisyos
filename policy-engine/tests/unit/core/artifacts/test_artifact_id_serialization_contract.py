from __future__ import annotations

import threading
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
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
    assert store_b.has(ref_a.artifact_id) is True
    assert store_b.get_bytes(ref_a.artifact_id) == store_a.get_bytes(ref_a.artifact_id)


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
    with pytest.raises(ArtifactOwnershipError):
        store.get_paths(view_ref)
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
    index_path = shared_root / "artifacts" / "ownership" / "index.json"
    signature_path = index_path.with_name("index.signature.json")
    original_loader = ownership_module._load_json_file
    parsed_paths: list[Path] = []

    def counted_load(path: Path):
        parsed_paths.append(path)
        return original_loader(path)

    monkeypatch.setattr(ownership_module, "_load_json_file", counted_load)

    for _ in range(4):
        with pytest.raises(ArtifactOwnershipError):
            ambient.get_bytes(ref_a.artifact_id)

    assert Counter(parsed_paths) == Counter({index_path: 1, signature_path: 1})

    store_b = FileSystemCAS(shared_root, tenant_id="tenant-b")
    ref_b = store_b.put_bytes(
        b"tenant B newly claimed bytes",
        PutOptions(kind="test.cache_claim", media_type="text/plain"),
    )
    parsed_paths.clear()

    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(ref_b.artifact_id)

    assert Counter(parsed_paths) == Counter({index_path: 1, signature_path: 1})

    index_bytes = index_path.read_bytes()
    signature_bytes = signature_path.read_bytes()
    index_replacement = index_path.with_name("index.replacement.json")
    index_replacement.write_bytes(index_bytes)
    index_replacement.replace(index_path)
    parsed_paths.clear()

    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(ref_b.artifact_id)

    assert Counter(parsed_paths) == Counter({index_path: 1, signature_path: 1})

    signature_replacement = signature_path.with_name("signature.replacement.json")
    signature_replacement.write_bytes(signature_bytes)
    signature_replacement.replace(signature_path)
    parsed_paths.clear()

    with pytest.raises(ArtifactOwnershipError):
        ambient.get_bytes(ref_b.artifact_id)

    assert Counter(parsed_paths) == Counter({index_path: 1, signature_path: 1})


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
