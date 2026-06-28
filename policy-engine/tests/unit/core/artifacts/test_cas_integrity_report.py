from __future__ import annotations

from polisyos.core.artifacts import (
    ArtifactID,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    build_cas_integrity_report,
)
from polisyos.core.artifacts._integrity_ops import verify_filesystem_artifact
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.artifacts import write_authority_artifact

FIXED_TIME = "2026-06-16T12:34:56Z"


def test_cas_integrity_report_proves_authority_dedup_tamper_and_gc(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    payload = {"fixture": "duplicate-authority-payload", "value": 7}

    first_ref = _write_authority_payload(store, payload, kind="surface.integrity_payload")
    second_ref = _write_authority_payload(store, payload, kind="surface.integrity_payload")

    artifact_id = ArtifactID.model_validate(first_ref)
    blob_path, manifest_path = store.get_paths(artifact_id)
    original = blob_path.read_bytes()
    blob_path.write_bytes(original + b"\nmutation")
    tamper = verify_filesystem_artifact(
        artifact_id,
        blob_path=blob_path,
        manifest_path=manifest_path,
    )
    blob_path.write_bytes(original)

    report = build_cas_integrity_report(
        store,
        artifact_id,
        referrers=["workspace://surface-safety"],
        report_index_refs=["report-index://surface-safety"],
        lineage_refs=[f"lineage://{artifact_id}"],
        retain_roots={
            "report_index": {"artifact_ref": str(artifact_id)},
            "lineage": {"nodes": [{"artifact_id": str(artifact_id)}]},
            "workspace": {"artifact_refs": [str(artifact_id)]},
        },
        tamper_probe_result=f"rejected:{tamper.error}",
        mutation_probe_result=f"duplicate_write_same_digest:{first_ref == second_ref}",
    )
    unreferenced_report = build_cas_integrity_report(
        store,
        artifact_id,
        tamper_probe_result=f"rejected:{tamper.error}",
        mutation_probe_result=f"duplicate_write_same_digest:{first_ref == second_ref}",
    )

    assert first_ref == second_ref
    assert tamper.ok is False
    assert report.payload_digest == artifact_id.hex
    assert report.blob_uri == f"cas-blob://{artifact_id}"
    assert report.authority_manifest_ref is not None
    assert report.mutation_probe_result == "duplicate_write_same_digest:True"
    assert report.gc_dry_run_result == "retain"
    assert unreferenced_report.gc_dry_run_result == "blocked"


def _write_authority_payload(
    store: FileSystemCAS,
    payload: dict[str, object],
    *,
    kind: str,
) -> str:
    result = write_authority_artifact(
        store,
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
            producer=ProducerInfo(component="polisyos.tests.cas_integrity", version="1.0"),
        ),
        evidence_id=f"{kind}-fixture",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner="team-runtime-quality",
        reader_contract=kind,
        reader_contract_version="1.0",
        tenant_id="policyos-system",
        cell_id=None,
        run_id="run-cas-integrity-test",
        job_id="job-cas-integrity-test",
        trace_id="trace-cas-integrity-test",
        span_id=f"span-{kind}",
        parent_span_id=None,
        requested_execution_profile="test",
        effective_execution_profile="test",
        phase="GY-F2",
        generated_at=FIXED_TIME,
        as_of_time=FIXED_TIME,
        same_input_closure={
            "closure_id": "cas-integrity-test",
            "status": "closed",
            "run_id": "run-cas-integrity-test",
            "job_id": "job-cas-integrity-test",
            "tenant_id": "policyos-system",
            "cell_id": None,
            "evidence_input_refs": (),
        },
        input_refs=[],
        effective_mode_ref="test",
        validation_status="pass",
        blocking_status="non_blocking",
        governance={
            "classification": "internal",
            "authority_boundary": "test",
            "pii": "secret_pii_scanned",
            "retention_policy": "test",
            "review_status": "runtime_generated",
            "override_policy": "no_override",
            "approval_policy": "not_publication_authority",
        },
        redaction_policy_ref="polisyos.core.llm.sanitization.v1",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return str(result.cas_ref.artifact_id)
