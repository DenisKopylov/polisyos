from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.contracts import ControlFailureEnvelope
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.pdc import OperationClass
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control.workspace_loop_transition import (
    RunBoundDesignRecordTenantNonReceipt,
)
from polisyos.runtime.quality.authority import ProductionLoopRunProof
from polisyos.runtime.quality.workspace import loop as workspace_loop_module
from polisyos.runtime.quality.workspace.loop import WorkspaceLoopRunProof
from polisyos.runtime.quality.workspace.s2_design_search_operation import (
    S2_DESIGN_SEARCH_OPERATION_ID,
)


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


def _layer2_s2_design_search_input() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[4]
    proving_case = json.loads(
        (
            repository_root
            / "architecture/policy_design_case/layer2_first_proving_case.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (
            repository_root
            / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
        ).read_text(encoding="utf-8")
    )
    candidate_space = manifest["candidate_space"]
    return {
        "schema_version": "policyos.policy_design_case.layer2_s2_design_search.v1",
        "case_id": str(proving_case["case_id"]),
        "intent_ref": "repo://architecture/policy_design_case/layer2_first_proving_case.json",
        "grammar_ref": "repo://src/polisyos/policy_grammar",
        "instrument_families": candidate_space["instrument_families"],
        "parameter_space": candidate_space["parameter_space"],
        "actor_ref": "actor://ua/ministry-of-economy",
        "domain": "ukrainian_msme_credit",
        "objective_refs": [f"objective://{item}" for item in proving_case["constructs"]],
        "construct_refs": [f"construct://{item}" for item in proving_case["constructs"]],
        "authority_profile_ref": "authority_profile.shadow",
        "requested_posture": "shadow",
        "generated_at": "2026-05-30T00:00:00Z",
        "rule_version_ref": "policyos.layer2.s2.design_search.v1",
    }


def _s2_artifact_census(cas_root: Path) -> dict[str, int]:
    expected = {
        "policyos.layer2_s2.design_record_v0",
        "policyos.layer2_s2.search_ledger",
        "policyos.pdc.run_bound_design_record_binding",
    }
    counts = dict.fromkeys(expected, 0)
    for path in cas_root.glob("artifacts/sha256/*/*/*.manifest.json"):
        kind = json.loads(path.read_text(encoding="utf-8"))["kind"]
        if kind in counts:
            counts[kind] += 1
    return counts


def _s2_registry_with_fault(fault: str):
    registry = workspace_loop_module.build_workspace_operation_registry()
    operations = dict(registry.operations)
    registration = operations[S2_DESIGN_SEARCH_OPERATION_ID]
    if fault == "removed":
        operations.pop(S2_DESIGN_SEARCH_OPERATION_ID)
    elif fault == "disabled":
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"executable": False}
        )
    elif fault == "registration_id":
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"operation_id": "phase2.refine.substituted_design_search"}
        )
    elif fault == "operation_class":
        substituted_contract = registration.contract.model_copy(
            update={"operation_class": OperationClass.BIND}
        )
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={
                "operation_class": OperationClass.BIND,
                "contract": substituted_contract,
            }
        )
    elif fault == "contract_id":
        substituted_contract = registration.contract.model_copy(
            update={"operation_id": "phase2.refine.substituted_design_search"}
        )
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"contract": substituted_contract}
        )
    elif fault == "contract_class":
        substituted_contract = registration.contract.model_copy(
            update={"operation_class": OperationClass.BIND}
        )
        operations[S2_DESIGN_SEARCH_OPERATION_ID] = registration.model_copy(
            update={"contract": substituted_contract}
        )
    else:  # pragma: no cover - the parametrization is the complete mutation set
        raise AssertionError(f"unsupported registry fault: {fault}")
    return registry.model_copy(update={"operations": operations})


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


