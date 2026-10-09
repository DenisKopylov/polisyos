from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.runtime import AgentPipelineCostEvent
from polisyos.runtime.http.services.debug import (
    DebugService,
    SimulationResultProjectionError,
)


def _redacted_marker() -> str:
    return "[" + "REDACTED" + "]"


def test_debug_artifact_reads_preserve_selected_manifest_profile(tmp_path) -> None:
    class _RecordingCAS(FileSystemCAS):
        def __init__(self, root):
            super().__init__(root)
            self.verify_refs: list[object] = []
            self.get_bytes_refs: list[object] = []

        def verify(self, artifact_ref):
            self.verify_refs.append(artifact_ref)
            return super().verify(artifact_ref)

        def get_bytes(self, artifact_ref):
            self.get_bytes_refs.append(artifact_ref)
            return super().get_bytes(artifact_ref)

    store = _RecordingCAS(tmp_path / "cas")
    payload = {"run_id": "run-selected", "schema_version": "1.0", "result": "selected"}
    options = {
        "kind": "scientist.workflow_binding",
        "media_type": "application/json",
        "schema": SchemaInfo(name="test.WorkflowBinding", version="1.0"),
    }
    default_ref = store.put_json(
        payload,
        PutOptions(
            **options,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-default",
                cell_id="cell-default",
            ),
        ),
    )
    selected_ref = store.put_json(
        payload,
        PutOptions(
            **options,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-selected",
                cell_id="cell-selected",
            ),
        ),
    )
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(default_ref).tenant_context.tenant_id == "tenant-default"
    assert store.get_manifest(selected_ref).tenant_context.tenant_id == "tenant-selected"

    debug = DebugService(store=store, timeline_service=object())
    store.verify_refs.clear()
    store.get_bytes_refs.clear()
    loaded = debug._load_verified_binding_json(
        selected_ref,
        expected_kind="scientist.workflow_binding",
        expected_media_type="application/json",
        expected_schema_name="test.WorkflowBinding",
        expected_schema_versions=frozenset({"1.0"}),
        expected_run_id="run-selected",
        expected_tenant_id="tenant-selected",
        expected_cell_id="cell-selected",
    )
    assert loaded == payload
    assert store.verify_refs == [selected_ref]
    assert store.get_bytes_refs == [selected_ref]

    store.get_bytes_refs.clear()
    assert debug._load_json_artifact(selected_ref) == payload
    assert store.get_bytes_refs == [selected_ref]

    foreign_profile = ArtifactRef.model_validate(
        selected_ref.model_dump(mode="json") | {"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    with pytest.raises(SimulationResultProjectionError):
        debug._load_verified_binding_json(
            foreign_profile,
            expected_kind="scientist.workflow_binding",
            expected_media_type="application/json",
            expected_schema_name="test.WorkflowBinding",
            expected_schema_versions=frozenset({"1.0"}),
            expected_run_id="run-selected",
            expected_tenant_id="tenant-selected",
            expected_cell_id="cell-selected",
        )


@pytest.mark.parametrize(
    ("reader_name", "kind", "schema_name"),
    [
        (
            "_agent_steps_from_compiled_cycle",
            "runtime.compiled_recursive_generation_cycle",
            "polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        ),
        (
            "_agent_steps_from_n4_candidate_proposal",
            "runtime.quality.n4_candidate_proposal",
            "policyos.runtime.quality.n4_candidate_proposal_record.v3",
        ),
    ],
)
def test_debug_cost_readers_preserve_exact_selected_profile(
    tmp_path, monkeypatch: pytest.MonkeyPatch, reader_name: str, kind: str, schema_name: str
) -> None:
    class _RecordingCAS(FileSystemCAS):
        def __init__(self, root):
            super().__init__(root)
            self.verify_refs: list[object] = []
            self.get_bytes_refs: list[object] = []

        def verify(self, artifact_ref):
            self.verify_refs.append(artifact_ref)
            return super().verify(artifact_ref)

        def get_bytes(self, artifact_ref):
            self.get_bytes_refs.append(artifact_ref)
            return super().get_bytes(artifact_ref)

    store = _RecordingCAS(tmp_path / reader_name)
    payload = b'{"candidate":"same-bytes"}'
    schema = SchemaInfo(name=schema_name, version="1.0" if "compiled" in kind else "3")
    shared = {
        "kind": kind,
        "media_type": "application/json",
        "schema": schema,
    }
    sibling_ref = store.put_bytes(
        payload,
        PutOptions(
            **shared,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-sibling",
                cell_id="cell-sibling",
            ),
        ),
    )
    selected_ref = store.put_bytes(
        payload,
        PutOptions(
            **shared,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id="tenant-selected",
                cell_id="cell-selected",
            ),
        ),
    )
    assert selected_ref.artifact_id == sibling_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 != sibling_ref.manifest_profile_sha256
    assert store.get_manifest(sibling_ref).tenant_context.tenant_id == "tenant-sibling"
    assert store.get_manifest(selected_ref).tenant_context.tenant_id == "tenant-selected"

    event = AgentPipelineCostEvent(
        event_id="event-selected-profile",
        cost_origin="reported",
        amount=Decimal("0.25"),
        cost_usd=0.25,
        settlement_status="committed",
        durability="ledger",
        model="configured-model",
        provider="configured-provider",
    )
    if reader_name == "_agent_steps_from_compiled_cycle":
        from polisyos.runtime.http.services.control.generation_cycle import (
            CompiledRecursiveGenerationCycleRun,
        )

        monkeypatch.setattr(
            CompiledRecursiveGenerationCycleRun,
            "model_validate",
            classmethod(
                lambda _cls, _payload: SimpleNamespace(
                    nl_preflight_cost_events=(event,),
                    n4_generation_cost_events=(),
                )
            ),
        )
    else:
        from polisyos.runtime.quality import generation_source

        monkeypatch.setattr(
            generation_source.N4CandidateProposalRecordV3,
            "model_validate",
            classmethod(
                lambda _cls, _payload: SimpleNamespace(
                    core_run_id="run-selected",
                    job_id="job-selected",
                    tenant_id="tenant-selected",
                    cell_id="cell-selected",
                    control_job_attempt=1,
                    nl_preflight_cost_events=(),
                    n4_generation_cost_events=(event,),
                )
            ),
        )
        monkeypatch.setattr(
            generation_source,
            "_has_n4_candidate_proposal_v3_owner_profile",
            lambda _manifest, _proposal: True,
        )

    run = SimpleNamespace(
        run_id="run-selected",
        details=SimpleNamespace(
            root_artifacts=(selected_ref,),
            tenant_id="tenant-selected",
            cell_id="cell-selected",
            control_job_id="job-selected",
        ),
    )
    debug = DebugService(store=store, timeline_service=object())
    store.verify_refs.clear()
    store.get_bytes_refs.clear()

    steps, note = getattr(debug, reader_name)(run, sensitive_keys=())

    assert note is None
    assert steps and steps[0].cost_events == [event]
    assert store.verify_refs == [selected_ref]
    assert store.get_bytes_refs == [selected_ref]


def test_node_debug_endpoint_returns_node_context(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(
        f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/nodes/run_governance"
    )
    assert response.status_code == 200

    payload = response.json()["debug"]
    assert payload["alias"] == "run_governance"
    assert payload["record"]["status"] == "fail"
    assert payload["record"]["error_code"] == "governance.blocked"
    assert payload["record"]["error_details"]["api_token"] == _redacted_marker()
    assert payload["cache_bypasses"] >= 1


def test_governance_debug_prefers_governance_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/governance")
    assert response.status_code == 200

    payload = response.json()["debug"]
    assert payload["verdict"] == "reject"
    assert payload["issue_summary"] == {"blocker_count": 1, "warning_count": 0, "info_count": 0}
    assert payload["legal_executed"] is True
    assert payload["transport_summary"]["status"] == "blocked"
    assert payload["normative_summary"]["selected_policy"] == "weighted_welfare"
    assert payload["normative_summary"]["selected_option"] == "baseline"
    assert payload["normative_arbitration_result_ref"] is not None
    assert payload["fallback_from_decision_packet"] is False
    assert payload["report_ref"] is not None


def test_run_errors_endpoint_aggregates_manifest_and_workflow_errors(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/errors")
    assert response.status_code == 200

    errors = response.json()["errors"]
    codes = {item["code"] for item in errors}
    assert "run.failed" in codes
    assert "governance.blocked" in codes
    workflow_error = next(item for item in errors if item["code"] == "governance.blocked")
    assert workflow_error["details"]["api_token"] == _redacted_marker()


def test_feedback_endpoint_returns_feedback_loop(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/feedback")
    assert response.status_code == 200

    payload = response.json()["feedback"]
    assert payload["feedback_loop"]["monitoring_contract_ref"] is not None
    assert payload["monitoring_contract"]["metrics"][0]["metric_id"] == "policy_cost"


def test_equilibria_endpoint_returns_multiplicity_report(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/equilibria")
    assert response.status_code == 200

    payload = response.json()["equilibria"]
    assert payload["report_ref"]["artifact_id"] == runtime_api_env["equilibrium_report_artifact_id"]
    assert payload["report"]["model_id"] == "ks_lite_fixture"
    assert payload["report"]["global_diagnostics"]["num_equilibria"] == 1


def test_compare_endpoint_surfaces_law_delta(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(
        f"/api/v1/debug/runs/{runtime_api_env['core_run_id']}/compare/"
        f"{runtime_api_env['core_run_id_secondary']}"
    )
    assert response.status_code == 200

    payload = response.json()["compare"]
    assert payload["report"]["deltas"]["law"]["changed"] is True
    assert "law" in payload["report"]["root_cause"]
