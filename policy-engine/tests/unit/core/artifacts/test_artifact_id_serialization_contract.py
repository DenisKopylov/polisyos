from __future__ import annotations

import warnings

import pytest

from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
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
