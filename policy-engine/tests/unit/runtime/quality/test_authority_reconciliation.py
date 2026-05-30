from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.http.services.control.artifacts import (
    write_authority_artifact,
    write_runtime_authority_artifact,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.attestation import deserialize_attestation_record
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
    reconcile_authority_event,
    reconcile_authority_ref,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


def _runtime_context(source_ref: str) -> dict[str, object]:
    return {
        "evidence_id": "evidence-policy-grounding",
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "owner": "team-runtime",
        "reader_contract": "runtime_quality.policy_grounding.reader",
        "reader_contract_version": "1.0",
        "tenant_id": "tenant-1",
        "cell_id": "cell-a",
        "run_id": "run-wave-2",
        "job_id": "job-wave-2",
        "trace_id": "trace-wave-2",
        "span_id": "span-policy-grounding",
        "parent_span_id": "span-parent",
        "requested_execution_profile": "production",
        "effective_execution_profile": "production",
        "phase": "policy_grounding",
        "generated_at": "2026-05-15T09:30:00+00:00",
        "as_of_time": "2026-05-15T09:30:00+00:00",
        "same_input_closure": {
            "closure_id": "closure-wave-2",
            "status": "closed",
            "run_id": "run-wave-2",
            "job_id": "job-wave-2",
            "tenant_id": "tenant-1",
            "cell_id": "cell-a",
            "evidence_input_refs": [source_ref],
            "closure_sha256": "1" * 64,
        },
        "input_refs": [source_ref],
        "effective_mode_ref": "sha256:" + "2" * 64,
        "degradation_ledger_ref": "sha256:" + "3" * 64,
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="runtime_owner_required",
        ),
    }


def _opts(source_ref: str) -> PutOptions:
    return PutOptions(
        kind="scientist.policy_grounding_matrix",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.scientist.PolicyGroundingMatrix", version="1.0"),
        producer=ProducerInfo(
            component="polisyos.runtime.quality.policy_grounding_matrix",
            version="2026.05.15+hds-wave2",
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[
            InputRef.model_validate({"artifact_id": source_ref, "role": "policy_grounding_input"})
        ],
    )


def _stores(tmp_path) -> tuple[FileSystemCAS, RuntimeDiagnosticEventLog]:
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )
    control_store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    event_log = RuntimeDiagnosticEventLog(
        store=control_store,
        artifact_store=artifact_store,
    )
    return artifact_store, event_log


def test_runtime_authority_writer_appends_durable_event_and_reconciles(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )

    records = event_log.list_events(run_id="run-wave-2", job_id="job-wave-2")
    assert len(records) == 1
    assert records[0].event.payload_ref == str(result.cas_ref.artifact_id)
    assert str(result.cas_ref.artifact_id).startswith("sha256:")

    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=event_log,
        cas_ref=str(result.cas_ref.artifact_id),
        expected_tenant_id="tenant-1",
        expected_cell_id="cell-a",
        expected_run_id="run-wave-2",
        expected_job_id="job-wave-2",
    )

    assert report.status == "pass"
    assert report.cas_ref == str(result.cas_ref.artifact_id)
    assert report.durable_event_id == records[0].event.event_id


def test_runtime_authority_writer_links_cas_writer_attestation(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )

    envelope = from_canonical_bytes(
        artifact_store.get_bytes(result.authority_envelope_ref.artifact_id)
    )
    attestation_ref = envelope["attestation_ref"]
    attestation = deserialize_attestation_record(
        from_canonical_bytes(artifact_store.get_bytes(attestation_ref))
    )

    assert attestation.trust_boundary_id == "cas_writer"
    assert attestation.producer_identity.owner == "team-runtime"
    assert attestation.environment_identity.tenant_id == "tenant-1"
    assert attestation.consumer_verification == "verified"
    assert attestation.tamper_check_status == "pass"


def test_runtime_authority_writer_rejects_existing_cas_without_durable_event(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    write_authority_artifact(
        artifact_store,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )

    with pytest.raises(AuthorityReconciliationError) as error:
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **context,
        )

    assert error.value.code == "authority_orphan_cas"
    assert event_log.list_events(run_id="run-wave-2", job_id="job-wave-2") == []


def test_runtime_authority_writer_reuses_existing_cas_only_after_reconciliation(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    first = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )

    second = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )

    assert second == first
    records = event_log.list_events(run_id="run-wave-2", job_id="job-wave-2")
    assert len(records) == 1


def test_cas_artifact_without_durable_event_fails_serious_reconciliation(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    result = write_authority_artifact(
        artifact_store,
        {"status": "pass"},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )

    with pytest.raises(AuthorityReconciliationError) as error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=event_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )

    assert error.value.code == "authority_orphan_cas"


def test_durable_event_without_cas_artifact_fails_serious_reconciliation(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    missing_ref = "sha256:" + "9" * 64
    event_log.append(
        DiagnosticEvent(
            event_id="evt-missing-cas",
            event_source="polisyos.runtime.http.nl_pipeline",
            event_type="polisyos.runtime.diagnostic.cas_write.v1",
            event_time=datetime(2026, 5, 15, 9, 30, tzinfo=UTC),
            event_subject="run/run-wave-2/job/job-wave-2/phase/policy_grounding",
            schema_name="polisyos.runtime.quality.diagnostic_event",
            schema_version="1.0",
            trace_id="trace-wave-2",
            span_id="span-policy-grounding",
            parent_span_id="span-parent",
            run_id="run-wave-2",
            job_id="job-wave-2",
            tenant_id="tenant-1",
            cell_id="cell-a",
            producer_component="polisyos.runtime.quality.policy_grounding_matrix",
            producer_version="2026.05.15+hds-wave2",
            execution_profile="production",
            phase="policy_grounding",
            state_before=None,
            state_after="persisted",
            payload_ref=missing_ref,
            artifact_refs=(missing_ref,),
            input_refs=(),
            blocking_status="non_blocking",
            redaction_policy_ref=None,
            duplicate_of=None,
            dedupe_key="job-wave-2:policy_grounding:evidence-policy-grounding:cas_write",
            sampling_decision="always_record",
            sampling_rate=1.0,
        )
    )

    with pytest.raises(AuthorityReconciliationError) as error:
        reconcile_authority_event(
            artifact_store=artifact_store,
            event_log=event_log,
            event_id="evt-missing-cas",
        )

    assert error.value.code == "authority_cas_missing"
