from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
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

    other_source = artifact_store.put_json(
        {"source": "other-runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    other_source_ref = str(other_source.artifact_id)
    base_context = _runtime_context(str(source_ref.artifact_id))
    mutations: tuple[tuple[PutOptions, dict[str, object]], ...] = (
        (_opts(other_source_ref), {**base_context, "input_refs": [other_source_ref]}),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "tenant_id": "tenant-other"},
        ),
        (_opts(str(source_ref.artifact_id)), {**base_context, "cell_id": "cell-b"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "run_id": "run-other"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "job_id": "job-other"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "trace_id": "trace-other"}),
        (_opts(str(source_ref.artifact_id)), {**base_context, "span_id": "span-other"}),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "parent_span_id": "parent-other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "requested_execution_profile": "diagnostic"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "effective_execution_profile": "diagnostic"},
        ),
        (_opts(str(source_ref.artifact_id)), {**base_context, "phase": "other-phase"}),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "generated_at": "2026-05-15T09:31:00+00:00"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "as_of_time": "2026-05-15T09:31:00+00:00"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {
                **base_context,
                "same_input_closure": {
                    **base_context["same_input_closure"],  # type: ignore[dict-item]
                    "closure_id": "closure-other",
                },
            },
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "effective_mode_ref": "sha256:" + "4" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "validation_status": "blocked"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "blocking_status": "blocking"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {
                **base_context,
                "governance": base_context["governance"].model_copy(  # type: ignore[union-attr]
                    update={"review_status": "runtime_rejected"}
                ),
            },
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "degradation_ledger_ref": "sha256:" + "5" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "schema_compatibility_ref": "sha256:" + "6" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "semantic_binding_ref": "sha256:" + "7" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "redaction_policy_ref": "sha256:" + "8" * 64},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_id": "evt-other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_source": "runtime.other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_type": "runtime.other.event.v1"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "event_subject": "runtime/other"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "state_before": "queued"},
        ),
        (
            _opts(str(source_ref.artifact_id)),
            {**base_context, "state_after": "rejected"},
        ),
    )
    for mutated_opts, mutated_context in mutations:
        with pytest.raises(ValueError, match="existing authority identity mismatch"):
            write_runtime_authority_artifact(
                artifact_store,
                event_log,
                payload,
                mutated_opts,
                **mutated_context,
            )


def test_runtime_authority_writer_binds_the_exact_generated_attestation(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    arbitrary_ref = artifact_store.put_json(
        {"not": "a-cas-writer-attestation"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))

    with pytest.raises(ValueError, match="attestation identity mismatch"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **{
                **context,
                "attestation_ref": str(arbitrary_ref.artifact_id),
            },
        )

    produced = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )
    reused = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        _opts(str(source_ref.artifact_id)),
        **context,
    )
    envelope = from_canonical_bytes(
        artifact_store.get_bytes(produced.authority_envelope_ref.artifact_id)
    )
    attestation_id = ArtifactID.model_validate(envelope["attestation_ref"])
    attestation_manifest = artifact_store.get_manifest(attestation_id)
    assert reused == produced
    assert attestation_manifest.kind == "runtime_quality.trust_boundary_attestation"


def test_runtime_authority_writer_propagates_backend_programmer_faults(
    tmp_path,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )

    class FaultingStore:
        def has(self, artifact_id: ArtifactID) -> bool:
            del artifact_id
            raise RuntimeError("backend programmer fault")

        def __getattr__(self, name: str) -> object:
            return getattr(artifact_store, name)

    with pytest.raises(RuntimeError, match="backend programmer fault"):
        write_runtime_authority_artifact(
            FaultingStore(),
            event_log,
            {"status": "pass", "claims": [{"claim_id": "claim-1"}]},
            _opts(str(source_ref.artifact_id)),
            **_runtime_context(str(source_ref.artifact_id)),
        )


def test_runtime_authority_writer_rejects_relabelled_same_bytes(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    payload = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}
    context = _runtime_context(str(source_ref.artifact_id))
    wrong_opts = replace(
        _opts(str(source_ref.artifact_id)),
        kind="runtime.wrong-kind",
        schema=SchemaInfo(name="runtime.WrongSchema", version="1.0"),
    )
    write_runtime_authority_artifact(
        artifact_store,
        event_log,
        payload,
        wrong_opts,
        **context,
    )

    with pytest.raises(ValueError, match="existing authority identity mismatch"):
        write_runtime_authority_artifact(
            artifact_store,
            event_log,
            payload,
            _opts(str(source_ref.artifact_id)),
            **context,
        )


