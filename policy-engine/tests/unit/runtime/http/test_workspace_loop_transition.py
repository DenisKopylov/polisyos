from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.contracts.control import NaturalLanguageRunRequest, WorkflowRunRequest
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.quality.authority import ProductionLoopRunProof
from polisyos.runtime.quality.workspace.loop import WorkspaceLoopRunProof


def _await_terminal_job(service: ControlPlaneService, job_id: str):
    deadline = time.monotonic() + 15.0
    response = service.get_job_status(job_id)
    while response.state in {"pending", "running"} and time.monotonic() < deadline:
        if service._worker is not None:
            service._worker.dispatch_once()
        time.sleep(0.02)
        response = service.get_job_status(job_id)
    return response


def _build_slice0_catalog(tmp_path: Path):
    return build_slice0_fixture_catalog_graph(tmp_path)


def _assert_surface_packet_consumes_boundary(
    progress: dict[str, object],
    *,
    expected_result: str,
) -> None:
    boundary = progress["authority_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["decision_grade"] == "unsupported"
    assert boundary["posture"] == "shadow"
    assert "runtime_closeout_authority" in boundary["may_not_use_for"]
    packet = progress["authority_surface_packet"]
    assert isinstance(packet, dict)
    assert packet["boundary"] == boundary
    surfaces = packet["surfaces"]
    assert isinstance(surfaces, dict)
    assert set(surfaces) >= {
        "run",
        "artifact",
        "lineage",
        "export",
        "dashboard",
        "public_packet",
    }
    for surface_name in (
        "run",
        "artifact",
        "lineage",
        "export",
        "dashboard",
        "public_packet",
    ):
        surface = surfaces[surface_name]
        assert isinstance(surface, dict)
        assert surface["consumed_boundary_id"] == boundary["boundary_id"]
        assert surface["authority_result"] == expected_result
        assert surface["decision_grade"] == "unsupported"
        assert set(surface["may_not_use_for"]) >= set(boundary["may_not_use_for"])
    assert progress["artifact_projection"] == surfaces["artifact"]
    assert progress["lineage_projection"] == surfaces["lineage"]
    assert progress["export_projection"] == surfaces["export"]
    assert progress["public_packet"] == {
        "authority_boundary": boundary,
        "projection": surfaces["public_packet"],
    }
    artifacts_index = progress["artifacts_index"]
    assert isinstance(artifacts_index, dict)
    assert artifacts_index["authority_boundary"] == boundary["boundary_id"]
    assert artifacts_index["authority_surface_packet"] == "progress.authority_surface_packet"
    scorecard = progress["quality_scorecard"]
    assert isinstance(scorecard, dict)
    assert scorecard["authority_boundary"] == boundary
    assert scorecard["authority_surface_packet"] == packet
    assert scorecard["approval_ready"] is False
    assert scorecard["approval_state"] == "candidate_only"
    for row in scorecard["quality_gates"] + scorecard["blocking_quality_failures"]:
        assert row["authority_refs"]["authority_boundary"] == boundary["boundary_id"]


def test_workflow_request_defaults_to_workspace_loop_transition(runtime_api_env) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={"slice0_fixture_id": "ua_msme_credit_worldbank_measurement"},
    )

    launch = service.launch_workflow_run(request)
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "completed"
    assert response.progress["authority_path"] == "workspace_loop"
    assert response.progress["authority_result"] == "verifier_stamped"
    assert response.progress["search_exit_contract_ref"].startswith("sha256:")
    assert response.progress["production_loop_run_proof_ref"].startswith("sha256:")
    assert response.approval_projection.eligible is False

    proof = WorkspaceLoopRunProof.model_validate(response.progress["production_loop_run_proof"])
    assert proof.job_id == launch.job_id
    assert proof.run_id == launch.run_id
    assert proof.endpoint == "/api/v1/control/runs"
    assert proof.legacy_path_disposition == "routed_to_workspace_loop"
    assert proof.output_search_exit_contract_ref == response.progress["search_exit_contract_ref"]
    assert "runs_readback" in proof.surface_reads_checked
    assert proof.surface_readbacks
    readback = proof.surface_readbacks[0]
    assert readback["surface"] == "/api/v1/control/runs"
    assert readback["observed_job_state"] == "completed"
    assert readback["observed_search_exit_contract_ref"] == response.progress[
        "search_exit_contract_ref"
    ]
    assert readback["matched_search_exit_contract_ref"] is True