def test_s2_design_search_real_http_worker_closes_run_bound_case(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    search_input = _layer2_s2_design_search_input()
    before = _s2_artifact_census(Path(runtime_api_env["cas_root"]))

    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "params": {
                "control_plane_transition": "workspace_loop",
                "workspace_operation_id": "phase2.refine.layer2_s2_design_search",
                "layer2_s2_design_search_input": search_input,
            },
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch = launch_response.json()
    assert service._worker is not None
    deadline = time.monotonic() + 15.0
    job_response = client.get(f"/api/v1/control/jobs/{launch['job_id']}")
    while (
        job_response.json()["state"] in {"pending", "running"}
        and time.monotonic() < deadline
    ):
        service._worker.dispatch_once()
        time.sleep(0.02)
        job_response = client.get(f"/api/v1/control/jobs/{launch['job_id']}")

    assert job_response.status_code == 200
    job = job_response.json()
    assert job["state"] == "completed", job
    assert job["progress"]["workspace_operation_id"] == (
        "phase2.refine.layer2_s2_design_search"
    )
    after = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    assert {kind: after[kind] - before[kind] for kind in before} == {
        "policyos.layer2_s2.design_record_v0": 1,
        "policyos.layer2_s2.search_ledger": 1,
        "policyos.pdc.run_bound_design_record_binding": 1,
    }

    paper_response = client.get(f"/api/v1/runs/{launch['run_id']}/paper")
    assert paper_response.status_code == 200, paper_response.text
    packet = paper_response.json()
    binding = packet["case_record"]["design_record_binding"]
    assert packet["case_record"]["availability"] == (
        "record_available_authority_abstaining"
    )
    assert binding["run_id"] == launch["run_id"]
    assert binding["tenant_id"] == runtime_api_env["tenant_a"]
    assert binding["cell_id"] == runtime_api_env["cell_a"]
    assert binding["case_id"] == search_input["case_id"]
    assert packet["run"]["tenant_id"] == runtime_api_env["tenant_a"]
    assert packet["run"]["cell_id"] == runtime_api_env["cell_a"]
    assert packet["source"]["manifest_ref"] == job["progress"]["manifest_ref"]


def test_s2_design_search_real_http_worker_tenantless_refuses_with_zero_pdc_writes(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = runtime_api_env["client"]
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    producer_calls: list[object] = []

    monkeypatch.setattr(
        "polisyos.runtime.http.routes.control._get_principal",
        lambda _request: RuntimePrincipal(
            subject="tenantless-falsifier",
            authenticated=True,
            tenant_id=None,
            cell_id=None,
        ),
    )

    def _producer_must_not_run(value: object):
        producer_calls.append(value)
        raise AssertionError("S2 producer ran without tenant authority")

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.s2_design_search_operation."
        "run_s2_shadow_design_loop",
        _producer_must_not_run,
    )
    before = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "params": {
                "control_plane_transition": "workspace_loop",
                "workspace_operation_id": "phase2.refine.layer2_s2_design_search",
                "layer2_s2_design_search_input": _layer2_s2_design_search_input(),
                "tenant_id": "tenant-unknown",
                "cell_id": "forged-cell",
            },
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch = launch_response.json()
    assert service._worker is not None
    service._worker.dispatch_once()
    response = _await_terminal_job(service, launch["job_id"])

    assert response.state == "failed"
    assert response.runtime_state == "blocked"
    assert response.progress["authority_result"] == "repair_required"
    nonreceipt = RunBoundDesignRecordTenantNonReceipt.model_validate(
        response.progress["run_bound_design_record_nonreceipt"]
    )
    assert nonreceipt == RunBoundDesignRecordTenantNonReceipt()
    assert response.failure is not None
    expected_failure = ControlFailureEnvelope(
        code="run_bound_design_record_tenant_scope_missing",
        layer="pdc.gy",
        phase="s2_design_search_persist",
        message=(
            "Run-bound DesignRecord persistence requires a verified ambient tenant scope."
        ),
        retryable=False,
        next_action=(
            "Re-launch under an authenticated principal with a verified tenant scope; "
            "tenant_id is not caller-supplied."
        ),
        run_id=launch["run_id"],
        job_id=launch["job_id"],
        artifact_refs={},
    )
    assert type(response.failure) is ControlFailureEnvelope
    assert response.failure.model_dump(exclude={"operator_diagnostic"}) == (
        expected_failure.model_dump(exclude={"operator_diagnostic"})
    )
    assert response.failure.code == "run_bound_design_record_tenant_scope_missing"
    assert response.failure.layer == "pdc.gy"
    assert response.failure.phase == "s2_design_search_persist"
    assert response.failure.artifact_refs == {}
    assert producer_calls == []
    assert _s2_artifact_census(Path(runtime_api_env["cas_root"])) == before
    rendered_progress = json.dumps(response.progress, sort_keys=True)
    assert "tenant-unknown" not in rendered_progress
    assert "forged-cell" not in rendered_progress


@pytest.mark.parametrize(
    "registry_fault",
    [
        "removed",
        "disabled",
        "registration_id",
        "operation_class",
        "contract_id",
        "contract_class",
    ],
)
def test_s2_design_search_real_http_worker_refuses_untrusted_registry_rows_before_writes(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    registry_fault: str,
) -> None:
    client = runtime_api_env["client"]
    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    producer_calls: list[object] = []
    faulting_registry = _s2_registry_with_fault(registry_fault)

    monkeypatch.setattr(
        workspace_loop_module,
        "build_workspace_operation_registry",
        lambda: faulting_registry,
    )

    def _producer_must_not_run(value: object):
        producer_calls.append(value)
        raise AssertionError("S2 producer ran without a trusted executable registration")

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.s2_design_search_operation.run_s2_shadow_design_loop",
        _producer_must_not_run,
    )
    before = _s2_artifact_census(Path(runtime_api_env["cas_root"]))
    launch_response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            "params": {
                "control_plane_transition": "workspace_loop",
                "workspace_operation_id": S2_DESIGN_SEARCH_OPERATION_ID,
                "layer2_s2_design_search_input": _layer2_s2_design_search_input(),
            },
        },
    )
    assert launch_response.status_code == 200, launch_response.text
    launch = launch_response.json()
    assert service._worker is not None
    service._worker.dispatch_once()
    response = _await_terminal_job(service, launch["job_id"])

    assert response.state == "failed"
    assert response.failure is not None
    assert response.failure.code == "s2_design_search_failed_non_authority"
    assert producer_calls == []
    assert _s2_artifact_census(Path(runtime_api_env["cas_root"])) == before


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
async def test_public_nl_route_persists_n4_candidate_without_n6_s8_or_publication(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The authorized public route persists N4 while authority stages remain unrun."""
    import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _design_problem_tool_args,
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
        _intent_context,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )
    from tests.unit.runtime.quality.test_design_generation import (
        RecordedClientWithCatalog,
        _recording_with_successful_first_response,
    )

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    raw_request = (
        "Design a wartime MSME credit guarantee for Ukraine within the stated UAH 10b budget cap."
    )
    compiler_arguments = _design_problem_tool_args()
    compiler_arguments["nl_provenance"]["source_context"] = {
        "tenant_id": "tenant-llm-foreign",
        "cell_id": "cell-llm-foreign",
        "job_id": "job-llm-foreign",
        "run_id": "run-llm-foreign",
        "runtime_identity": {
            "tenant_id": "tenant-llm-runtime-foreign",
            "cell_id": "cell-llm-runtime-foreign",
            "job_id": "job-llm-runtime-foreign",
            "run_id": "run-llm-runtime-foreign",
        },
    }
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=compiler_arguments,
    )
    generation_gateway = RecordedClientWithCatalog(recording, model_ids=[model_id])
    original_compiler = nl_pipeline.build_design_problem_from_nl_request

    async def compile_with_deterministic_gateway(**kwargs):
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        compile_with_deterministic_gateway,
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        lambda **_kwargs: generation_gateway,
    )

    service: ControlPlaneService = runtime_api_env["app"].state._control_service
    runtime_container = runtime_api_env["app"].state.runtime_container
    bearer = _fixture_bearer("control-r5-n4-positive-candidate")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_container.runtime_api_context,
            control_service=service,
            decision_validity_service=service._decision_validity_service,
            claim_ledger_owner=service._epoch_claim_lifecycle_bridge.claim_owner,
            epoch_claim_lifecycle_bridge=service._epoch_claim_lifecycle_bridge,
        ),
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-control-r5-n4-positive-candidate",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    cell_id = cell.cell_id
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    request_body = {
        "request": raw_request,
        "llm_model": model_id,
        "max_iterations": 1,
        "context": _intent_context(
            as_of="2026-05-12",
            tenant_id="tenant-request-foreign",
            cell_id="cell-request-foreign",
            job_id="job-request-foreign",
            run_id="run-request-foreign",
            runtime_identity={
                "tenant_id": "tenant-request-runtime-foreign",
                "cell_id": "cell-request-runtime-foreign",
                "job_id": "job-request-runtime-foreign",
                "run_id": "run-request-runtime-foreign",
            },
        ),
    }
    try:
        launch_response = client.post(
            "/api/v1/control/runs/nl",
            json=request_body,
            headers=headers,
        )
        assert launch_response.status_code == 200, launch_response.text
        launch = launch_response.json()
        assert launch["status"] == "accepted"
        job_id = str(launch["job_id"])
        job = service._control_store.get_job(job_id)
        assert job is not None

        def reject_downstream(*_args, **_kwargs):
            pytest.fail("candidate-only N4 entered a downstream authority stage")

        monkeypatch.setattr(service, "resolve_generation_value_choices", reject_downstream)
        monkeypatch.setattr(service, "_publish_generation_run", reject_downstream)
        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            reject_downstream,
        )
        assert service._worker is not None
        service._worker.dispatch_once()

        completed = _await_terminal_job(service, job_id)
        assert completed.state == "completed"
        assert compiler_gateway.generate_calls
        assert generation_gateway._cursor > 0
        assert completed.progress["execution_intent_band"] == "candidate_only"
        assert completed.progress["execution_band"] == "candidate"
        assert completed.progress["status"] == "candidate_limited"
        assert completed.progress["candidate_computation_status"] == "completed"
        assert completed.progress["n5_status"] == "not_run"
        assert completed.progress["n8_status"] == "not_run"
        assert completed.progress["n9_status"] == "not_run"
        assert completed.progress["s8_status"] == "not_run"
        assert "compiled_recursive_generation_cycle_ref" not in completed.progress
        assert completed.progress.get("normative_disposition_ref") is None
        assert completed.progress.get("manifest_ref") is None

        payload = service._load_payload_ref(str(job.payload_ref))
        assert payload["tenant_id"] == runtime_api_env["tenant_a"]
        assert payload["cell_id"] == cell_id
        intent_binding = service._require_nl_job_execution_intent_binding(
            job=job,
            payload=payload,
        )
        assert intent_binding["admission_surface"] == "served_route"
        assert intent_binding["intent_band"] == "candidate_only"
        authorization_receipt = intent_binding["authorization_receipt"]
        assert authorization_receipt["route_id"] == "POST /api/v1/control/runs/nl"
        permission_snapshot = authorization_receipt["permission_snapshot"]
        assert permission_snapshot["required_permission"] == RuntimePermission.RUNS_LAUNCH.value
        assert permission_snapshot["subject"] == "user-1"
        assert permission_snapshot["jwt_id"] == "jwt-control-r5-n4-positive-candidate"
        assert permission_snapshot["tenant_id"] == runtime_api_env["tenant_a"]
        assert permission_snapshot["roles"] == [PolicyOSRole.ANALYST.value]
        assert authorization_receipt["resource"]["tenant_id"] == runtime_api_env["tenant_a"]
        proposal_locator = completed.progress["candidate_proposal_ref"]
        assert proposal_locator["schema_version"] == (
            "policyos.runtime.quality.n4_candidate_proposal_locator.v1"
        )
        assert proposal_locator["artifact_ref"]["kind"] == (
            "runtime.quality.n4_candidate_proposal"
        )
        proposal = GenerationSourceRepository(
            service._artifact_store
        ).load_candidate_proposal_for_served_job(
            proposal_locator,
            job_id=job_id,
            run_id=str(job.run_id),
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell_id,
            raw_request=raw_request,
        )
        assert proposal.problem.nl_provenance.raw_request == raw_request
        assert proposal.problem.nl_provenance.source_context["tenant_id"] == (
            runtime_api_env["tenant_a"]
        )
        assert proposal.problem.nl_provenance.source_context["cell_id"] == cell_id
        assert proposal.problem.nl_provenance.source_context["job_id"] == job.job_id
        assert proposal.problem.nl_provenance.source_context["run_id"] == str(job.run_id)
        assert "runtime_identity" not in proposal.problem.nl_provenance.source_context
        intent_envelope = proposal.problem.to_policy_intent_envelope()
        assert intent_envelope["tenant_id"] == runtime_api_env["tenant_a"]
        assert intent_envelope["job_id"] == job.job_id
        assert intent_envelope["run_id"] == str(job.run_id)
        assert (
            intent_envelope["authoring_provenance"]["source_context"]["cell_id"]
            == cell_id
        )
        compiler_context = json.loads(compiler_gateway.generate_calls[0]["user"])["context"]
        assert "runtime_identity" not in compiler_context
        assert not set(compiler_context["candidate_context"]).intersection(
            {"tenant_id", "cell_id", "job_id", "run_id", "runtime_identity"}
        )
        assert compiler_context["tenant_id"] == runtime_api_env["tenant_a"]
        assert compiler_context["cell_id"] == cell_id
        assert compiler_context["job_id"] == job.job_id
        assert compiler_context["run_id"] == str(job.run_id)
        persisted_request = service._load_payload_ref(str(job.payload_ref))
        assert persisted_request["context"]["tenant_id"] == "tenant-request-foreign"
        assert (
            persisted_request["context"]["runtime_identity"]["cell_id"]
            == "cell-request-runtime-foreign"
        )
        assert proposal.proposal.trinity_bundle.policy_spec.interventions
        assert proposal.proposal.limitation_code == "cycle_substrate_context_unavailable"
    finally:
        client.close()