def test_exact_event_identity_reconciliation_is_page_position_independent(tmp_path) -> None:
    artifact_store, event_log = _stores(tmp_path)
    source_ref = artifact_store.put_json(
        {"source": "runtime-input"},
        PutOptions(kind="runtime.input", media_type="application/json"),
    )
    result = write_runtime_authority_artifact(
        artifact_store,
        event_log,
        {"status": "pass", "claims": [{"claim_id": "claim-exact-event"}]},
        _opts(str(source_ref.artifact_id)),
        **_runtime_context(str(source_ref.artifact_id)),
    )
    target = event_log.list_events(run_id="run-wave-2", job_id="job-wave-2")[0]

    class PageCappedEventLog:
        def __init__(self, exact_records: list[object] | None = None) -> None:
            self._exact_records = [target] if exact_records is None else exact_records
            self.queries: list[tuple[str | None, int]] = []

        def list_events(
            self,
            *,
            event_id: str | None = None,
            run_id: str | None = None,
            job_id: str | None = None,
            limit: int = 500,
        ) -> list[object]:
            del run_id, job_id
            self.queries.append((event_id, limit))
            if event_id == target.event.event_id:
                return self._exact_records
            return []

    report = reconcile_authority_ref(
        artifact_store=artifact_store,
        event_log=PageCappedEventLog(),
        cas_ref=str(result.cas_ref.artifact_id),
        expected_run_id="run-wave-2",
        expected_job_id="job-wave-2",
    )

    assert report.status == "pass"
    assert report.durable_event_id == target.event.event_id

    exact_log = PageCappedEventLog()
    event_report = reconcile_authority_event(
        artifact_store=artifact_store,
        event_log=exact_log,
        event_id=target.event.event_id,
    )
    assert event_report.status == "pass"
    assert exact_log.queries == [
        (target.event.event_id, 2),
        (target.event.event_id, 2),
    ]

    with pytest.raises(AuthorityReconciliationError) as event_collision:
        reconcile_authority_event(
            artifact_store=artifact_store,
            event_log=PageCappedEventLog([target, target]),
            event_id=target.event.event_id,
        )
    assert event_collision.value.code == "authority_event_collision"

    duplicate_log = PageCappedEventLog([target, target])
    with pytest.raises(AuthorityReconciliationError) as duplicate_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=duplicate_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert duplicate_error.value.code == "authority_event_collision"

    changed = replace(
        target,
        event=target.event.model_copy(update={"trace_id": "trace-substituted"}),
    )
    changed_log = PageCappedEventLog([changed])
    with pytest.raises(AuthorityReconciliationError) as changed_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=changed_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert changed_error.value.code == "authority_payload_mismatch"

    wrong_row = replace(target, payload_ref="sha256:" + "f" * 64)
    wrong_row_log = PageCappedEventLog([wrong_row])
    with pytest.raises(AuthorityReconciliationError) as row_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=wrong_row_log,
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert row_error.value.code == "authority_payload_mismatch"

    changed_artifact_ref = "sha256:" + "e" * 64
    changed_artifacts = replace(
        target,
        event=target.event.model_copy(
            update={"artifact_refs": (changed_artifact_ref,)}
        ),
    )
    linked_event_bytes = to_canonical_bytes(
        changed_artifacts.event.model_dump(mode="json")
    )
    authority_manifest = artifact_store.get_manifest(result.cas_ref.artifact_id)
    linked_id = ArtifactID.model_validate(
        authority_manifest.authority.diagnostic_event_ref
    )

    class ChangedArtifactRefsStore:
        def has(self, artifact_id):
            return artifact_store.has(artifact_id)

        def verify(self, artifact_id):
            return artifact_store.verify(artifact_id)

        def get_bytes(self, artifact_id):
            if artifact_id == linked_id:
                return linked_event_bytes
            return artifact_store.get_bytes(artifact_id)

        def get_manifest(self, artifact_id):
            return artifact_store.get_manifest(artifact_id)

    with pytest.raises(AuthorityReconciliationError) as artifact_refs_error:
        reconcile_authority_ref(
            artifact_store=ChangedArtifactRefsStore(),
            event_log=PageCappedEventLog([changed_artifacts]),
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert artifact_refs_error.value.code == "authority_payload_mismatch"

    with pytest.raises(AuthorityReconciliationError) as missing_error:
        reconcile_authority_ref(
            artifact_store=artifact_store,
            event_log=PageCappedEventLog([]),
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert missing_error.value.code == "authority_orphan_cas"

    class WrongKindStore:
        def has(self, artifact_id):
            return artifact_store.has(artifact_id)

        def verify(self, artifact_id):
            return artifact_store.verify(artifact_id)

        def get_bytes(self, artifact_id):
            return artifact_store.get_bytes(artifact_id)

        def get_manifest(self, artifact_id):
            manifest = artifact_store.get_manifest(artifact_id)
            if artifact_id == linked_id:
                return manifest.model_copy(update={"kind": "runtime.wrong-kind"})
            return manifest

    with pytest.raises(AuthorityReconciliationError) as kind_error:
        reconcile_authority_ref(
            artifact_store=WrongKindStore(),
            event_log=PageCappedEventLog(),
            cas_ref=str(result.cas_ref.artifact_id),
        )
    assert kind_error.value.code == "authority_payload_mismatch"


def test_authority_ref_normalization_catches_only_expected_parse_failures(
    tmp_path,
    monkeypatch,
) -> None:
    artifact_store, event_log = _stores(tmp_path)
    for invalid_ref in ("sha256:not-a-digest", "cas://sha256/not-a-digest"):
        with pytest.raises(AuthorityReconciliationError) as invalid_error:
            reconcile_authority_ref(
                artifact_store=artifact_store,
                event_log=event_log,
                cas_ref=invalid_ref,
            )
        assert invalid_error.value.code == "authority_ref_not_cas"

    def programmer_fault(cls, value):
        del cls, value
        raise RuntimeError("artifact id programmer fault")

    monkeypatch.setattr(ArtifactID, "model_validate", classmethod(programmer_fault))
    for parseable_form in ("sha256:" + "1" * 64, "cas://sha256/" + "1" * 64):
        with pytest.raises(RuntimeError, match="artifact id programmer fault"):
            reconcile_authority_ref(
                artifact_store=artifact_store,
                event_log=event_log,
                cas_ref=parseable_form,
            )


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
