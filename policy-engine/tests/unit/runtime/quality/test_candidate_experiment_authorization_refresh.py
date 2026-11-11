"""Persisted pending-authority transitions; PA2/DS9 issuance is a separate boundary.

These controls use real CAS, events, SQL, leases and fresh phase readers. They
replace only authority-owner verification, so they do not establish that a real
external approval was issued or remains current, and never invoke N5.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_job
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _hash,
    _persist_requested_phase,
    _phase_writer_case,
    _ref,
    _requested_phase,
)


def _refreshed(
    phase: AcquisitionCandidateExperimentPhaseReceipt,
    predecessor: str,
    *,
    digit: str = "1",
) -> AcquisitionCandidateExperimentPhaseReceipt:
    return AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        phase.model_copy(
            update={
                "schema_version": "AcquisitionCandidateExperimentPhaseReceipt@2.0",
                "receipt_id": f"{phase.job_id}.authorization-refreshed.{digit}",
                "receipt_phase": "authorization_refreshed",
                "coarse_phase": "requested",
                "recovery_state": "none",
                "predecessor_receipt_ref": predecessor,
                "authority_decision_ref": _ref(
                    "runtime_quality.agent_action_authority_decision", digit
                ),
                "generated_at": phase.generated_at + timedelta(seconds=1),
            }
        ).model_dump(mode="python")
    )


def _pending_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database, cas, sink, requested = _phase_writer_case(tmp_path, monkeypatch)
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_prejob_live_authority",
        lambda *_args: None,
    )
    job = _create_job(
        database, job_id=requested.job_id, kind="acquisition", run_id=requested.run_id
    )
    head = _persist_requested_phase(sink, requested)
    return database, cas, sink, requested, job, head


def test_refresh_is_versioned_and_preserves_original_v1_wire() -> None:
    requested = _requested_phase()
    original_wire = requested.model_dump(mode="json")
    restored = AcquisitionCandidateExperimentPhaseReceipt.model_validate(original_wire)
    assert restored.model_dump(mode="json") == original_wire
    assert original_wire["schema_version"] == "AcquisitionCandidateExperimentPhaseReceipt@1.0"
    refreshed = _refreshed(requested, _hash("a"))
    assert refreshed.schema_version == "AcquisitionCandidateExperimentPhaseReceipt@2.0"
    with pytest.raises(ValueError, match="refresh_requires_v2"):
        AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            {**refreshed.model_dump(mode="python"), "schema_version": requested.schema_version}
        )
    with pytest.raises(ValueError, match="original_requested_root"):
        AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            {**original_wire, "schema_version": refreshed.schema_version}
        )


def test_pending_refresh_persists_new_authority_without_replacing_job_or_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    original_bytes = cas.get_bytes(initial.receipt_ref)
    refreshed = _refreshed(requested, initial.receipt_ref)
    try:
        head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        assert head.head_generation == 2
        assert head.job_id == job.job_id
        assert head.action_generation == initial.action_generation
        assert head.receipt_phase == "authorization_refreshed"
        assert head.predecessor_receipt_ref == initial.receipt_ref
        assert database.get_job(job.job_id) == job
        assert cas.get_bytes(initial.receipt_ref) == original_bytes
        assert sink.get_head(requested) == head

        reader = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
        fresh_cas = FileSystemCAS(tmp_path / "cas")
        fresh_sink = AcquisitionRouteLoopAuthoritySink(
            artifact_store=fresh_cas,
            event_log=RuntimeDiagnosticEventLog(store=reader, artifact_store=fresh_cas),
            control_store=reader,
        )
        try:
            verified = fresh_sink.verify_action_head(head)
            assert [row.receipt.receipt_phase for row in verified.phase_chain] == [
                "requested",
                "authorization_refreshed",
            ]
            assert (
                verified.phase_chain[0].receipt.authority_decision_ref
                == requested.authority_decision_ref
            )
            assert (
                verified.latest_receipt.authority_decision_ref == refreshed.authority_decision_ref
            )
            selected = ArtifactRef(
                artifact_id=head.receipt_ref,
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
                manifest_profile_sha256=head.receipt_manifest_profile_sha256,
            )
            actual = fresh_cas.get_bytes

            def missing(ref):
                if ref == selected:
                    raise OSError("selected refresh bytes unavailable")
                return actual(ref)

            monkeypatch.setattr(fresh_cas, "get_bytes", missing)
            with pytest.raises(OSError, match="selected refresh bytes unavailable"):
                fresh_sink.verify_action_head(head)
        finally:
            reader.close()
    finally:
        database.close()


def test_authority_change_cannot_be_hidden_in_ordinary_execution_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _cas, sink, requested, _job, initial = _pending_case(tmp_path, monkeypatch)
    forged = requested.model_copy(
        update={
            "receipt_id": "unrenewed-executing",
            "coarse_phase": "executing",
            "receipt_phase": "executing",
            "predecessor_receipt_ref": initial.receipt_ref,
            "authority_decision_ref": _ref("runtime_quality.agent_action_authority_decision", "1"),
        }
    )
    try:
        with pytest.raises(ValueError, match="predecessor_identity_mismatch"):
            sink._persist_receipt(
                forged,
                artifact_kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                schema_name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
                event_type="polisyos.runtime.acquisition.candidate_experiment_phase.v1",
                event_suffix="forged-executing",
                receipt_type=AcquisitionCandidateExperimentPhaseReceipt,
                receipt_label="candidate_experiment_phase",
            )
        assert sink.get_head(requested) == initial
    finally:
        database.close()


def test_refresh_retry_and_second_permission_preserve_the_exact_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    first = _refreshed(requested, initial.receipt_ref)
    try:
        first_head = sink.refresh_experiment_authorization(first, object(), expected_job=job)
        retry = first.model_copy(
            update={"generated_at": first.generated_at + timedelta(seconds=10)}
        )
        assert (
            sink.refresh_experiment_authorization(retry, object(), expected_job=job) == first_head
        )
        second = _refreshed(first, first_head.receipt_ref, digit="2")
        second_head = sink.refresh_experiment_authorization(second, object(), expected_job=job)
        assert second_head.head_generation == 3
        assert database.get_job(job.job_id) == job
        chain = sink.verify_action_head(second_head).phase_chain
        assert [row.receipt.authority_decision_ref for row in chain] == [
            requested.authority_decision_ref,
            first.authority_decision_ref,
            second.authority_decision_ref,
        ]
    finally:
        database.close()


def test_refreshed_permission_flows_into_leased_execution_without_new_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    refreshed = _refreshed(requested, initial.receipt_ref)
    try:
        fresh_head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        leased = database.lease_next_job(worker_id="renewal-worker", lease_seconds=60)
        assert leased is not None and leased.job_id == job.job_id
        executing = refreshed.model_copy(
            update={
                "receipt_id": job.job_id + ".executing",
                "coarse_phase": "executing",
                "receipt_phase": "executing",
                "predecessor_receipt_ref": fresh_head.receipt_ref,
            }
        )
        with database.job_execution_fence(
            job_id=job.job_id, worker_id="renewal-worker", attempt=leased.attempt
        ):
            execution_head = sink.persist_experiment_phase(executing)
        verified = sink.verify_action_head(execution_head)
        assert verified.executing_phase.authority_decision_ref == refreshed.authority_decision_ref
        assert (
            verified.phase_chain[0].receipt.authority_decision_ref
            == requested.authority_decision_ref
        )
        assert database.get_job(job.job_id).payload_ref == job.payload_ref
        refused = _refreshed(refreshed, execution_head.receipt_ref, digit="2")
        with pytest.raises(ValueError, match="pending_job_not_established"):
            sink.refresh_experiment_authorization(refused, object(), expected_job=leased)
    finally:
        database.close()


def test_same_byte_wrong_version_manifest_does_not_reinterpret_v2_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    refreshed = _refreshed(requested, initial.receipt_ref)
    try:
        head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        wrong = cas.put_json(
            refreshed.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
                    version="1.0",
                ),
                producer=ProducerInfo(
                    component="polisyos.runtime.acquisition_route_loop",
                    version="2026.08.28+ds15-c02",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert str(wrong.artifact_id) == head.receipt_ref
        assert wrong.manifest_profile_sha256 != head.receipt_manifest_profile_sha256
        with pytest.raises(ValueError, match="receipt_schema_or_scope_invalid"):
            sink._read_verified_action_phase(head.receipt_ref, selected_ref=wrong)
        assert sink.verify_action_head(head).latest_receipt == refreshed
    finally:
        database.close()


def test_version_downgrade_refuses_before_advancing_the_selected_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    refreshed = _refreshed(requested, initial.receipt_ref)
    try:
        head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        downgraded = refreshed.model_copy(
            update={
                "schema_version": "AcquisitionCandidateExperimentPhaseReceipt@1.0",
                "receipt_id": job.job_id + ".downgraded-executing",
                "receipt_phase": "executing",
                "coarse_phase": "executing",
                "predecessor_receipt_ref": head.receipt_ref,
            }
        )
        with pytest.raises(ValueError, match="predecessor_identity_mismatch"):
            sink._persist_receipt(
                downgraded,
                artifact_kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                schema_name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
                event_type="polisyos.runtime.acquisition.candidate_experiment_phase.v1",
                event_suffix="downgraded-executing",
                receipt_type=AcquisitionCandidateExperimentPhaseReceipt,
                receipt_label="candidate_experiment_phase",
            )
        assert sink.get_head(requested) == head
        assert sink.verify_action_head(head).latest_receipt == refreshed
    finally:
        database.close()


def test_refresh_retry_uses_sql_selected_profile_when_cas_default_is_a_wrong_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    refreshed = _refreshed(requested, initial.receipt_ref)
    try:
        default = cas.put_json(
            refreshed.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
                    version="1.0",
                ),
                producer=ProducerInfo(component="test.foreign-default", version="1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        assert str(default.artifact_id) == head.receipt_ref
        assert cas.get_manifest(head.receipt_ref).artifact_schema.version == "1.0"
        assert head.receipt_manifest_profile_sha256 != default.manifest_profile_sha256
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _selected_candidate_experiment_phase_ref,
        )

        selected = _selected_candidate_experiment_phase_ref(
            SimpleNamespace(artifact_store=cas, control_store=database), refreshed, head.receipt_ref
        )
        assert selected.manifest_profile_sha256 == head.receipt_manifest_profile_sha256
        retry = refreshed.model_copy(
            update={"generated_at": refreshed.generated_at + timedelta(seconds=5)}
        )
        assert sink.refresh_experiment_authorization(retry, object(), expected_job=job) == head
        assert sink.verify_action_head(head).latest_receipt == refreshed
    finally:
        database.close()


def test_v2_refresh_cannot_downgrade_to_legacy_profileless_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    refreshed = _refreshed(requested, initial.receipt_ref)
    try:
        head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        database._execute(
            "UPDATE runtime_acquisition_action_heads SET receipt_manifest_profile_sha256 = NULL "
            "WHERE receipt_ref = ?",
            (head.receipt_ref,),
        )
        changed = sink.get_head(refreshed)
        assert changed is not None and changed.receipt_manifest_profile_sha256 is None
        with pytest.raises(ValueError, match="v2_phase_profile_required"):
            sink.verify_action_head(changed)
    finally:
        database.close()
