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
    VerifiedCandidateExperimentOrigin,
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


def test_prejob_authority_reuses_one_origin_and_bound_source_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PA2 history and current gateway share one folded origin, with fresh row checks."""
    from polisyos.runtime.http.deployment_security import DeploymentHumanDecisionCustody
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
    )
    from polisyos.runtime.http.services.acquisition_authority_provider import (
        ProductionAcquisitionAuthorityProvider,
    )
    from polisyos.runtime.http.services.human_decision_contracts import HumanDecisionResolverPolicy
    from polisyos.runtime.http.services.human_decisions import HumanDecisionService
    from polisyos.runtime.quality.agent_action_authority import CANDIDATE_EXPERIMENT_ACTION_KIND
    from tests._helpers.runtime_http import _build_control_service
    from tests.unit.runtime.http.services.test_acquisition_action_service import (
        _candidate_experiment_action_fixture,
    )
    from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_job

    control = _build_control_service(tmp_path / "control")
    store = control._control_store
    base, request = _candidate_experiment_action_fixture(run_id="prejob-origin-run")
    job = _create_job(
        store, job_id=base.source_job_id, kind="natural_language_run", run_id=base.run_id
    )
    request = request.model_copy(
        update={
            "replay_pins": request.replay_pins.model_copy(
                update={"source_payload_ref": job.payload_ref}
            )
        }
    )
    phase_base = _requested_phase()
    phase = phase_base.model_copy(
        update={
            "tenant_id": base.tenant_id,
            "cell_id": base.cell_id,
            "run_id": base.run_id,
            "source_job_id": job.job_id,
            "source_payload_ref": job.payload_ref,
            "capability_manifest_ref": job.capability_manifest_ref,
            "request_content_hash": base.request_content_hash,
            "route_id": request.route_id,
            "policy_scope": base.policy_scope,
            "policy_ref": base.policy_ref,
            "job_id": "pending-action",
        }
    )
    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=base.tenant_id,
        cell_id=base.cell_id,
        run_id=base.run_id,
        source_job_id=job.job_id,
        source_payload_ref=job.payload_ref,
        capability_manifest_ref=job.capability_manifest_ref,
        request_content_hash=base.request_content_hash,
        route_id=request.route_id,
        policy_ref=base.policy_ref,
        policy_scope=base.policy_scope,
        generation_run=None,
        source_cycle=SimpleNamespace(voi_decision=phase.voi_decision),
        design_problem_basis=None,
        planner_report=None,
        planner_record=None,
    )
    phase = phase.model_copy(
        update={"job_id": AcquisitionActionService._candidate_experiment_job_id(origin, request)}
    )
    decision_ref = str(phase.authority_decision_ref.artifact_id)
    decision = SimpleNamespace(outcome="allowed", action_kind=CANDIDATE_EXPERIMENT_ACTION_KIND)
    history = SimpleNamespace(
        current_authority="not_revalidated",
        decision_ref=decision_ref,
        payload_sha256=decision_ref.removeprefix("sha256:"),
        decision=decision,
    )
    persisted = SimpleNamespace(
        decision=decision,
        write_result=SimpleNamespace(cas_ref=SimpleNamespace(artifact_id=decision_ref)),
    )
    order: list[str] = []
    original_get_job = store.get_job
    original_get_event = store.get_job_created_event_payload
    original_get_outbox = store.get_job_created_outbox_event

    def get_job(job_id: str):
        if job_id == phase.source_job_id:
            order.append("source_job")
        return original_get_job(job_id)

    def get_event(job_id: str):
        if job_id == phase.source_job_id:
            order.append("source_event")
        return original_get_event(job_id)

    def get_outbox(job_id: str):
        if job_id == phase.source_job_id:
            order.append("source_outbox")
        return original_get_outbox(job_id)

    monkeypatch.setattr(store, "get_job", get_job)
    monkeypatch.setattr(store, "get_job_created_event_payload", get_event)
    monkeypatch.setattr(store, "get_job_created_outbox_event", get_outbox)
    sink = control.acquisition_route_sink
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_resolve_candidate_experiment_source",
        lambda _self, **_: order.append("source_origin") or origin,
    )
    human = HumanDecisionService(
        authority_sink=control.human_decision_sink,
        custody=DeploymentHumanDecisionCustody(
            available=False, unavailability_code="DS9-DECISION-PRODUCER-MISSING"
        ),
        resolver_policy=HumanDecisionResolverPolicy(
            expected_consumer="polisyos.runtime.quality.agent_action_authority",
            expected_audience="polisyos-runtime",
            principal_audience="polisyos-runtime",
            expected_agent_operation=None,
            required_permission="runs.human_decisions.create",
        ),
        access_audit_path=tmp_path / "audit.jsonl",
    )
    provider = object.__new__(ProductionAcquisitionAuthorityProvider)
    gateway = SimpleNamespace(
        load_persisted_decision=lambda _ref: order.append("pa2_ds9") or persisted,
        verify_bound_authorization=lambda **_: order.append("verify_bound_authorization"),
    )
    provider_calls: list[dict[str, object]] = []
    provider.for_candidate_experiment_job = lambda **kwargs: (
        provider_calls.append(kwargs) or order.append("provider") or gateway
    )
    action_service = AcquisitionActionService(
        control_service=control,
        human_decision_service=human,
        authority_provider=provider,
        execution_port=SimpleNamespace(
            execute=lambda *_: None, reenter=lambda *_: None, resume_reentry=lambda *_: None
        ),
    )
    origin_calls: list[dict[str, object]] = []
    action_service._candidate_experiment_origin_for_request = lambda **kwargs: (
        origin_calls.append(kwargs) or order.append("fold_origin") or origin
    )
    history_calls: list[dict[str, object]] = []
    action_service.load_candidate_experiment_decision_history = lambda **kwargs: (
        history_calls.append(kwargs) or order.append("history") or history
    )
    revalidation_calls: list[dict[str, object]] = []
    action_service._revalidate_candidate_experiment_execute_origin = lambda **kwargs: (
        revalidation_calls.append(kwargs) or order.append("revalidate_current") or origin
    )
    action_service._candidate_experiment_action_tuple = lambda *_: (object(), object(), object())

    try:
        assert sink._verify_candidate_experiment_prejob_live_authority(phase, request) is origin
        assert order == [
            "source_job",
            "source_event",
            "source_outbox",
            "source_origin",
            "fold_origin",
            "history",
            "revalidate_current",
            "provider",
            "pa2_ds9",
            "verify_bound_authorization",
        ]
        assert origin_calls == [
            {
                "tenant_id": phase.tenant_id,
                "cell_id": phase.cell_id,
                "run_id": phase.run_id,
                "request": request,
                "require_current": True,
            }
        ]
        assert history_calls[0]["verified_origin"] is origin
        assert history_calls[0]["verified_source_inputs"] == (
            job,
            original_get_event(phase.source_job_id),
            original_get_outbox(phase.source_job_id),
        )
        assert revalidation_calls == [
            {"origin": origin, "request": request, "expected_head": origin.current_action_head}
        ]
        assert provider_calls[0]["origin"] is origin
        assert provider_calls[0]["request"] is request
        assert provider_calls[0]["decision_ref"] == decision_ref
    finally:
        store.close()


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


@pytest.mark.parametrize("head_current", [True, False], ids=["current", "changed"])
def test_pending_refresh_persists_new_authority_without_replacing_job_or_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, head_current: bool
) -> None:
    database, cas, sink, requested, job, initial = _pending_case(tmp_path, monkeypatch)
    original_bytes = cas.get_bytes(initial.receipt_ref)
    refreshed = _refreshed(requested, initial.receipt_ref)
    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=requested.tenant_id,
        cell_id=requested.cell_id,
        run_id=requested.run_id,
        source_job_id=requested.source_job_id,
        source_payload_ref=requested.source_payload_ref,
        capability_manifest_ref=requested.capability_manifest_ref,
        request_content_hash=requested.request_content_hash,
        route_id=requested.route_id,
        policy_scope=requested.policy_scope,
        policy_ref=requested.policy_ref,
        generation_run=None,
        source_cycle=SimpleNamespace(voi_decision=requested.voi_decision),
        design_problem_basis=None,
        planner_report=None,
        planner_record=None,
        current_action_head=initial if head_current else None,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_prejob_live_authority",
        lambda *_args: origin,
    )
    verify = AcquisitionRouteLoopAuthoritySink._verify_action_head_with_origin
    predecessor_origins = []

    def record_origin(owner, head, **kwargs):
        if owner is sink and head == initial:
            predecessor_origins.append(kwargs.get("verified_origin"))
        return verify(owner, head, **kwargs)

    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink, "_verify_action_head_with_origin", record_origin
    )

    try:
        if not head_current:
            with pytest.raises(
                ValueError, match="candidate_experiment_refresh_pending_head_changed"
            ):
                sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
            assert sink.get_head(requested) == initial
            assert database.get_job(job.job_id) == job
            assert predecessor_origins == []
            return
        head = sink.refresh_experiment_authorization(refreshed, object(), expected_job=job)
        assert predecessor_origins == [origin]
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
