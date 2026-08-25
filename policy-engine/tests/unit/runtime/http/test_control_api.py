"""Tests for Control Plane API routes."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders
from polisyos.scientist.governance.continuous.monitors import (
    DecisionValidityStatus as ContinuousDecisionValidityStatus,
)
from polisyos.scientist.governance.continuous.reissue import build_reissue_packet
from polisyos.scientist.orchestration.llm.provider_verification import ProviderPreflightReport
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _secure_control_client(
    runtime_api_env,
    *,
    role: PolicyOSRole,
    case_id: str,
):
    bearer = _fixture_bearer(f"control-{case_id}")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-control-{case_id}",
            roles=frozenset({role}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }
    return client, cell.cell_id, headers


def _with_fresh_step_up(client, headers: dict[str, str]) -> dict[str, str]:
    return {
        **headers,
        "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
    }


def _align_secure_artifact_ownership(
    runtime_api_env,
    *,
    client,
    cell_id: str,
    artifact_ids: tuple[str, ...],
) -> None:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    for artifact_id in artifact_ids:
        store.record_artifact_owner(
            artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell_id,
            writer="tests.runtime_http.control_authz",
        )
    client.app.state.runtime_container.runtime_api_context.run_index.refresh(force=True)


def _production_approval_scorecard(
    *,
    run_id: str,
    evidence_bundle_path: str,
    performance_status: str = "pass",
) -> dict[str, object]:
    return {
        "schema_version": "policyos.quality_scorecard.v1",
        "generated_at": "2026-05-13T09:00:00+00:00",
        "canary_kind": "production",
        "job_id": "job_quality_api_fixture",
        "run_id": run_id,
        "execution_status": "completed",
        "quality_status": "pass",
        "performance_status": performance_status,
        "conflict_status": "pass",
        "approval_state": "approval_ready",
        "quality_gates": [
            {
                "name": "conflict_check_present",
                "code": "conflict_check_present",
                "status": "pass",
                "layer": "normative_conflict",
                "phase": "quality_evidence",
                "message": "Policy conflict check is present.",
                "evidence_ref": "quality_evidence/conflict_check.json",
                "blocking": True,
            }
        ],
        "blocking_quality_failures": [],
        "warnings": [],
        "evidence_refs": {
            "quality_scorecard": _sha("a"),
            "conflict_check_ref": _sha("b"),
            "performance_summary": "performance.json",
        },
        "quality_scorecard_ref": _sha("a"),
        "quality_evidence_bundle_path": evidence_bundle_path,
    }


def _persist_scorecard(runtime_api_env, scorecard: dict[str, object]) -> str:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    ref = store.put_json(
        scorecard,
        ArtifactWriteOptions(
            kind="runtime.quality_scorecard",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    store.record_artifact_owner(
        ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        writer="test",
    )
    return str(ref.artifact_id)


def _artifact_ref(artifact_id: str, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        media_type="application/json",
    )


def _register_lifecycle_decision_packet(
    runtime_api_env,
    *,
    dependency_kind: DecisionDependencyKind,
    dependency_key: str,
    lineage_key: str,
) -> str:
    store = FileSystemCAS(runtime_api_env["cas_root"])
    service = DecisionValidityService(store)
    packet_ref = runtime_api_env["decision_packet_artifact_id"]
    envelope = DecisionValidityEnvelope(
        decision_lineage_key=lineage_key,
        policy_fingerprint=f"policy::{lineage_key}",
        normative_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=dependency_kind,
                    key=dependency_key,
                    label="lifecycle fixture dependency",
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    service.register_decision_packet(
        packet_ref=packet_ref,
        envelope=envelope,
        baseline=baseline,
    )
    return packet_ref


@pytest.fixture(autouse=True)
def _reset_connector_registry():
    """Reset ConnectorRegistry singleton before each test to avoid bootstrap hang."""
    ConnectorRegistry.reset_instance()
    # Create instance without bootstrap (no component discovery)
    ConnectorRegistry.get_instance(bootstrap=False)
    yield
    ConnectorRegistry.reset_instance()


class TestLaunchRun:
    def test_launch_workflow_run_accepted(self, runtime_api_env):
        client = runtime_api_env["client"]
        # Use an existing artifact from the fixture as data_snapshot_ref
        artifact_id = runtime_api_env["root_artifact_id"]
        resp = client.post(
            "/api/v1/control/runs",
            json={
                "mode": "workflow",
                "data_source": {"data_snapshot_ref": artifact_id},
                "checkpoint_policy": "strict",
                "params": {"seed": 42},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["run_id"].startswith("R_")
        assert body["job_id"]
        assert body["effective_execution_profile"] == "dev"
        assert "meta" in body
        assert body["meta"]["request_id"]

    def test_launch_run_with_trinity_bundle(self, runtime_api_env):
        client = runtime_api_env["client"]
        artifact_id = runtime_api_env["root_artifact_id"]
        resp = client.post(
            "/api/v1/control/runs",
            json={
                "data_source": {"input_bindings_ref": artifact_id},
                "trinity_bundle_ref": artifact_id,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["job_id"]

    def test_launch_run_missing_data_source_returns_400(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs",
            json={
                "data_source": {},
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "missing_data_source"

    def test_launch_run_invalid_body_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs",
            json={"invalid_field": "value"},
        )
        assert resp.status_code == 422


class TestCapabilities:
    def test_get_control_capabilities_returns_manifest(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["shell_flavor"] == "atlas"
        assert body["default_locale"] == "en"
        assert body["default_execution_profile"] == "dev"
        assert body["worker_backend"] == "embedded"
        assert body["state_store_backend"] == "sqlite"
        assert "features" in body
        assert isinstance(body["features"], list)
        assert body["features"] == []
        assert body["constraints"]["max_parallel_models"] == 16
        assert body["constraints"]["durable_control_profiles"] == [
            "research",
            "governed",
            "production",
        ]

    def test_get_control_capabilities_reports_selected_production_data_manifest(
        self,
        runtime_api_env,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        production_data_root = tmp_path / "production_data"
        datasets_dir = production_data_root / "datasets_full_20990101"
        datasets_dir.mkdir(parents=True)
        manifest = {
            "schema_version": "1.0",
            "bundles": {
                "datasets": {
                    "version_id": "datasets_full_20990101",
                    "readiness": "ready",
                    "path": "datasets_full_20990101",
                }
            },
        }
        (production_data_root / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        monkeypatch.setenv("POLISYOS_PRODUCTION_DATA_ROOT", str(production_data_root))

        response = runtime_api_env["client"].get("/api/v1/control/capabilities")

        assert response.status_code == 200
        production_data = response.json()["constraints"]["production_data"]
        assert production_data["root"] == str(production_data_root)
        assert production_data["manifest_sha256"].startswith("sha256:")
        assert production_data["bundles"]["datasets"]["version_id"] == "datasets_full_20990101"

    def test_get_control_workers_returns_worker_leases(self, runtime_api_env):
        client = runtime_api_env["client"]
        response = client.get("/api/v1/control/workers")
        assert response.status_code == 200
        body = response.json()
        assert body["active_only"] is True
        assert len(body["workers"]) >= 1
        assert body["workers"][0]["worker_id"]
        assert body["workers"][0]["state"] in {"idle", "running", "stopped"}

    def test_get_control_outbox_returns_events(self, runtime_api_env):
        service = runtime_api_env["app"].state._control_service
        record = service._control_store.enqueue_outbox_event(
            topic="control.fixture",
            event_key="fixture-event",
            payload={"fixture": True},
        )

        client = runtime_api_env["client"]
        response = client.get("/api/v1/control/outbox?state=pending&limit=10")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "pending"
        assert body["limit"] == 10
        assert any(item["event_id"] == record.event_id for item in body["events"])

    def test_get_control_job_status_returns_record(self, runtime_api_env):
        client = runtime_api_env["client"]
        launch = client.post(
            "/api/v1/control/runs",
            json={
                "mode": "workflow",
                "data_source": {"data_snapshot_ref": runtime_api_env["root_artifact_id"]},
            },
        )
        assert launch.status_code == 200
        job_id = launch.json()["job_id"]
        status = client.get(f"/api/v1/control/jobs/{job_id}")
        assert status.status_code == 200
        body = status.json()
        assert body["job_id"] == job_id
        assert body["kind"] == "workflow_run"
        assert body["effective_execution_profile"] == "dev"

    def test_get_control_job_status_returns_quality_scorecard(self, runtime_api_env):
        service = runtime_api_env["app"].state._control_service
        service._worker.stop()
        store = service._control_store
        store.create_job(
            job_id="job_quality_api_fixture",
            kind="natural_language_run",
            run_id="R_quality_api_fixture",
            pipeline_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="tester",
        )
        store.complete_job(
            job_id="job_quality_api_fixture",
            progress={
                "quality_scorecard": {
                    "execution_status": "completed",
                    "quality_status": "fail",
                    "quality_gates": [
                        {
                            "name": "policy_grounding_matrix_present",
                            "code": "major_claim_missing_grounding",
                            "status": "fail",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Unsupported policy claim.",
                            "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                            "next_action": "Map final policy claims to evidence refs.",
                            "blocking": True,
                        }
                    ],
                    "blocking_quality_failures": [
                        {
                            "gate": "policy_grounding_matrix_present",
                            "code": "major_claim_missing_grounding",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Unsupported policy claim.",
                            "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                            "next_action": "Map final policy claims to evidence refs.",
                        }
                    ],
                }
            },
        )

        response = runtime_api_env["client"].get("/api/v1/control/jobs/job_quality_api_fixture")

        assert response.status_code == 200
        body = response.json()
        assert body["execution_status"] == "completed"
        assert body["quality_status"] == "fail"
        assert body["quality_gates"][0]["name"] == "policy_grounding_matrix_present"
        assert body["quality_gates"][0]["code"] == "major_claim_missing_grounding"
        assert body["quality_gates"][0]["phase"] == "policy_grounding"
        assert body["blocking_quality_failures"][0]["gate"] == ("policy_grounding_matrix_present")
        assert body["blocking_quality_failures"][0]["code"] == ("major_claim_missing_grounding")
        assert body["blocking_quality_failures"][0]["phase"] == "policy_grounding"

    def test_get_control_job_status_labels_dashboard_projection_authority_gaps(
        self,
        runtime_api_env,
    ):
        service = runtime_api_env["app"].state._control_service
        service._worker.stop()
        store = service._control_store
        next_command = "uv run pytest tests/unit/runtime/http/test_control_api.py -q"
        store.create_job(
            job_id="job_projection_gap_fixture",
            kind="natural_language_run",
            run_id="R_projection_gap_fixture",
            pipeline_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="tester",
        )
        store.complete_job(
            job_id="job_projection_gap_fixture",
            progress={
                "quality_scorecard": {
                    "execution_status": "completed",
                    "quality_status": "fail",
                    "approval_state": "approval_ready",
                    "approval_eligibility": {
                        "eligible": True,
                        "state": "approval_ready",
                    },
                    "quality_gates": [
                        {
                            "name": "policy_grounding_matrix_present",
                            "code": "major_claim_missing_grounding",
                            "status": "fail",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Unsupported policy claim.",
                            "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                            "next_action": "Map final policy claims to evidence refs.",
                            "next_diagnostic_command": next_command,
                            "blocking": True,
                        }
                    ],
                    "blocking_quality_failures": [
                        {
                            "gate": "policy_grounding_matrix_present",
                            "code": "major_claim_missing_grounding",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Unsupported policy claim.",
                            "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                            "next_action": "Map final policy claims to evidence refs.",
                            "next_diagnostic_command": next_command,
                        }
                    ],
                }
            },
        )

        response = runtime_api_env["client"].get("/api/v1/control/jobs/job_projection_gap_fixture")

        assert response.status_code == 200
        body = response.json()
        assert body["projection_source"] == {
            "source_surface": "runtime.control_job",
            "source_detail": "control_store_progress",
            "authority_level": "projection_only",
            "projection_policy": "projection_only",
        }
        assert body["runtime_state"] == "completed"
        assert body["authoritative_scorecard_ref"] is None
        assert body["approval_projection"]["eligible"] is False
        assert body["approval_projection"]["state"] == "quality_failed"
        assert body["unresolved_authority_gaps"][0]["code"] == ("major_claim_missing_grounding")
        assert body["unresolved_authority_gaps"][0]["next_diagnostic_command"] == (next_command)
        assert next_command in body["next_diagnostic_commands"]

    def test_api_projection_source_truth_conflict_blocks_approval_ready_shape(
        self,
        runtime_api_env,
    ):
        service = runtime_api_env["app"].state._control_service
        service._worker.stop()
        store = service._control_store
        scorecard_ref = "sha256:" + "9" * 64
        store.create_job(
            job_id="job_api_projection_conflict_fixture",
            kind="natural_language_run",
            run_id="R_api_projection_conflict_fixture",
            pipeline_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="tester",
        )
        store.complete_job(
            job_id="job_api_projection_conflict_fixture",
            progress={
                "quality_scorecard": {
                    "execution_status": "completed",
                    "quality_status": "pass",
                    "approval_state": "approval_ready",
                    "quality_scorecard_ref": scorecard_ref,
                    "quality_gates": [
                        {
                            "name": "policy_grounding_matrix_present",
                            "code": "major_claim_missing_grounding",
                            "status": "fail",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Unsupported policy claim.",
                            "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                            "next_action": "Map final policy claims to evidence refs.",
                            "blocking": True,
                        }
                    ],
                    "blocking_quality_failures": [
                        {
                            "gate": "policy_grounding_matrix_present",
                            "code": "major_claim_missing_grounding",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Unsupported policy claim.",
                            "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                            "next_action": "Map final policy claims to evidence refs.",
                        }
                    ],
                }
            },
        )

        response = runtime_api_env["client"].get(
            "/api/v1/control/jobs/job_api_projection_conflict_fixture"
        )

        assert response.status_code == 200
        body = response.json()
        gap_codes = {gap["code"] for gap in body["unresolved_authority_gaps"]}
        assert body["authoritative_scorecard_ref"] == scorecard_ref
        assert "hds_source_truth_conflict" in gap_codes
        assert body["approval_projection"]["eligible"] is False
        assert body["approval_projection"]["state"] == "quality_failed"
        assert body["operator_diagnostic"]["first_blocking_cause"] == ("hds_source_truth_conflict")
        assert body["operator_diagnostic"]["projection_source"] == ("runtime_api_projection")

    def test_failed_serious_run_exposes_operator_diagnostic_on_api_projections(
        self,
        runtime_api_env,
    ):
        run_id = runtime_api_env["core_run_id"]
        service = runtime_api_env["app"].state._control_service
        service._worker.stop()
        store = service._control_store
        next_command = "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q"
        store.create_job(
            job_id="job_operator_projection_fixture",
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="tester",
        )
        store.complete_job(
            job_id="job_operator_projection_fixture",
            progress={
                "quality_scorecard": {
                    "execution_status": "completed",
                    "quality_status": "fail",
                    "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
                    "evidence_refs": {
                        "quality_scorecard": "quality_evidence/quality_scorecard.json",
                        "policy_grounding_matrix": (
                            "quality_evidence/policy_grounding_matrix.json"
                        ),
                    },
                    "quality_gates": [
                        {
                            "name": "policy_grounding_matrix_present",
                            "code": "policy_grounding_matrix_ref_missing",
                            "status": "fail",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Policy grounding matrix is missing.",
                            "evidence_ref": ("quality_evidence/policy_grounding_matrix.json"),
                            "next_action": "Attach the policy grounding matrix ref.",
                            "next_diagnostic_command": next_command,
                            "owner": "team-policy-semantics",
                            "upstream_missing_input": "policy_grounding_matrix_ref",
                            "downstream_impact": (
                                "Readiness and approval projections remain closed."
                            ),
                            "blocker_overridable": False,
                            "blocking": True,
                        }
                    ],
                    "blocking_quality_failures": [
                        {
                            "gate": "policy_grounding_matrix_present",
                            "code": "policy_grounding_matrix_ref_missing",
                            "layer": "scientist_policy_artifacts",
                            "phase": "policy_grounding",
                            "message": "Policy grounding matrix is missing.",
                            "evidence_ref": ("quality_evidence/policy_grounding_matrix.json"),
                            "next_action": "Attach the policy grounding matrix ref.",
                            "next_diagnostic_command": next_command,
                            "owner": "team-policy-semantics",
                            "upstream_missing_input": "policy_grounding_matrix_ref",
                            "downstream_impact": (
                                "Readiness and approval projections remain closed."
                            ),
                            "blocker_overridable": False,
                        }
                    ],
                }
            },
        )

        control_response = runtime_api_env["client"].get(
            "/api/v1/control/jobs/job_operator_projection_fixture"
        )
        run_response = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")

        assert control_response.status_code == 200
        assert run_response.status_code == 200
        control_diagnostic = control_response.json()["operator_diagnostic"]
        run_diagnostic = run_response.json()["run"]["operator_diagnostic"]
        for diagnostic in (control_diagnostic, run_diagnostic):
            assert diagnostic["owner"] == "team-policy-semantics"
            assert diagnostic["phase"] == "policy_grounding"
            assert diagnostic["first_blocking_cause"] == "policy_grounding_matrix_ref_missing"
            assert diagnostic["upstream_missing_input"] == "policy_grounding_matrix_ref"
            assert (
                diagnostic["downstream_impact"]
                == "Readiness and approval projections remain closed."
            )
            assert diagnostic["projection_source"] == "runtime_quality_scorecard"
            assert diagnostic["blocker_overridable"] is False
            assert diagnostic["authority_refs"]["quality_scorecard"] == (
                "quality_evidence/quality_scorecard.json"
            )
            assert "quality_evidence/policy_grounding_matrix.json" in diagnostic["evidence_refs"]
            assert diagnostic["next_diagnostic_command"] == next_command


class TestProductionApproval:
    def test_runtime_context_store_enforces_tenant_ownership_index(
        self,
        runtime_api_env,
    ):
        tenant_b_store = FileSystemCAS(runtime_api_env["cas_root"])
        tenant_b_ref = tenant_b_store.put_json(
            {"tenant": "b-only"},
            ArtifactWriteOptions(
                kind="test.tenant_b_only",
                media_type="application/json",
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        tenant_b_store.record_artifact_owner(
            tenant_b_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=runtime_api_env["cell_a"],
            writer="test",
        )
        runtime_store = runtime_api_env["app"].state.runtime_api_ctx.store

        with (
            tenant_scope(
                None,
                tenant_id=runtime_api_env["tenant_a"],
                cell_id=runtime_api_env["cell_a"],
            ),
            pytest.raises(ArtifactOwnershipError),
        ):
            runtime_store.get_bytes(tenant_b_ref.artifact_id)

        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=runtime_api_env["cell_a"],
        ):
            assert json.loads(runtime_store.get_bytes(tenant_b_ref.artifact_id)) == {
                "tenant": "b-only"
            }

    def test_production_approval_blocks_missing_decision_producer(
        self,
        runtime_api_env,
        tmp_path,
    ):
        client, cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id="production-approval-persisted-scorecard",
        )
        run_id = runtime_api_env["core_run_id"]
        evidence_bundle = tmp_path / "quality-evidence"
        scorecard_ref = _persist_scorecard(
            runtime_api_env,
            _production_approval_scorecard(
                run_id=run_id,
                evidence_bundle_path=str(evidence_bundle),
            ),
        )
        _align_secure_artifact_ownership(
            runtime_api_env,
            client=client,
            cell_id=cell_id,
            artifact_ids=(scorecard_ref,),
        )
        with client:
            response = client.post(
                f"/api/v1/runs/{run_id}/production-approval",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "quality_scorecard_ref": scorecard_ref,
                    "production_basis_ref": _sha("b"),
                    "production_basis_digest": _sha("b"),
                    "human_decision_record_ref": _sha("c"),
                    "human_decision_record_digest": _sha("c"),
                },
            )

        assert response.status_code == 503
        body = response.json()
        assert body["code"] == "DS9-DECISION-PRODUCER-MISSING"
        assert not (evidence_bundle / "production_approval_packet.json").exists()

        store = FileSystemCAS(runtime_api_env["cas_root"])
        assert all(
            store.get_manifest(artifact_id).kind != "runtime.production_approval_packet"
            for artifact_id in store.iter_artifact_ids()
        )

    def test_persisted_control_progress_does_not_bypass_producer_trust(
        self,
        runtime_api_env,
        tmp_path,
    ):
        client, cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id="production-approval-control-progress",
        )
        run_id = runtime_api_env["core_run_id"]
        evidence_bundle = tmp_path / "quality-evidence-from-progress"
        scorecard = _production_approval_scorecard(
            run_id=run_id,
            evidence_bundle_path=str(evidence_bundle),
        )
        scorecard_ref = _persist_scorecard(runtime_api_env, scorecard)
        scorecard_with_ref = {
            **scorecard,
            "quality_scorecard_ref": scorecard_ref,
            "evidence_refs": {
                **dict(scorecard["evidence_refs"]),
                "quality_scorecard": scorecard_ref,
            },
        }
        _align_secure_artifact_ownership(
            runtime_api_env,
            client=client,
            cell_id=cell_id,
            artifact_ids=(scorecard_ref,),
        )
        with client:
            service = client.app.state._control_service
            assert service is not None
            if service._worker is not None:
                service._worker.stop()
            service._control_store.create_job(
                job_id="job_production_approval_progress",
                kind="natural_language_run",
                run_id=run_id,
                pipeline_id=None,
                requested_execution_profile="production",
                effective_execution_profile="production",
                policy_flags={},
                capability_manifest_ref=None,
                payload_ref=None,
                submitted_by="tester",
            )
            service._control_store.complete_job(
                job_id="job_production_approval_progress",
                progress={"quality_scorecard": scorecard_with_ref},
            )
            response = client.post(
                f"/api/v1/runs/{run_id}/production-approval",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "production_basis_ref": _sha("b"),
                    "production_basis_digest": _sha("b"),
                    "human_decision_record_ref": _sha("c"),
                    "human_decision_record_digest": _sha("c"),
                },
            )
            assert response.status_code == 503
            body = response.json()
            assert body["code"] == "DS9-DECISION-PRODUCER-MISSING"
            record = service._control_store.get_job("job_production_approval_progress")
            assert record is not None
            progress_scorecard = record.progress["quality_scorecard"]
            assert progress_scorecard["quality_scorecard_ref"] == scorecard_ref
            assert "approval_packet_ref" not in progress_scorecard
            assert "approval_packet_ref" not in progress_scorecard["evidence_refs"]
            assert "approval_decision" not in progress_scorecard

    def test_run_production_approval_rejects_unpersisted_inline_scorecard(
        self,
        runtime_api_env,
        tmp_path,
    ):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id="production-approval-inline-scorecard",
        )
        run_id = runtime_api_env["core_run_id"]
        with client:
            response = client.post(
                f"/api/v1/runs/{run_id}/production-approval",
                headers=headers,
                json={
                    "quality_scorecard": _production_approval_scorecard(
                        run_id=run_id,
                        evidence_bundle_path=str(tmp_path / "quality-evidence"),
                    )
                },
            )

        assert response.status_code == 403, response.text
        assert response.json()["code"] == "authorization_binding_scorecard_tenant_mismatch"

    def test_run_production_approval_rejects_incomplete_override(self, runtime_api_env, tmp_path):
        client, cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id="production-approval-incomplete-override",
        )
        run_id = runtime_api_env["core_run_id"]
        scorecard_ref = _persist_scorecard(
            runtime_api_env,
            _production_approval_scorecard(
                run_id=run_id,
                evidence_bundle_path=str(tmp_path / "quality-evidence"),
                performance_status="over_budget",
            ),
        )
        _align_secure_artifact_ownership(
            runtime_api_env,
            client=client,
            cell_id=cell_id,
            artifact_ids=(scorecard_ref,),
        )
        with client:
            response = client.post(
                f"/api/v1/runs/{run_id}/production-approval",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "quality_scorecard_ref": scorecard_ref,
                    "production_basis_ref": _sha("b"),
                    "production_basis_digest": _sha("b"),
                    "human_decision_record_ref": _sha("c"),
                    "human_decision_record_digest": _sha("c"),
                    "override": {
                        "reviewer_identity": "user-1",
                    },
                },
            )

        assert response.status_code == 422


class TestDecisionValidity:
    def test_get_run_decision_validity_returns_lifecycle_summary(self, runtime_api_env):
        client = runtime_api_env["client"]
        response = client.get(
            f"/api/v1/control/runs/{runtime_api_env['core_run_id']}/decision-validity"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == runtime_api_env["core_run_id"]
        assert (
            body["decision_packet_ref"]["artifact_id"]
            == runtime_api_env["decision_packet_artifact_id"]
        )
        assert body["status"] == "warning"
        assert body["decision_lineage_key"] == runtime_api_env["decision_packet_artifact_id"]
        assert body["evaluation_ref"]["kind"] == "scientist.decision_validity_evaluation"
        assert body["lifecycle"]["events"] == []
        assert body["lifecycle"]["transitions"] == []
        assert body["lifecycle"]["scheduled_jobs"] == []
        assert body["lifecycle"]["reissue_candidates"] == []

    def test_get_packet_decision_validity_exposes_pending_reviews(self, runtime_api_env):
        service = DecisionValidityService(FileSystemCAS(runtime_api_env["cas_root"]))
        service.mark_packet_trigger(
            packet_ref=runtime_api_env["decision_packet_artifact_id"],
            trigger=DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="target_applicability_changed",
            ),
        )

        client = runtime_api_env["client"]
        response = client.get(
            "/api/v1/control/decision-packets/"
            f"{runtime_api_env['decision_packet_artifact_id']}/decision-validity"
        )
        assert response.status_code == 200
        body = response.json()
        assert (
            body["decision_packet_ref"]["artifact_id"]
            == runtime_api_env["decision_packet_artifact_id"]
        )
        assert body["status"] == "requires_human_review"
        assert body["review_required"] is True
        assert body["lifecycle"]["events"][0]["trigger_type"] == "context_profile_drift"
        assert body["lifecycle"]["pending_reviews"][0]["reason"] == "target_applicability_changed"
        assert body["lifecycle"]["transitions"][-1]["current_status"] == "requires_human_review"

    def test_decision_validity_exports_bind_shared_replay_contract(
        self,
        runtime_api_env,
    ):
        client = runtime_api_env["client"]
        run_id = runtime_api_env["core_run_id"]
        path = f"/api/v1/control/runs/{run_id}/decision-validity"

        first = client.get(path)

        assert first.status_code == 200
        projection_hash = first.headers["x-policyos-export-projection-hash"]
        assert projection_hash.startswith("sha256:")
        assert first.headers["x-policyos-export-stable-address"] == path
        assert first.headers["x-policyos-export-as-of"]

        replay = client.get(path, params={"export_projection_hash": projection_hash})
        mismatch = client.get(
            path,
            params={"export_projection_hash": "sha256:" + "0" * 64},
        )

        assert replay.status_code == 200
        assert replay.headers["x-policyos-export-projection-hash"] == projection_hash
        assert mismatch.status_code == 409
        assert mismatch.json()["code"] == "export_replay_pin_mismatch"

    def test_source_invalidation_marks_published_decision_stale_and_exposes_lifecycle_status(
        self,
        runtime_api_env,
    ):
        client, cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id="decision-validity-source-invalidation",
        )
        packet_ref = _register_lifecycle_decision_packet(
            runtime_api_env,
            dependency_kind=DecisionDependencyKind.SOURCE,
            dependency_key="source::gazette::2026",
            lineage_key="lineage::source-invalidation",
        )
        _align_secure_artifact_ownership(
            runtime_api_env,
            client=client,
            cell_id=cell_id,
            artifact_ids=(packet_ref,),
        )

        with client:
            response = client.post(
                "/api/v1/control/decision-validity/events",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "trigger_type": "source_invalidation",
                    "status": "stale",
                    "reason": "gazette_source_superseded",
                    "dependency_keys": ["source::gazette::2026"],
                    "source_ref": "source://gazette/2026",
                    "payload": {
                        "invalidation_domain": "source",
                        "new_evidence_refs": [_sha("c")],
                        "change_reason": "official gazette issued a corrected publication",
                    },
                },
            )

            assert response.status_code == 200
            assert response.json()["affected_statuses"] == {"stale": 1}

            summary = client.get(
                f"/api/v1/control/decision-packets/{packet_ref}/decision-validity",
                headers=headers,
            )

        assert summary.status_code == 200
        body = summary.json()
        assert body["status"] == "stale"
        assert body["lifecycle_status"] == "stale"
        assert body["recommended_action"] == "refresh_decision"
        assert body["lifecycle"]["events"][0]["trigger_type"] == "source_invalidation"
        assert body["lifecycle"]["transitions"][-1]["current_status"] == "stale"

    def test_norm_invalidation_can_withdraw_published_decision(self, runtime_api_env):
        client, cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id="decision-validity-norm-invalidation",
        )
        packet_ref = _register_lifecycle_decision_packet(
            runtime_api_env,
            dependency_kind=DecisionDependencyKind.NORM_PACK,
            dependency_key="norm::msme-tax::2026",
            lineage_key="lineage::norm-withdrawal",
        )
        _align_secure_artifact_ownership(
            runtime_api_env,
            client=client,
            cell_id=cell_id,
            artifact_ids=(packet_ref,),
        )

        with client:
            response = client.post(
                "/api/v1/control/decision-validity/events",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "trigger_type": "norm_invalidation",
                    "status": "withdrawn",
                    "reason": "enabling_norm_withdrawn",
                    "dependency_keys": ["norm::msme-tax::2026"],
                    "source_ref": "law://ua/msme-tax/2026/withdrawal",
                    "payload": {
                        "invalidation_domain": "norm",
                        "withdrawal_record_ref": _sha("d"),
                    },
                },
            )

            assert response.status_code == 200
            assert response.json()["affected_statuses"] == {"withdrawn": 1}

            summary = client.get(
                f"/api/v1/control/decision-packets/{packet_ref}/decision-validity",
                headers=headers,
            )

        assert summary.status_code == 200
        body = summary.json()
        assert body["status"] == "withdrawn"
        assert body["lifecycle_status"] == "withdrawn"
        assert body["recommended_action"] == "record_withdrawal"
        assert body["review_required"] is True
        assert body["lifecycle"]["transitions"][-1]["current_status"] == "withdrawn"

    @pytest.mark.parametrize(
        (
            "dependency_kind",
            "dependency_key",
            "trigger_type",
            "status",
            "expected_action",
        ),
        [
            (
                DecisionDependencyKind.DATA_SNAPSHOT,
                "data::msme-panel::2026",
                "data_invalidation",
                "stale",
                "refresh_decision",
            ),
            (
                DecisionDependencyKind.QUALITY_REPORT,
                "metric::msme_survival_rate",
                "metric_invalidation",
                "review_required",
                "human_review",
            ),
            (
                DecisionDependencyKind.ECONOMETRIC_EVIDENCE,
                "model::survival-effect-v2",
                "model_invalidation",
                "superseded",
                "review_superseded",
            ),
            (
                DecisionDependencyKind.NORMATIVE_ARBITRATION,
                "conflict::eligibility-budget-2026",
                "conflict_invalidation",
                "review_required",
                "human_review",
            ),
        ],
    )
    def test_invalidation_domains_update_lifecycle_status(
        self,
        runtime_api_env,
        dependency_kind,
        dependency_key,
        trigger_type,
        status,
        expected_action,
    ):
        client, cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ADMIN,
            case_id=f"decision-validity-{trigger_type}",
        )
        packet_ref = _register_lifecycle_decision_packet(
            runtime_api_env,
            dependency_kind=dependency_kind,
            dependency_key=dependency_key,
            lineage_key=f"lineage::{trigger_type}",
        )
        _align_secure_artifact_ownership(
            runtime_api_env,
            client=client,
            cell_id=cell_id,
            artifact_ids=(packet_ref,),
        )

        with client:
            response = client.post(
                "/api/v1/control/decision-validity/events",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "trigger_type": trigger_type,
                    "status": status,
                    "reason": f"{trigger_type}_fixture",
                    "dependency_keys": [dependency_key],
                    "source_ref": f"decision-validity://{trigger_type}",
                    "payload": {
                        "invalidation_domain": trigger_type.removesuffix("_invalidation"),
                        "new_evidence_refs": [_sha("6")],
                        "change_reason": f"{trigger_type} changed the decision basis",
                    },
                },
            )

            assert response.status_code == 200
            assert response.json()["affected_statuses"] == {status: 1}

            summary = client.get(
                f"/api/v1/control/decision-packets/{packet_ref}/decision-validity",
                headers=headers,
            )

        assert summary.status_code == 200
        body = summary.json()
        assert body["status"] == status
        assert body["lifecycle_status"] == status
        assert body["recommended_action"] == expected_action
        assert body["lifecycle"]["events"][0]["trigger_type"] == trigger_type
        assert body["lifecycle"]["transitions"][-1]["current_status"] == status

    def test_reissue_packet_includes_scorecard_new_evidence_and_change_reason(
        self,
        runtime_api_env,
        tmp_path,
    ):
        original_scorecard_ref = _persist_scorecard(
            runtime_api_env,
            _production_approval_scorecard(
                run_id=runtime_api_env["core_run_id"],
                evidence_bundle_path=str(tmp_path / "quality-evidence"),
            ),
        )
        packet_ref = _artifact_ref(
            runtime_api_env["decision_packet_artifact_id"],
            kind="scientist.decision_packet",
        )
        ledger_ref = _artifact_ref(_sha("e"), kind="scientist.claim_ledger")
        monitor_event_ref = _artifact_ref(_sha("f"), kind="scientist.governance_monitor_event")
        new_packet_ref = _artifact_ref(_sha("1"), kind="scientist.decision_packet")
        new_ledger_ref = _artifact_ref(_sha("2"), kind="scientist.claim_ledger")
        evidence_refs = [
            _artifact_ref(_sha("3"), kind="fabric.evidence_bundle"),
            _artifact_ref(_sha("4"), kind="lex.normpack"),
        ]

        packet = build_reissue_packet(
            original_decision_packet_ref=packet_ref,
            original_claim_ledger_ref=ledger_ref,
            status=ContinuousDecisionValidityStatus.REISSUED,
            reason="published decision reissued after source correction",
            monitor_event_refs=[monitor_event_ref],
            new_decision_packet_ref=new_packet_ref,
            new_claim_ledger_ref=new_ledger_ref,
            original_scorecard_ref=_artifact_ref(
                original_scorecard_ref,
                kind="runtime.quality_scorecard",
            ),
            new_evidence_refs=evidence_refs,
            change_reason="official gazette correction changed the governing evidence",
        )

        assert str(packet.original_scorecard_ref.artifact_id) == original_scorecard_ref
        assert packet.new_evidence_refs == evidence_refs
        assert packet.change_reason == (
            "official gazette correction changed the governing evidence"
        )


class TestLaunchNlRun:
    def test_launch_nl_run_without_model_is_typed_refusal(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Analyze minimum wage impact on small businesses",
                "domain_hint": "fiscal",
                "max_iterations": 2,
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "llm_model_unconfigured"

    def test_launch_nl_run_with_llm_model(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Study healthcare policy effects",
                "llm_model": "claude-sonnet-4-5-20250929",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["job_id"]
        assert "claude-sonnet" in body["message"]

    def test_launch_nl_run_with_llm_models(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Compare multiple model variants on the same task",
                "llm_models": ["gpt-5-mini", "claude-sonnet-4-5-20250929"],
                "max_parallel_models": 2,
                "run_budget_usd": 2.0,
                "per_model_budget_usd": 1.0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["job_id"]
        assert "model variants" in body["message"]

    def test_launch_nl_run_accepts_execution_plan_payload(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Plan-first NL cycle",
                "llm_model": "simulated-qwen",
                "execution_plan": {
                    "plan_id": "plan_contract_test",
                    "schema_version": "1.0",
                    "data_needs": [{"metric": "macro.gdp"}],
                    "method_dag": [],
                    "method_edges": [],
                    "params": {},
                    "budgets": {"max_iterations": 2},
                    "stop_criteria": {
                        "min_delta_improvement": 0.01,
                        "max_no_delta_iterations": 1,
                    },
                    "governance_constraints": [],
                    "expected_outputs": [],
                },
                "stop_criteria": {"max_no_delta_iterations": 1},
                "governance_constraints": [{"constraint_id": "g1", "kind": "policy"}],
                "expected_outputs": [{"output_id": "o1", "metric_id": "macro.gdp"}],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["job_id"]

    def test_launch_nl_run_invalid_parallel_models_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Invalid max_parallel_models value",
                "llm_models": ["gpt-5-mini", "claude-sonnet-4-5-20250929"],
                "max_parallel_models": 0,
            },
        )
        assert resp.status_code == 422

    def test_launch_nl_run_empty_request_returns_422(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/runs/nl",
            json={"request": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_launch_nl_run_research_red_preflight_creates_short_failed_job(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
        execute_called = False

        async def _red_preflight(**_kwargs):
            return ProviderPreflightReport(
                status="failed",
                provider="gonka_proxy",
                base_url="https://proxy.gonka.gg/v1",
                models=["missing-model"],
                checks=[],
                retryable=False,
                failure={
                    "code": "llm_provider_preflight_failed",
                    "layer": "llm_gateway",
                    "phase": "provider_preflight",
                    "message": "missing-model not returned by /v1/models",
                    "retryable": False,
                    "model": "missing-model",
                    "provider": "gonka_proxy",
                    "next_action": "Check provider credentials and model configuration.",
                },
            )

        def _execute(*_args, **_kwargs):
            nonlocal execute_called
            execute_called = True

        monkeypatch.setattr(
            "polisyos.runtime.http.services.control.run_lifecycle.run_provider_preflight",
            _red_preflight,
        )
        monkeypatch.setattr(ControlPlaneService, "_execute_nl_pipeline", _execute)

        registry = type(
            "_Registry",
            (),
            {
                "query_entries": lambda self, *args, **kwargs: [],
                "get": lambda self, profile_id: None,
                "list_all": lambda self: [],
                "list_by_family": lambda self, connector_family: [],
            },
        )()
        service = ControlPlaneService(
            cas_root=tmp_path / "cas",
            core_runs_root=tmp_path / "runs",
            policy_resolver=RuntimeExecutionPolicyResolver(
                default_profile="dev",
                worker_backend="external",
                state_store_backend="sqlite",
                sqlite_path=str(tmp_path / "control.sqlite3"),
                postgres_dsn=None,
            ),
            registry_providers=ControlRegistryProviders(
                connectors=registry,
                source_profiles=registry,
                binding_profiles=registry,
                model_profiles=registry,
            ),
        )
        try:
            response = await service.launch_nl_run(
                NaturalLanguageRunRequest(
                    request="Evaluate Ukraine MSME support.",
                    execution_profile="research",
                    llm_models=["missing-model"],
                    policy_flags={"allow_mock_fallback": False},
                ),
                request_id="req-red-preflight",
            )
            record = service._control_store.get_job(response.job_id)
        finally:
            service.close()

        assert response.status == "rejected"
        assert execute_called is False
        assert record is not None
        assert record.state == "failed"
        assert record.progress["phase"] == "provider_preflight"
        assert record.progress["failure"]["code"] == "llm_provider_preflight_failed"
        assert record.to_response().failure is not None


class TestDataIngestion:
    def test_ingest_data_accepted(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-accepted",
        )
        IngestionResult(datasets_fetched=1)
        with (
            client,
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [
                        {
                            "connector_id": "worldbank.wdi",
                            "dataset_id": "NY.GDP.MKTP.CD",
                            "filters": {"country": ["USA"]},
                        }
                    ],
                    "source": "test",
                    "license_name": "open",
                },
            )
        assert resp.status_code == 200

    def test_ingest_data_empty_datasets_returns_422(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-empty-datasets",
        )
        with client:
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=headers,
                json={"datasets": []},
            )
        assert resp.status_code == 400
        assert resp.json()["code"] == "authorization_binding_selector_alternative_required"


class TestConnectorsList:
    def test_list_connectors_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        assert resp.status_code == 200
        body = resp.json()
        assert "connectors" in body
        assert isinstance(body["connectors"], list)
        assert "meta" in body


class TestConnectorsAvailableProfiles:
    def test_connectors_include_available_profiles(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/connectors")
        assert resp.status_code == 200
        body = resp.json()
        for c in body["connectors"]:
            assert "available_profiles" in c
            assert isinstance(c["available_profiles"], list)


class TestSourceProfiles:
    def test_list_profiles_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert isinstance(body["profiles"], list)
        assert "meta" in body

    def test_list_profiles_has_builtin(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        profile_ids = [p["profile_id"] for p in body["profiles"]]
        assert "worldbank_wdi" in profile_ids
        assert "ecb_sdmx" in profile_ids

    def test_profile_has_expected_fields(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/profiles")
        body = resp.json()
        for p in body["profiles"]:
            assert "profile_id" in p
            assert "display_name" in p
            assert "connector_family" in p
            assert "base_url" in p
            assert "connector_available" in p

    def test_ingest_with_connection_profile(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-connection-profile",
        )
        with (
            client,
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [
                        {
                            "connector_id": "worldbank.wdi",
                            "dataset_id": "NY.GDP.MKTP.CD",
                        }
                    ],
                    "connection_profile": "worldbank_wdi",
                    "produce_data_snapshot": True,
                },
            )
        assert resp.status_code == 200

    def test_ingest_response_has_new_fields(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-response-fields",
        )
        with (
            client,
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [
                        {
                            "connector_id": "worldbank.wdi",
                            "dataset_id": "NY.GDP.MKTP.CD",
                        }
                    ],
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        # New fields should be present regardless of success/failure
        assert "data_snapshot_ref" in body
        assert "warnings" in body


class TestLlmProfiles:
    def test_list_llm_profiles_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/llm/profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert isinstance(body["profiles"], list)
        assert "meta" in body

    def test_list_llm_profiles_has_builtin(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/llm/profiles")
        body = resp.json()
        profile_ids = [p["profile_id"] for p in body["profiles"]]
        assert "gpt5_mini_gateway" in profile_ids


class TestCacheStatus:
    def test_cache_status_returns_empty(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/cache")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_entries"] == 0
        assert "entries" in body
        assert "meta" in body


class TestBindingProfiles:
    def test_list_binding_profiles_returns_list(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/binding-profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert isinstance(body["profiles"], list)
        assert "meta" in body

    def test_list_binding_profiles_has_builtins(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/binding-profiles")
        body = resp.json()
        profile_ids = [p["profile_id"] for p in body["profiles"]]
        assert "ts_single_indicator" in profile_ids
        assert "ts_multi_indicator" in profile_ids
        assert "ts_exchange_rate" in profile_ids

    def test_binding_profile_has_expected_fields(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/binding-profiles")
        body = resp.json()
        for p in body["profiles"]:
            assert "profile_id" in p
            assert "display_name" in p
            assert "schema_family" in p
            assert "rule_count" in p
            assert isinstance(p["rule_count"], int)
            assert p["rule_count"] >= 0


class TestDataRetrievalControl:
    def test_data_resolve_returns_payload(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/resolve",
            json={
                "data_needs": [
                    {
                        "metric": "us.macro.gdp_nominal",
                        "geography": "USA",
                        "granularity": "annual",
                        "quality_min": 0.6,
                        "purpose": "test",
                    }
                ],
                "mode": "hybrid",
                "allow_explore_fallback": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "hybrid"
        assert isinstance(body["fetch_plans"], list)
        assert isinstance(body["candidates"], list)
        assert "meta" in body

    def test_data_discover_returns_payload(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/discover",
            json={
                "data_needs": [
                    {
                        "metric": "us.macro.gdp_nominal",
                        "granularity": "annual",
                        "quality_min": 0.6,
                        "purpose": "test",
                    }
                ],
                "max_sources_per_query": 2,
                "max_discovery_calls_per_source": 3,
                "max_candidates_total": 5,
                "time_budget_ms": 1000,
                "cost_budget_usd": 0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["candidates"], list)
        assert isinstance(body["docs_fetched_total"], int)
        assert "index_stats" in body
        assert "meta" in body

    def test_data_preview_returns_preview(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.post(
            "/api/v1/control/data/preview",
            json={
                "fetch_plan": {
                    "plan_id": "plan_test_preview",
                    "metric_id": "us.macro.gdp_nominal",
                    "connector_id": "missing.connector",
                    "dataset_id": "missing.dataset",
                    "profile_id": None,
                    "filters": {},
                    "date_start": None,
                    "date_end": None,
                    "granularity": "annual",
                    "quality_min": 0.6,
                    "source_lane": "fastlane",
                    "persist_payload": False,
                    "max_preview_rows": 10,
                    "fallbacks": [],
                    "metadata": {},
                },
                "allow_fallback": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "preview" in body
        assert body["preview"]["connector_id"] == "missing.connector"
        assert body["preview"]["dataset_id"] == "missing.dataset"
        assert "meta" in body

    def test_data_catalog_search_returns_capability_frontier(self, runtime_api_env):
        with runtime_api_env["client"] as client:
            resp = client.get("/api/v1/control/data/catalog/search?metric=us.macro&limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["request"]["resource_kinds"] == ["dataset"]
        assert body["request"]["search"]["query_text"] == "us.macro"
        assert body["frontier"]["completeness_status"] == "producer_missing"
        assert body["results"] == []

    def test_data_index_stats_returns_stats(self, runtime_api_env):
        client = runtime_api_env["client"]
        resp = client.get("/api/v1/control/data/index/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "stats" in body
        assert "index_docs_total" in body["stats"]
        assert "index_size_bytes" in body["stats"]
        assert "meta" in body

    def test_data_promotion_endpoints(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="promotion-unresolved-selector",
        )
        with client:
            list_resp = client.get(
                "/api/v1/control/data/promotion/candidates",
                headers=headers,
            )
            assert list_resp.status_code == 200
            assert isinstance(list_resp.json()["candidates"], list)

            approve_resp = client.post(
                "/api/v1/control/data/promotion/nonexistent/approve",
                headers=headers,
                json={"reason": "test"},
            )
            reject_resp = client.post(
                "/api/v1/control/data/promotion/nonexistent/reject",
                headers=headers,
                json={"reason": "test"},
            )

        assert approve_resp.status_code == 403
        assert approve_resp.json()["code"] == "authorization_binding_selector_unresolved"
        assert reject_resp.status_code == 403
        assert reject_resp.json()["code"] == "authorization_binding_selector_unresolved"


class TestIngestStreamingWindowed:
    def test_ingest_streaming_windowed(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-streaming-windowed",
        )
        with (
            client,
            patch(
                "polisyos.fabric.data_plane.modes._fetch_stream_for_dataset_async",
                return_value=[
                    {
                        "chunk_index": 0,
                        "row_count": 1,
                        "is_first": True,
                        "is_last": True,
                        "data": [{"x": 1}],
                    }
                ],
            ),
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [
                        {
                            "connector_id": "test.conn",
                            "dataset_id": "ds1",
                        }
                    ],
                    "execution_mode": "streaming_windowed",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode_effective"] == "streaming_windowed"


class TestIngestRecordReplay:
    def test_ingest_record_mode(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-record-mode",
        )
        with (
            client,
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [
                        {
                            "connector_id": "test.conn",
                            "dataset_id": "ds1",
                        }
                    ],
                    "record_mode": True,
                },
            )
        assert resp.status_code == 200

    def test_ingest_response_has_record_and_binding_fields(self, runtime_api_env):
        client, _cell_id, headers = _secure_control_client(
            runtime_api_env,
            role=PolicyOSRole.ANALYST,
            case_id="ingest-record-binding-fields",
        )
        with (
            client,
            patch(
                "polisyos.fabric.ingestion.run_connectors_ingestion",
                return_value=None,
            ),
        ):
            resp = client.post(
                "/api/v1/control/data/ingest",
                headers=_with_fresh_step_up(client, headers),
                json={
                    "datasets": [
                        {
                            "connector_id": "test.conn",
                            "dataset_id": "ds1",
                        }
                    ],
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        # New Phase 4+5 fields should be present in the response
        assert "record_ref" in body
        assert "input_bindings_ref" in body


def test_lex_search_preserves_truth_fields_through_api(
    runtime_api_env,
    tmp_path,
) -> None:
    import duckdb

    output_dir = tmp_path / "lex-truth-projection"
    output_dir.mkdir()
    database = output_dir / "lex_knowledge_graph.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            """
            CREATE TABLE lex_facts (
                fact_id VARCHAR,
                subject_en VARCHAR,
                predicate VARCHAR,
                object_en VARCHAR,
                fact_text VARCHAR,
                confidence DOUBLE,
                norm_type VARCHAR,
                source_quote_uk VARCHAR,
                trust_tier VARCHAR,
                grounding_status VARCHAR,
                canonical_status VARCHAR,
                reference_resolution_status VARCHAR,
                structure_quality VARCHAR,
                constraint_type_canon VARCHAR,
                route_class VARCHAR,
                fused_confidence DOUBLE,
                consistency_score DOUBLE,
                hallucination_flags_json VARCHAR,
                quality_band VARCHAR,
                doc_id VARCHAR,
                doc_family_id VARCHAR,
                version_id VARCHAR,
                jurisdiction VARCHAR,
                top_domain VARCHAR,
                effective_from VARCHAR,
                effective_to VARCHAR,
                temporal_state VARCHAR,
                temporal_resolution_status VARCHAR,
                temporal_source_scope VARCHAR,
                temporal_source_kind VARCHAR,
                temporal_confidence DOUBLE,
                temporal_provenance_json VARCHAR,
                doc_name VARCHAR,
                doc_reestr_code VARCHAR,
                provision_anchor VARCHAR,
                provision_citation VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO lex_facts VALUES (
                'fact-1', 'Worker', 'is entitled to', 'Leave',
                'Worker is entitled to annual leave', 0.91, 'right',
                'Працівник має право на щорічну відпустку',
                'grounded_fact', 'exact_quote', 'canonicalized', 'resolved',
                'complete', 'entitlement', 'direct_norm', 0.88, 0.97,
                '[]', 'high', 'doc-1', 'family-1', 'version-2026', 'UA',
                'labor', '2026-01-01', '', 'effective', 'resolved',
                'provision', 'official_registry', 0.99,
                '{"source":"official_registry"}', 'Labor Code', '322-VIII',
                'article-74', 'Article 74'
            )
            """
        )
    finally:
        connection.close()

    response = runtime_api_env["client"].post(
        "/api/v1/control/lex/search",
        json={"query": "annual leave", "top_k": 5, "output_dir": str(output_dir)},
    )

    assert response.status_code == 200
    item = response.json()["results"][0]
    assert item["trust_tier"] == "grounded_fact"
    assert item["grounding_status"] == "exact_quote"
    assert item["canonical_status"] == "canonicalized"
    assert item["reference_resolution_status"] == "resolved"
    assert item["fused_confidence"] == pytest.approx(0.88)
    assert item["consistency_score"] == pytest.approx(0.97)
    assert item["hallucination_flags_json"] == "[]"
    assert item["temporal_state"] == "effective"
    assert item["temporal_provenance_json"] == '{"source":"official_registry"}'
    assert item["provision_anchor"] == "article-74"