def test_http_control_route_persists_production_and_replay_proofs(runtime_api_env) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    client = runtime_api_env["client"]
    service._artifact_store.record_artifact_owner(
        runtime_api_env["root_artifact_id"],
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        writer="test_http_control_route_persists_production_and_replay_proofs",
    )

    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {
                "data_snapshot_ref": runtime_api_env["root_artifact_id"],
            },
            "params": {
                "slice0_fixture_id": "ua_msme_credit_worldbank_measurement",
            },
        },
        headers={"X-Request-ID": "gy-l-http-route-proof"},
    )
    assert launch_response.status_code == 200
    launch = launch_response.json()
    assert service._worker is not None
    deadline = time.monotonic() + 15.0
    readback_response = client.get(f"/api/v1/control/jobs/{launch['job_id']}")
    while (
        readback_response.json()["state"] in {"pending", "running"}
        and time.monotonic() < deadline
    ):
        service._worker.dispatch_once()
        time.sleep(0.02)
        readback_response = client.get(
            f"/api/v1/control/jobs/{launch['job_id']}",
            headers={"X-Request-ID": "gy-l-http-readback-proof"},
        )
    assert readback_response.status_code == 200
    progress = readback_response.json()["progress"]
    proof = ProductionLoopRunProof.model_validate(progress["production_loop_run_proof"])

    assert proof.job_id == launch["job_id"]
    assert proof.run_id == launch["run_id"]
    assert proof.http_request_id == "gy-l-http-route-proof"
    assert proof.control_store_state_transitions == ["pending", "running", "completed"]
    assert proof.output_replay_proof_ref.startswith("sha256:")
    assert "outcome_replay_proof_ref" in proof.artifacts_index_refs
    assert progress["outcome_replay_proof"]["replay_levels"] == ["A", "B", "C"]
    assert progress["outcome_replay_proof"]["output_hash"].startswith("sha256:")
    assert progress["outcome_replay_proof"]["input_hashes"]


def test_workspace_loop_non_authority_terminal_is_not_verifier_stamped(
    runtime_api_env,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            params={"slice0_fixture_id": "tourism_local_development_ceiling_probe"},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "completed"
    assert response.progress["authority_path"] == "workspace_loop"
    assert response.progress["authority_result"] == "acquisition_required"
    assert response.progress["search_exit_contract"]["terminal_state"]["kind"] == (
        "acquisition_required"
    )
    assert response.progress["search_exit_contract"]["authority_boundary"] is None
    assert response.progress["authority_derivation_trace_refs"] == []
    assert response.quality_status == "fail"
    assert any(gate.code == "acquisition_required" for gate in response.quality_gates)


def test_workflow_transition_uses_injected_catalog_and_persists_measurement_payload(
    runtime_api_env,
    monkeypatch,
    tmp_path,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    catalog = _build_slice0_catalog(tmp_path)
    service._registry_providers = replace(
        service._registry_providers,
        gy_catalog_graph=catalog,
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            params={"slice0_fixture_id": "ua_msme_credit_worldbank_measurement"},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    proof = WorkspaceLoopRunProof.model_validate(response.progress["production_loop_run_proof"])
    envelopes = response.progress["search_exit_contract"]["artifact_envelopes"]
    measurement_payload_ref = envelopes[0]["payload_ref"]

    assert response.state == "completed"
    assert measurement_payload_ref in proof.output_cas_refs
    assert service._artifact_store.get_bytes(measurement_payload_ref)
    assert proof.artifacts_index_refs[0] == "search_exit_contract_ref"
    assert "authority_derivation_trace_refs" in proof.artifacts_index_refs


def test_legacy_workflow_shadow_cannot_emit_authority_completed_result(runtime_api_env, monkeypatch) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={"control_plane_transition": "legacy_shadow"},
    )
    called = {"run_experiment": False}

    def _legacy_success(*_args, **_kwargs):
        called["run_experiment"] = True
        return {"status": "success", "authority_boundary": {"decision_grade": "decision_admissible"}}

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _legacy_success)

    launch = service.launch_workflow_run(request)
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert called["run_experiment"] is True
    assert response.state == "completed"
    assert response.progress["authority_path"] == "legacy_shadow"
    assert response.progress["authority_result"] == "candidate_only"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="candidate_only",
    )
    assert response.operator_diagnostic is not None
    assert response.operator_diagnostic.authority_refs["authority_boundary"] == response.progress[
        "authority_boundary"
    ]["boundary_id"]
    assert response.quality_status == "fail"
    assert any(gap.code == "legacy_shadow_candidate_only" for gap in response.unresolved_authority_gaps)


