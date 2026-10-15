from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.runtime import AgentPipelineCostEvent
from polisyos.core.security.tenant_context import tenant_scope
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
            super().__init__(root, ownership_enforced=True, ownership_requires_scope=False)
            self.verify_refs: list[object] = []
            self.get_bytes_refs: list[object] = []

        def verify(self, artifact_ref):
            self.verify_refs.append(artifact_ref)
            return super().verify(artifact_ref)

        def get_bytes(self, artifact_ref):
            self.get_bytes_refs.append(artifact_ref)
            return super().get_bytes(artifact_ref)

    store = _RecordingCAS(tmp_path / reader_name)
    canon_spec = CanonSpec(forbid_floats=False)
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
    selected_proposal_record = None
    if reader_name == "_agent_steps_from_n4_candidate_proposal":
        from polisyos.runtime.quality import generation_source

        payload = to_canonical_bytes({"candidate": "same-bytes"}, generation_source._SOURCE_CANON)

        def proposal_record(tenant_id: str, cell_id: str) -> SimpleNamespace:
            return SimpleNamespace(
                run_id="run-selected",
                core_run_id="run-selected",
                job_id="job-selected",
                tenant_id=tenant_id,
                cell_id=cell_id,
                control_job_attempt=1,
                nl_preflight_cost_events=(),
                n4_generation_cost_events=(event,),
            )

        selected_proposal_record = proposal_record("tenant-selected", "cell-selected")
        sibling_options = generation_source._n4_candidate_proposal_v3_write_options(
            proposal_record("tenant-sibling", "cell-sibling")
        )
        selected_options = generation_source._n4_candidate_proposal_v3_write_options(
            selected_proposal_record
        )
    else:
        payload = to_canonical_bytes({"candidate": "same-bytes"}, canon_spec)

        def compiled_options(tenant_id: str, cell_id: str) -> PutOptions:
            return PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version="1.0"),
                canon=CanonInfo.from_spec(canon_spec),
                tenant_context=ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id),
            )

        sibling_options = compiled_options("tenant-sibling", "cell-sibling")
        selected_options = compiled_options("tenant-selected", "cell-selected")

    with tenant_scope(None, tenant_id="tenant-sibling", cell_id="cell-sibling"):
        sibling_ref = store.put_bytes(payload, sibling_options, return_selected_profile=True)
    with tenant_scope(None, tenant_id="tenant-selected", cell_id="cell-selected"):
        selected_ref = store.put_bytes(payload, selected_options, return_selected_profile=True)
    assert selected_ref.artifact_id == sibling_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    assert sibling_ref.manifest_profile_sha256 is not None
    assert selected_ref.manifest_profile_sha256 != sibling_ref.manifest_profile_sha256
    with tenant_scope(None, tenant_id="tenant-sibling", cell_id="cell-sibling"):
        assert store.get_manifest(sibling_ref).tenant_context.tenant_id == "tenant-sibling"
    with tenant_scope(None, tenant_id="tenant-selected", cell_id="cell-selected"):
        assert store.get_manifest(selected_ref).tenant_context.tenant_id == "tenant-selected"
        with pytest.raises(ArtifactOwnershipError):
            store.get_manifest(sibling_ref)

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

        assert selected_proposal_record is not None
        monkeypatch.setattr(
            generation_source.N4CandidateProposalRecordV3,
            "model_validate",
            classmethod(lambda _cls, _payload: selected_proposal_record),
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

    with tenant_scope(None, tenant_id="tenant-selected", cell_id="cell-selected"):
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


@pytest.mark.parametrize(
    ("quality_kind", "quality_schema", "quality_payload"),
    [
        (
            "fabric.retrieval_summary",
            SchemaInfo(name="polisyos.fabric.RetrievalSummary", version="1.0"),
            {
                "assessment_status": "not_assessed",
                "source": "debug_fixture",
                "source_refs": [],
                "observed_counts": {},
                "notes": [],
            },
        ),
        (
            "fabric.quality_report",
            SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
            {"status": "assessed_by_owner"},
        ),
    ],
)
def test_evidence_context_preserves_quality_ref_selected_by_snapshot(
    tmp_path,
    quality_kind,
    quality_schema,
    quality_payload,
) -> None:
    from polisyos.core.contracts.fabric import DataSnapshot

    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = store.put_json(
        {"metrics": [{"metric_id": "gdp"}]},
        PutOptions(
            kind="fabric.retrieval_payload",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.RetrievalPayload", version="1.0"),
        ),
        return_selected_profile=True,
    )
    if quality_kind == "fabric.retrieval_summary":
        quality_payload = {
            **quality_payload,
            "source_refs": [payload_ref.model_dump(mode="json")],
        }
    quality_ref = store.put_json(
        quality_payload,
        PutOptions(
            kind=quality_kind,
            media_type="application/json",
            schema=quality_schema,
        ),
        return_selected_profile=True,
    )
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref, quality_report_ref=quality_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        return_selected_profile=True,
    )
    state_ref = store.put_json(
        {
            "inputs": {"data_snapshot_ref": snapshot_ref.model_dump(mode="json")},
            "params": {
                "retrieval_context": {
                    "auto_data_source_refs": {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "quality_report_ref": str(quality_ref.artifact_id),
                    }
                }
            },
        },
        PutOptions(
            kind="scientist.experiment_state",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.ExperimentState", version="1.0"),
        ),
    )
    run = SimpleNamespace(
        run_id="run-summary-debug",
        source_kind="core_run",
        details=SimpleNamespace(
            control_job_id=None,
            tenant_id=None,
            cell_id=None,
            manifest_ref=None,
            root_artifacts=(),
            root_input_artifacts=(snapshot_ref,),
        ),
        experiment_state_ref=state_ref,
        decision_packet_ref=None,
    )

    context = DebugService(store=store, timeline_service=object()).get_run_evidence_context(run)

    selected_quality_ref = context.materialization_refs["quality_report_ref"]
    assert selected_quality_ref == quality_ref
    assert selected_quality_ref.kind == quality_kind
    assert selected_quality_ref.manifest_profile_sha256 == quality_ref.manifest_profile_sha256


