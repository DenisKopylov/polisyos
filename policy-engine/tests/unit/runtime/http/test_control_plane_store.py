from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import cast

import polisyos.runtime.http.services.control_worker as control_worker_module
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.runtime.http.services.control_plane_store import ControlJobRecord, ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker
from tests._helpers.policy_design_case_projection import policy_design_case, sha


def _make_store(tmp_path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def test_control_plane_store_tracks_worker_leases_and_outbox(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.heartbeat_worker(
        worker_id="worker-a",
        state="idle",
        lease_seconds=30,
        backend="external",
        metadata={"zone": "lab"},
    )

    workers = store.list_worker_leases()
    assert len(workers) == 1
    assert workers[0].worker_id == "worker-a"
    assert workers[0].state == "idle"
    assert workers[0].metadata["zone"] == "lab"

    record = store.create_job(
        job_id="job_fixture_001",
        kind="workflow_run",
        run_id="R_fixture_001",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    leased = store.lease_next_job(worker_id="worker-a", lease_seconds=30)
    assert leased is not None
    assert leased.job_id == record.job_id

    store.heartbeat_worker(
        worker_id="worker-a",
        state="running",
        lease_seconds=30,
        backend="external",
        active_job_id=record.job_id,
        metadata={"job_kind": record.kind},
    )
    store.update_progress_state(
        job_id=record.job_id,
        state="running",
        progress={"phase": "dispatch"},
    )
    store.complete_job(
        job_id=record.job_id,
        progress={"phase": "completed"},
    )

    first = store.enqueue_outbox_event(
        topic="control.decision_validity.event_published",
        event_key="decision_evt_fixture",
        payload={"trigger_type": "law_change"},
    )
    second = store.enqueue_outbox_event(
        topic="control.decision_validity.event_published",
        event_key="decision_evt_fixture",
        payload={"trigger_type": "law_change"},
    )
    assert first.event_id == second.event_id

    topics = {item.topic for item in store.list_outbox_events(state=None, limit=16)}
    assert "control.job.created" in topics
    assert "control.job.running" in topics
    assert "control.job.progress" in topics
    assert "control.job.completed" in topics
    assert "control.decision_validity.event_published" in topics

    store.mark_outbox_published(event_id=first.event_id)
    published = store.get_outbox_event(first.event_id)
    assert published is not None
    assert published.state == "published"

    store.release_worker(worker_id="worker-a")
    all_workers = store.list_worker_leases(active_only=False)
    assert all_workers[0].state == "stopped"


def test_control_worker_renews_job_lease_while_handler_runs(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_renewal",
        kind="workflow_run",
        run_id="R_fixture_renewal",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    observed: dict[str, object] = {}

    def _handler(job) -> None:
        initial = store.get_job(job.job_id)
        assert initial is not None
        observed["initial_expiry"] = initial.lease_expires_at
        deadline = time.time() + 4.0
        renewed = None
        while time.time() < deadline:
            current = store.get_job(job.job_id)
            assert current is not None
            if (
                current.lease_expires_at is not None
                and initial.lease_expires_at is not None
                and current.lease_expires_at > initial.lease_expires_at
            ):
                renewed = current.lease_expires_at
                break
            time.sleep(0.1)
        observed["renewed_expiry"] = renewed
        store.complete_job(job_id=job.job_id)

    worker = ControlWorker(
        store=store,
        handler=_handler,
        lease_seconds=2,
        poll_interval_s=0.05,
        worker_id="ctrl-worker-test",
    )

    assert worker.dispatch_once() is True
    assert observed["renewed_expiry"] is not None
    assert observed["renewed_expiry"] > observed["initial_expiry"]

    workers = store.list_worker_leases(active_only=False)
    assert len(workers) == 1
    assert workers[0].worker_id == "ctrl-worker-test"
    assert workers[0].state == "idle"
    assert workers[0].metadata["last_job_id"] == "job_fixture_renewal"


def test_control_plane_store_dead_letters_terminal_failures(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_failed",
        kind="workflow_run",
        run_id="R_fixture_failed",
        pipeline_id="pipeline_fixture",
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.fail_job(job_id="job_fixture_failed", error_message="permanent failure")

    failed = store.get_job("job_fixture_failed")
    assert failed is not None
    assert failed.state == "failed"

    dead_letters = store.list_dead_letter_jobs()
    assert len(dead_letters) == 1
    assert dead_letters[0].job_id == "job_fixture_failed"
    assert dead_letters[0].run_id == "R_fixture_failed"
    assert dead_letters[0].pipeline_id == "pipeline_fixture"
    assert dead_letters[0].error_message == "permanent failure"
    assert dead_letters[0].acknowledged_at is None

    store.acknowledge_dead_letter_job(
        job_id="job_fixture_failed",
        acknowledged_by="operator@example.test",
    )
    assert store.list_dead_letter_jobs() == []
    acknowledged = store.list_dead_letter_jobs(acknowledged=True)
    assert acknowledged[0].acknowledged_by == "operator@example.test"


def test_control_job_response_promotes_progress_failure_to_stable_envelope(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_preflight_failed",
        kind="natural_language_run",
        run_id="R_fixture_preflight_failed",
        pipeline_id=None,
        requested_execution_profile="research",
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.fail_job(
        job_id="job_fixture_preflight_failed",
        error_message="llm provider preflight failed",
        progress={
            "phase": "provider_preflight",
            "failure": {
                "code": "llm_provider_preflight_failed",
                "layer": "llm_gateway",
                "phase": "provider_preflight",
                "message": "Model is missing from /v1/models",
                "retryable": False,
                "model": "missing-model",
                "provider": "gonka_proxy",
                "next_action": "Check provider credentials and model configuration.",
                "owner": "team-runtime-ops",
                "upstream_missing_input": "llm_provider_model_catalog",
                "downstream_impact": "No serious decision packet can be materialized.",
                "authority_refs": {
                    "provider_preflight_ref": "sha256:" + "a" * 64,
                    "runtime_event_log": "sha256:" + "b" * 64,
                },
                "next_diagnostic_command": (
                    "uv run pytest "
                    "tests/unit/scientist/orchestration/llm/test_provider_verification.py -q"
                ),
            },
        },
    )

    record = store.get_job("job_fixture_preflight_failed")
    assert record is not None
    response = record.to_response(request_id="req-preflight")

    assert response.failure is not None
    assert response.failure.code == "llm_provider_preflight_failed"
    assert response.failure.layer == "llm_gateway"
    assert response.failure.phase == "provider_preflight"
    assert response.failure.model == "missing-model"
    assert response.failure.provider == "gonka_proxy"
    assert response.failure.next_action == "Check provider credentials and model configuration."
    body = response.model_dump(mode="json")
    diagnostic = body["failure"]["operator_diagnostic"]
    assert body["failure"]["retryable"] is False
    assert diagnostic["authoritative_runtime_state"] == "failed"
    assert diagnostic["projection_source"] == "runtime_control_job_failure"
    assert diagnostic["owner"] == "team-runtime-ops"
    assert diagnostic["phase"] == "provider_preflight"
    assert diagnostic["first_blocking_cause"] == "llm_provider_preflight_failed"
    assert diagnostic["upstream_missing_input"] == "llm_provider_model_catalog"
    assert diagnostic["downstream_impact"] == "No serious decision packet can be materialized."
    assert diagnostic["authority_refs"]["runtime_event_log"].startswith("sha256:")
    assert diagnostic["blocker_overridable"] is False
    assert diagnostic["next_diagnostic_command"].startswith("uv run pytest ")


def test_control_job_response_marks_completed_without_quality_evidence_as_failed(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_quality_missing",
        kind="natural_language_run",
        run_id="R_fixture_quality_missing",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_quality_missing",
        progress={"phase": "completed"},
    )

    record = store.get_job("job_fixture_quality_missing")
    assert record is not None
    response = record.to_response(request_id="req-quality-missing")
    body = response.model_dump(mode="json")

    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "fail"
    assert body["quality_gates"][0]["name"] == "quality_evidence_present"
    assert body["quality_gates"][0]["status"] == "fail"
    assert body["blocking_quality_failures"][0]["gate"] == "quality_evidence_present"


def test_control_plane_store_rejects_clean_completion_for_failed_workflow_progress(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_failed_progress",
        kind="workflow_run",
        run_id="R_fixture_failed_progress",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.complete_job(
        job_id="job_fixture_failed_progress",
        progress={
            "state": "failed",
            "runtime_state": "blocked",
            "authority_path": "workflow_failure",
            "authority_result": "repair_required",
            "legacy_path_disposition": "blocked_workflow_failure_ring2_withheld",
            "failure": {
                "code": "workflow_failed_non_authority",
                "message": "workflow returned fail",
            },
        },
    )

    record = store.get_job("job_fixture_failed_progress")
    assert record is not None
    assert record.state == "failed"
    assert record.error_message == "workflow returned fail"
    assert store.list_dead_letter_jobs()[0].job_id == "job_fixture_failed_progress"


def test_control_job_response_projects_operator_diagnostic_for_serious_quality_failure(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_operator_quality_failure",
        kind="natural_language_run",
        run_id="R_fixture_operator_quality_failure",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_operator_quality_failure",
        progress={
            "phase": "quality_evidence",
            "quality_scorecard": {
                "execution_status": "completed",
                "quality_status": "fail",
                "approval_state": "quality_failed",
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-operator",
                "evidence_refs": {
                    "quality_scorecard": "quality_evidence/quality_scorecard.json",
                    "policy_grounding_matrix": ("quality_evidence/policy_grounding_matrix.json"),
                },
                "quality_gates": [
                    {
                        "name": "policy_grounding_matrix_present",
                        "code": "policy_grounding_matrix_ref_missing",
                        "status": "fail",
                        "layer": "scientist_policy_artifacts",
                        "phase": "policy_grounding",
                        "message": "Policy grounding matrix ref is missing.",
                        "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                        "next_action": "Re-run final claim grounding before approval.",
                        "blocking": True,
                        "owner": "team-policy-semantics",
                        "upstream_missing_input": "policy_grounding_matrix_ref",
                        "downstream_impact": ("Readiness and approval projections remain closed."),
                        "authority_refs": {
                            "quality_scorecard": "quality_evidence/quality_scorecard.json",
                            "runtime_event_log": "sha256:" + "c" * 64,
                        },
                        "next_diagnostic_command": (
                            "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
                        ),
                    }
                ],
                "blocking_quality_failures": [],
            },
        },
    )

    record = store.get_job("job_fixture_operator_quality_failure")
    assert record is not None
    body = record.to_response(request_id="req-operator-quality").model_dump(mode="json")

    diagnostic = body["operator_diagnostic"]
    first_failure = body["blocking_quality_failures"][0]
    assert diagnostic["authoritative_runtime_state"] == "completed"
    assert diagnostic["projection_source"] == "runtime_quality_scorecard"
    assert diagnostic["owner"] == "team-policy-semantics"
    assert diagnostic["first_blocking_cause"] == "policy_grounding_matrix_ref_missing"
    assert diagnostic["upstream_missing_input"] == "policy_grounding_matrix_ref"
    assert diagnostic["downstream_impact"] == "Readiness and approval projections remain closed."
    assert diagnostic["authority_refs"]["quality_scorecard"] == (
        "quality_evidence/quality_scorecard.json"
    )
    assert diagnostic["next_diagnostic_command"].endswith(
        "tests/unit/runtime/quality/test_scorecard.py -q"
    )
    assert first_failure["operator_diagnostic"] == diagnostic


def test_control_job_response_fails_completed_scorecard_missing_runtime_quality_refs(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_missing_runtime_quality_refs",
        kind="natural_language_run",
        run_id="R_fixture_missing_runtime_quality_refs",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_missing_runtime_quality_refs",
        progress={
            "phase": "completed",
            "details": {
                "data_snapshot_ref": "sha256:" + "1" * 64,
                "input_bindings_ref": "sha256:" + "2" * 64,
                "registry_bundle_ref": "sha256:" + "3" * 64,
                "quality_report_ref": "sha256:" + "4" * 64,
            },
            "quality_scorecard": {
                "execution_status": "completed",
                "quality_status": "pass",
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-missing-refs",
                "evidence_refs": {
                    "quality_scorecard": "quality_evidence/quality_scorecard.json",
                    "normative_evidence": "quality_evidence/normative_evidence.json",
                    "fabric_retrieval_trace": "quality_evidence/fabric_retrieval_trace.json",
                    "foundry_method_report": "quality_evidence/foundry_method_report.json",
                    "policy_grounding_matrix": ("quality_evidence/policy_grounding_matrix.json"),
                    "conflict_check": "quality_evidence/conflict_check.json",
                },
                "quality_gates": [
                    {
                        "name": "normative_evidence_present",
                        "code": "normative_evidence_present",
                        "status": "pass",
                        "layer": "lex",
                        "phase": "quality_evidence",
                        "message": "Normative applicability evidence is present.",
                        "blocking": True,
                    },
                    {
                        "name": "fabric_retrieval_trace_present",
                        "code": "fabric_retrieval_trace_present",
                        "status": "pass",
                        "layer": "fabric_retrieval",
                        "phase": "quality_evidence",
                        "message": "Fabric source-selection evidence is present.",
                        "blocking": True,
                    },
                    {
                        "name": "foundry_method_evidence_present",
                        "code": "foundry_method_evidence_present",
                        "status": "pass",
                        "layer": "foundry_methods",
                        "phase": "quality_evidence",
                        "message": "Foundry method validity evidence is present.",
                        "blocking": True,
                    },
                    {
                        "name": "policy_grounding_matrix_present",
                        "code": "policy_grounding_matrix_present",
                        "status": "pass",
                        "layer": "scientist_policy_artifacts",
                        "phase": "quality_evidence",
                        "message": "Policy grounding matrix is present.",
                        "blocking": True,
                    },
                    {
                        "name": "conflict_check_present",
                        "code": "conflict_check_present",
                        "status": "pass",
                        "layer": "normative_conflict",
                        "phase": "quality_evidence",
                        "message": "Policy conflict check is present.",
                        "blocking": True,
                    },
                ],
                "blocking_quality_failures": [],
            },
        },
    )

    record = store.get_job("job_fixture_missing_runtime_quality_refs")
    assert record is not None
    response = record.to_response(request_id="req-runtime-quality-refs")
    body = response.model_dump(mode="json")
    gates = {gate["name"]: gate for gate in body["quality_gates"]}
    failures = {failure["gate"]: failure for failure in body["blocking_quality_failures"]}
    expected = {
        "normative_evidence_present": "normative_applicability_report_ref_missing",
        "fabric_retrieval_trace_present": "fabric_retrieval_trace_ref_missing",
        "foundry_method_evidence_present": "foundry_method_report_ref_missing",
        "policy_grounding_matrix_present": "policy_grounding_matrix_ref_missing",
        "conflict_check_present": "conflict_check_ref_missing",
        "causal_statistical_validity_present": ("causal_statistical_validity_report_ref_missing"),
        "replay_manifest_present": "replay_manifest_ref_missing",
        "drift_explanation_present": "drift_explanation_ref_missing",
        "resilience_matrix_present": "resilience_report_ref_missing",
        "human_review_calibration_present": "human_review_calibration_report_ref_missing",
        "privacy_compliance_report_present": "privacy_compliance_report_ref_missing",
        "decision_artifact_quality_present": "decision_artifact_quality_report_ref_missing",
    }

    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "fail"
    for gate_name, expected_code in expected.items():
        assert gates[gate_name]["status"] == "fail"
        assert gates[gate_name]["code"] == expected_code
        assert gates[gate_name]["next_action"]
        assert failures[gate_name]["code"] == expected_code
        assert failures[gate_name]["next_action"] == gates[gate_name]["next_action"]


def test_control_job_response_promotes_quality_scorecard_to_top_level(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_quality_scorecard",
        kind="natural_language_run",
        run_id="R_fixture_quality_scorecard",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_quality_scorecard",
        progress={
            "phase": "completed",
            "details": {
                "normative_applicability_report_ref": "sha256:" + "1" * 64,
                "fabric_retrieval_trace_ref": "sha256:" + "2" * 64,
                "foundry_method_report_ref": "sha256:" + "3" * 64,
                "policy_grounding_matrix_ref": "sha256:" + "4" * 64,
                "conflict_check_ref": "sha256:" + "5" * 64,
                "causal_statistical_validity_report_ref": "sha256:" + "6" * 64,
                "replay_manifest_ref": "sha256:" + "7" * 64,
                "drift_explanation_ref": "sha256:" + "8" * 64,
                "resilience_report_ref": "sha256:" + "9" * 64,
                "human_review_calibration_report_ref": "sha256:" + "a" * 64,
                "privacy_compliance_report_ref": "sha256:" + "b" * 64,
                "decision_artifact_quality_report_ref": "sha256:" + "c" * 64,
            },
            "quality_scorecard": {
                "execution_status": "completed",
                "quality_status": "warn",
                "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-1",
                "quality_gates": [
                    {
                        "name": "conflict_check_present",
                        "code": "indirect_policy_conflict",
                        "status": "warn",
                        "layer": "normative_conflict",
                        "phase": "corpus_compatibility",
                        "message": "Indirect conflict needs review.",
                        "evidence_ref": "quality_evidence/conflict_check.json",
                        "next_action": "Review medium severity compatibility conflict.",
                        "blocking": False,
                    }
                ],
                "blocking_quality_failures": [],
            },
        },
    )

    record = store.get_job("job_fixture_quality_scorecard")
    assert record is not None
    response = record.to_response(request_id="req-quality-scorecard")
    body = response.model_dump(mode="json")

    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "warn"
    assert body["quality_gates"][0]["name"] == "conflict_check_present"
    assert body["quality_gates"][0]["code"] == "indirect_policy_conflict"
    assert body["quality_gates"][0]["layer"] == "normative_conflict"
    assert body["quality_gates"][0]["phase"] == "corpus_compatibility"
    assert body["quality_gates"][0]["evidence_ref"] == "quality_evidence/conflict_check.json"
    assert body["quality_scorecard_ref"] == "quality_evidence/quality_scorecard.json"
    assert body["quality_evidence_bundle_path"] == ".polisyos/canary_evidence/run-1"
    assert body["blocking_quality_failures"] == []


def test_control_plane_store_persists_scorecard_refs_in_progress(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_scorecard_refs",
        kind="natural_language_run",
        run_id="R_fixture_scorecard_refs",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )

    store.complete_job(
        job_id="job_fixture_scorecard_refs",
        progress={
            "phase": "completed",
            "quality_status": "fail",
            "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
            "quality_evidence_bundle_path": ".polisyos/canary_evidence/run-scorecard",
            "evidence_refs": {
                "quality_scorecard": "quality_evidence/quality_scorecard.json",
                "fabric_retrieval_trace_ref": "sha256:" + "6" * 64,
            },
            "quality_gates": [
                {
                    "name": "fabric_retrieval_trace_present",
                    "code": "fabric_retrieval_trace_failed",
                    "status": "fail",
                    "layer": "fabric_retrieval",
                    "phase": "quality_evidence",
                    "message": "Fabric source-selection evidence failed.",
                    "evidence_ref": "quality_evidence/fabric_retrieval_trace.json",
                    "next_action": "Inspect source-selection diagnostics.",
                    "blocking": True,
                }
            ],
            "blocking_quality_failures": [
                {
                    "gate": "fabric_retrieval_trace_present",
                    "code": "fabric_retrieval_trace_failed",
                    "layer": "fabric_retrieval",
                    "phase": "quality_evidence",
                    "message": "Fabric source-selection evidence failed.",
                    "evidence_ref": "quality_evidence/fabric_retrieval_trace.json",
                    "next_action": "Inspect source-selection diagnostics.",
                }
            ],
        },
    )

    record = store.get_job("job_fixture_scorecard_refs")
    assert record is not None
    progress_scorecard = record.progress["quality_scorecard"]
    response = record.to_response(request_id="req-scorecard-refs")
    body = response.model_dump(mode="json")

    assert progress_scorecard["quality_scorecard_ref"] == (
        "quality_evidence/quality_scorecard.json"
    )
    assert progress_scorecard["quality_evidence_bundle_path"] == (
        ".polisyos/canary_evidence/run-scorecard"
    )
    assert progress_scorecard["evidence_refs"]["fabric_retrieval_trace_ref"].startswith("sha256:")
    assert body["execution_status"] == "completed"
    assert body["quality_status"] == "fail"
    assert body["quality_scorecard_ref"] == "quality_evidence/quality_scorecard.json"
    assert body["quality_evidence_bundle_path"] == ".polisyos/canary_evidence/run-scorecard"


def test_control_job_response_projects_policy_design_case_semantics_without_authority(
    tmp_path,
) -> None:
    store = _make_store(tmp_path)
    store.create_job(
        job_id="job_fixture_policy_design_projection",
        kind="natural_language_run",
        run_id="run-24",
        pipeline_id=None,
        requested_execution_profile="production",
        effective_execution_profile="production",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job_fixture_policy_design_projection",
        progress={
            "policy_design_case": policy_design_case(),
            "final_decision_artifact": {
                "artifact_kind": "publishable_decision_artifact",
                "publishability": "publishable",
                "decision_context": {"public_export_status": "publishable"},
                "authority_role": "final_decision_artifact",
            },
            "final_decision_artifact_ref": sha("9"),
        },
    )

    record = store.get_job("job_fixture_policy_design_projection")
    assert record is not None
    body = record.to_response(request_id="req-policy-design-projection").model_dump(mode="json")

    projection = body["policy_design_case_projection"]
    assert projection["primary_state"] == "publishable"
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert "publishable" in projection["states"]
    assert body["approval_projection"]["authority_level"] == "projection_only"


def test_control_plane_sqlite_uses_wal_journaling(tmp_path) -> None:
    db_path = tmp_path / "control-plane.sqlite3"
    _ = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)

    with sqlite3.connect(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert synchronous in {1, 2}


def test_scenario_head_create_cas_has_one_winner_across_store_instances(tmp_path) -> None:
    db_path = tmp_path / "control-plane.sqlite3"
    first_store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    second_store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    barrier = threading.Barrier(2)

    def _claim(store: ControlPlaneStore, artifact_ref: str, manifest_hash: str) -> bool:
        barrier.wait()
        return store.compare_and_set_scenario_head(
            scenario_id="scenario-shared",
            baseline_run_id="run-authorized",
            expected_revision=0,
            new_revision=1,
            artifact_ref=artifact_ref,
            manifest_hash=manifest_hash,
        )

    contenders = (
        (first_store, "sha256:first", "sha256:manifest-first"),
        (second_store, "sha256:second", "sha256:manifest-second"),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_claim, *contender) for contender in contenders]
        outcomes = [future.result() for future in futures]

    assert sorted(outcomes) == [False, True]
    winner = contenders[outcomes.index(True)]
    assert first_store.get_scenario_head("scenario-shared") == second_store.get_scenario_head(
        "scenario-shared"
    )
    head = first_store.get_scenario_head("scenario-shared")
    assert head is not None
    assert head.baseline_run_id == "run-authorized"
    assert head.revision == 1
    assert head.artifact_ref == winner[1]
    assert head.manifest_hash == winner[2]


def test_scenario_head_update_cas_denies_baseline_run_rebinding(tmp_path) -> None:
    store = _make_store(tmp_path)
    assert store.compare_and_set_scenario_head(
        scenario_id="scenario-bound",
        baseline_run_id="run-original",
        expected_revision=0,
        new_revision=1,
        artifact_ref="sha256:revision-one",
        manifest_hash="sha256:manifest-one",
    )

    assert not store.compare_and_set_scenario_head(
        scenario_id="scenario-bound",
        baseline_run_id="run-other",
        expected_revision=1,
        new_revision=2,
        artifact_ref="sha256:revision-two",
        manifest_hash="sha256:manifest-two",
    )

    head = store.get_scenario_head("scenario-bound")
    assert head is not None
    assert head.baseline_run_id == "run-original"
    assert head.revision == 1
    assert head.artifact_ref == "sha256:revision-one"
    assert head.manifest_hash == "sha256:manifest-one"
    assert store.list_scenario_heads(baseline_run_id="run-original") == [head]
    assert store.list_scenario_heads(baseline_run_id="run-other") == []


class _FlakyHeartbeatStore:
    def __init__(self) -> None:
        self.fail = threading.Event()

    def heartbeat_worker(self, **_kwargs) -> None:
        if self.fail.is_set():
            raise RuntimeDependencyUnavailableError(
                "control_plane_store",
                detail="control_plane_store executor is unavailable",
            )

    def renew_job_lease(self, **_kwargs) -> None:
        if self.fail.is_set():
            raise RuntimeDependencyUnavailableError(
                "control_plane_store",
                detail="control_plane_store executor is unavailable",
            )


class _FlakyReleaseStore:
    def release_worker(self, **_kwargs) -> None:
        raise RuntimeDependencyUnavailableError(
            "control_plane_store",
            detail="control_plane_store circuit breaker is open",
        )


def test_control_worker_stop_suppresses_store_unavailable_release() -> None:
    worker = ControlWorker(
        store=cast("ControlPlaneStore", _FlakyReleaseStore()),
        handler=lambda _job: None,
        lease_seconds=1,
        worker_id="ctrl-worker-release-unavailable",
    )

    worker.stop()


def test_control_worker_shutdown_suppresses_heartbeat_store_unavailable_logs(
    monkeypatch,
) -> None:
    store = _FlakyHeartbeatStore()
    warnings: list[tuple[object, ...]] = []
    exceptions: list[tuple[object, ...]] = []
    worker = ControlWorker(
        store=cast("ControlPlaneStore", store),
        handler=lambda _job: None,
        lease_seconds=1,
        worker_id="ctrl-worker-shutdown",
    )
    job = ControlJobRecord(
        job_id="job_shutdown",
        kind="workflow_run",
        state="running",
        run_id="R_shutdown",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="tester",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=None,
        lease_owner=worker.worker_id,
        lease_expires_at=None,
        attempt=1,
        error_message=None,
        progress={},
    )

    def _handler(_job: ControlJobRecord) -> None:
        store.fail.set()
        worker._stop.set()
        time.sleep(worker._heartbeat_interval_s + 0.05)

    monkeypatch.setattr(worker, "_handler", _handler)
    monkeypatch.setattr(
        control_worker_module.logger,
        "warning",
        lambda *args, **kwargs: warnings.append(args),
    )
    monkeypatch.setattr(
        control_worker_module.logger,
        "exception",
        lambda *args, **kwargs: exceptions.append(args),
    )

    worker._run_with_lease_heartbeat(job)

    assert warnings == []
    assert exceptions == []