def test_failed_workflow_result_is_blocked_across_authority_surfaces(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _workflow_failure_result(_state_payload, _checkpoint_policy):
        return {
            "status": "fail",
            "state": "completed",
            "authority_boundary": {
                "decision_grade": "decision_admissible",
                "authoritative_for": ["runtime_closeout_authority"],
            },
        }

    monkeypatch.setattr(
        ControlPlaneService,
        "_execute_workflow",
        staticmethod(_workflow_failure_result),
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "failed"
    assert response.progress["authority_path"] == "workflow_failure"
    assert response.progress["authority_result"] == "repair_required"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="blocked",
    )
    assert response.operator_diagnostic is not None
    assert response.operator_diagnostic.authority_refs["authority_boundary"] == response.progress[
        "authority_boundary"
    ]["boundary_id"]
    assert response.failure is not None
    assert response.failure.code == "workflow_failed_non_authority"
    assert response.failure.operator_diagnostic is not None
    assert response.failure.operator_diagnostic.authority_refs["authority_boundary"] == (
        response.progress["authority_boundary"]["boundary_id"]
    )
    assert response.quality_status == "fail"
    assert response.approval_projection.eligible is False
    assert any(gap.code == "workflow_failed_non_authority" for gap in response.unresolved_authority_gaps)


def test_workspace_loop_exception_is_blocked_across_authority_surfaces(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _run_fixture_failure(self, fixture_id):
        del self, fixture_id
        raise RuntimeError("workspace loop failed before contract")

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.loop.WorkspaceLoop.run_fixture",
        _run_fixture_failure,
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "failed"
    assert response.progress["authority_path"] == "workflow_failure"
    assert response.progress["authority_result"] == "repair_required"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="blocked",
    )
    assert response.failure is not None
    assert response.failure.code == "workspace_loop_failed_non_authority"
    assert response.failure.operator_diagnostic is not None
    assert response.failure.operator_diagnostic.authority_refs["authority_boundary"] == (
        response.progress["authority_boundary"]["boundary_id"]
    )
    assert any(
        gap.code == "workspace_loop_failed_non_authority"
        for gap in response.unresolved_authority_gaps
    )


def test_failed_workflow_authority_packet_is_visible_through_http_job_route(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _workflow_failure_result(_state_payload, _checkpoint_policy):
        return {"status": "fail", "message": "fixture fail"}

    monkeypatch.setattr(
        ControlPlaneService,
        "_execute_workflow",
        staticmethod(_workflow_failure_result),
    )

    launch = service.launch_workflow_run(
        WorkflowRunRequest(
            data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()
    _await_terminal_job(service, launch.job_id)

    response = runtime_api_env["client"].get(f"/api/v1/control/jobs/{launch.job_id}")
    assert response.status_code == 200
    body = response.json()
    boundary = body["progress"]["authority_boundary"]
    packet = body["progress"]["authority_surface_packet"]
    assert body["state"] == "failed"
    assert body["failure"]["code"] == "workflow_failed_non_authority"
    assert body["operator_diagnostic"]["authority_refs"]["authority_boundary"] == (
        boundary["boundary_id"]
    )
    assert body["failure"]["operator_diagnostic"]["authority_refs"]["authority_boundary"] == (
        boundary["boundary_id"]
    )
    assert packet["boundary"] == boundary
    for surface_name in ("run", "artifact", "lineage", "export", "dashboard", "public_packet"):
        surface = packet["surfaces"][surface_name]
        assert surface["authority_result"] == "blocked"
        assert surface["consumed_boundary_id"] == boundary["boundary_id"]
    assert body["progress"]["public_packet"] == {
        "authority_boundary": boundary,
        "projection": packet["surfaces"]["public_packet"],
    }


def test_failed_legacy_workflow_does_not_complete_clean_as_authority(runtime_api_env, monkeypatch) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
        params={"control_plane_transition": "legacy_shadow"},
    )

    def _legacy_failure(*_args, **_kwargs):
        raise RuntimeError("workflow fail")

    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _legacy_failure)

    launch = service.launch_workflow_run(request)
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "failed"
    assert response.progress["authority_result"] == "repair_required"
    _assert_surface_packet_consumes_boundary(
        response.progress,
        expected_result="blocked",
    )
    assert response.failure is not None
    assert response.failure.code == "legacy_workflow_failed_non_authority"


@pytest.mark.asyncio
async def test_nl_runs_path_is_legacy_shadow_until_loop_proposer_exists(
    runtime_api_env,
    monkeypatch,
) -> None:
    service: ControlPlaneService = runtime_api_env["app"].state._control_service

    def _execute_nl_pipeline(**_kwargs):
        raise AssertionError("/runs/nl legacy-shadow path must not execute NL pipeline")

    monkeypatch.setattr(service, "_execute_nl_pipeline", _execute_nl_pipeline)

    launch = await service.launch_nl_run(
        NaturalLanguageRunRequest(
            request="Estimate whether UA MSME credit access can be measured.",
            max_iterations=1,
        )
    )
    assert service._worker is not None
    service._worker.dispatch_once()

    response = _await_terminal_job(service, launch.job_id)
    assert response.state == "completed"
    assert response.progress["authority_path"] == "legacy_shadow"
    assert response.progress["authority_result"] == "candidate_only"
    assert response.quality_status == "fail"
    assert any(gap.code == "legacy_shadow_candidate_only" for gap in response.unresolved_authority_gaps)