def test_evidence_context_does_not_infer_quality_owner_from_ids_alone(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = store.put_json(
        {"metrics": [{"metric_id": "gdp"}]},
        PutOptions(
            kind="fabric.retrieval_payload",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.RetrievalPayload", version="1.0"),
        ),
    )
    quality_ref = store.put_json(
        {"status": "assessed_by_owner"},
        PutOptions(
            kind="fabric.quality_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        ),
    )
    from polisyos.core.contracts.fabric import DataSnapshot

    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref, quality_report_ref=quality_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    state_ref = store.put_json(
        {
            "params": {
                "retrieval_context": {
                    "auto_data_source_refs": {
                        "data_snapshot_ref": str(snapshot_ref.artifact_id),
                        "quality_report_ref": str(quality_ref.artifact_id),
                    }
                }
            }
        },
        PutOptions(
            kind="scientist.experiment_state",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.ExperimentState", version="1.0"),
        ),
    )
    run = SimpleNamespace(
        run_id="run-unselected-debug",
        source_kind="core_run",
        details=SimpleNamespace(
            control_job_id=None,
            tenant_id=None,
            cell_id=None,
            manifest_ref=None,
            root_artifacts=(),
            root_input_artifacts=(),
        ),
        experiment_state_ref=state_ref,
        decision_packet_ref=None,
    )

    context = DebugService(store=store, timeline_service=object()).get_run_evidence_context(run)

    assert context.data_snapshot_ref is None
    assert "quality_report_ref" not in context.materialization_refs
    assert "data_snapshot_selected_view_not_established" in context.warnings
