from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlanRef, MetricsRef, SimulationResult
from polisyos.core.contracts.runtime import AgentPipelineCostEvent
from polisyos.core.run.context import RunContext
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
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotLineageError,
        validate_data_snapshot_owner_lineage,
    )

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
    snapshot = DataSnapshot(data_ref=payload_ref, quality_report_ref=quality_ref)
    snapshot_inputs = [
        input_ref_from_artifact_ref(payload_ref, role="data_ref"),
        input_ref_from_artifact_ref(quality_ref, role="quality_report_ref"),
    ]
    snapshot_ref = store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=snapshot_inputs,
        ),
        return_selected_profile=True,
    )
    validate_data_snapshot_owner_lineage(store, snapshot_ref, snapshot)
    state_payload = {
        "inputs": {"data_snapshot_ref": snapshot_ref.model_dump(mode="json")},
        "params": {
            "retrieval_context": {
                "auto_data_source_refs": {
                    "data_snapshot_ref": str(snapshot_ref.artifact_id),
                    "quality_report_ref": str(quality_ref.artifact_id),
                }
            }
        },
    }
    state_options = PutOptions(
        kind="scientist.experiment_state",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.scientist.ExperimentState", version="1.0"),
    )
    state_ref = store.put_json(state_payload, state_options)
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

    assert context.data_snapshot_ref == snapshot_ref
    assert "data_snapshot_selected_view_not_established" not in context.warnings
    selected_quality_ref = context.materialization_refs["quality_report_ref"]
    assert selected_quality_ref == quality_ref
    assert selected_quality_ref.kind == quality_kind
    assert selected_quality_ref.manifest_profile_sha256 == quality_ref.manifest_profile_sha256

    # The same snapshot bytes with either owner edge removed are not an admitted
    # parent view, even though the child refs and the context's ID hints remain.
    for omitted_input in snapshot_inputs:
        malformed_ref = store.put_json(
            snapshot,
            PutOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                    version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[edge for edge in snapshot_inputs if edge != omitted_input],
            ),
            return_selected_profile=True,
        )
        assert malformed_ref.artifact_id == snapshot_ref.artifact_id
        assert malformed_ref.manifest_profile_sha256 != snapshot_ref.manifest_profile_sha256
        with pytest.raises(
            DataSnapshotLineageError, match="data_snapshot_manifest_inputs_mismatch"
        ):
            validate_data_snapshot_owner_lineage(store, malformed_ref, snapshot)
        malformed_state_ref = store.put_json(
            {
                **state_payload,
                "inputs": {"data_snapshot_ref": malformed_ref.model_dump(mode="json")},
            },
            state_options,
        )
        malformed_run = SimpleNamespace(
            **{
                **vars(run),
                "experiment_state_ref": malformed_state_ref,
                "details": SimpleNamespace(
                    **{**vars(run.details), "root_input_artifacts": (malformed_ref,)}
                ),
            }
        )
        refused = DebugService(store=store, timeline_service=object()).get_run_evidence_context(
            malformed_run
        )
        assert refused.data_snapshot_ref is None
        assert "quality_report_ref" not in refused.materialization_refs
        assert "data_snapshot_selected_view_not_established" in refused.warnings


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


@pytest.fixture
def simulation_result_api_env(tmp_path: Path, pytestconfig: pytest.Config):
    """Use a declared candidate catalog, with the real DebugService/CAS HTTP graph."""
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_catalog_serving_source,
    )
    from tests._helpers.runtime_http import (
        _build_registry_providers,
        build_runtime_api_env,
        close_runtime_api_env,
    )

    selection, _ = build_candidate_cycle_catalog_serving_source(tmp_path)
    env = build_runtime_api_env(
        tmp_path / "api",
        include_test_client=True,
        app_kwargs={
            "repo_root": Path(pytestconfig.rootpath).resolve(strict=True),
            "catalog_source_selection": selection,
            "container_overrides": RuntimeContainerOverrides(
                control_registry_providers=_build_registry_providers(
                    catalog_run_profile=selection.catalog_run_profile,
                ),
            ),
        },
    )
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def _persist_debug_simulation_candidate_run(
    store,
    registry_bundle_ref: ArtifactRef,
    *,
    run_id: str,
    tenant_id: str,
    cell_id: str,
    simulation_result_ref: ArtifactRef,
    node_ref_payload_groups: list[list[dict[str, object]]],
    run_dir: Path,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef]:
    """Persist selected state/report refs through the runtime store for the served route."""
    tenant_context = ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        state_ref = store.put_json(
            {
                "schema_version": "1.3",
                "run_id": run_id,
                "artifacts_index": {
                    "simulation_result_ref": simulation_result_ref.model_dump(mode="json")
                },
            },
            PutOptions(
                kind="scientist.experiment_state",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.ExperimentState",
                    version="1.3",
                ),
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
        workflow_report_ref = store.put_json(
            {
                "schema_version": "1.0",
                "workflow_id": "debug_simulation_profile_binding",
                "run_id": run_id,
                "status": "ok",
                "nodes": [
                    {
                        "alias": "simulate",
                        "node_id": f"test.simulate.row{index}@1.0.0",
                        "status": "ok",
                        "artifacts": node_ref_payloads,
                    }
                    for index, node_ref_payloads in enumerate(node_ref_payload_groups)
                ],
            },
            PutOptions(
                kind="scientist.workflow_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowReport",
                    version="1.0",
                ),
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle_ref,
            run_dir=run_dir,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        run.add_output(state_ref)
        run.add_output(workflow_report_ref)
        run_manifest_ref = run.finalize(status="ok")

    from tests._helpers.runtime_http import _record_fixture_owner

    _record_fixture_owner(
        store,
        state_ref,
        workflow_report_ref,
        run_manifest_ref,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    return state_ref, workflow_report_ref, run_manifest_ref


def test_simulation_result_http_requires_exact_identity_for_every_same_id_node_ref(
    simulation_result_api_env,
) -> None:
    """Both selectors refuse conflicting refs or ambiguous rows before exposing a result."""
    cas_root = simulation_result_api_env["cas_root"]
    tenant_id = simulation_result_api_env["tenant_a"]
    cell_id = simulation_result_api_env["cell_a"]
    registry_bundle_ref = simulation_result_api_env["registry_bundle_ref"]
    client = simulation_result_api_env["client"]
    app = simulation_result_api_env["app"]
    assert isinstance(cas_root, Path)
    assert isinstance(tenant_id, str)
    assert isinstance(cell_id, str)
    assert isinstance(registry_bundle_ref, ArtifactRef)
    assert client is not None
    assert app is not None

    runtime_container = getattr(app.state, "runtime_container", None)
    runtime_context = getattr(runtime_container, "runtime_api_context", None)
    if runtime_context is None:
        runtime_context = app.state.runtime_api_ctx
    store = runtime_context.store

    tenant_context = ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        exec_plan_artifact = store.put_json(
            {"plan_id": "debug-simulation-profile-binding"},
            PutOptions(
                kind="foundry.exec_plan",
                media_type="application/json",
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
        metrics_artifact = store.put_json(
            {"metrics": {"outcome": 1}},
            PutOptions(
                kind="foundry.metrics",
                media_type="application/json",
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
        result = SimulationResult(
            schema_version="1.3",
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_artifact.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_artifact.artifact_id),
        )
        result_payload = result.to_artifact_payload()

        def _result_profile(version: str) -> ArtifactRef:
            return store.put_json(
                result_payload,
                PutOptions(
                    kind=SimulationResult.ARTIFACT_KIND,
                    media_type=SimulationResult.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(
                        name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                        version="1.3",
                    ),
                    producer=ProducerInfo(
                        component="polisyos.tests.runtime.http.debug",
                        version=version,
                    ),
                    tenant_context=tenant_context,
                ),
                return_selected_profile=True,
            )

        profile_a = _result_profile("profile-a")
        profile_b = _result_profile("profile-b")

    assert profile_a.artifact_id == profile_b.artifact_id
    assert profile_a.manifest_profile_sha256 is not None
    assert profile_b.manifest_profile_sha256 is not None
    assert profile_a.manifest_profile_sha256 != profile_b.manifest_profile_sha256

    from tests._helpers.runtime_http import _record_fixture_owner

    _record_fixture_owner(
        store,
        exec_plan_artifact,
        metrics_artifact,
        profile_a,
        profile_b,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )

    profileless_a = ArtifactRef(
        artifact_id=profile_a.artifact_id,
        kind=profile_a.kind,
        media_type=profile_a.media_type,
    )
    unavailable_b = ArtifactRef.model_validate(
        profile_a.model_dump(mode="json") | {"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    malformed_b = profile_a.model_dump(mode="json") | {
        "manifest_profile_sha256": "sha256:not-a-digest"
    }

    selection_forms = (("default", False), ("explicit", True))
    binding_cases = [
        ("same_ref", profile_a, [[profile_a]], 200, None),
        (
            "node_only_valid_b",
            profile_a,
            [[profile_b]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "node_only_unavailable_b",
            profile_a,
            [[unavailable_b]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "state_a_node_profile_absent",
            profile_a,
            [[profileless_a]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "mixed_a_and_valid_b",
            profile_a,
            [[profile_a, profile_b]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "mixed_a_and_malformed_b",
            profile_a,
            [[profile_a, malformed_b]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        ("state_and_node_unavailable_b", unavailable_b, [[unavailable_b]], 409, None),
        (
            "duplicate_alias_same_ref",
            profile_a,
            [[profile_a], [profile_a]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "duplicate_alias_a_then_b",
            profile_a,
            [[profile_a], [profile_b]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "duplicate_alias_b_then_a",
            profile_a,
            [[profile_b], [profile_a]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "duplicate_alias_a_then_malformed",
            profile_a,
            [[profile_a], [malformed_b]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "duplicate_alias_malformed_then_a",
            profile_a,
            [[malformed_b], [profile_a]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "duplicate_alias_a_then_absent_profile",
            profile_a,
            [[profile_a], [profileless_a]],
            409,
            "simulation_result_node_binding_mismatch",
        ),
        (
            "duplicate_alias_a_then_empty_artifacts",
            profile_a,
            [[profile_a], []],
            409,
            "simulation_result_node_binding_mismatch",
        ),
    ]
    cases = [
        (
            f"{case_name}_{selector_name}",
            state_ref,
            node_ref_groups,
            explicit,
            expected_status,
            expected_code,
        )
        for case_name, state_ref, node_ref_groups, expected_status, expected_code in binding_cases
        for selector_name, explicit in selection_forms
    ]

    for index, (
        case_name,
        state_ref,
        node_ref_groups,
        explicit,
        expected_status,
        expected_code,
    ) in enumerate(cases):
        run_id = f"R_debug_simulation_profile_binding_{index}"
        _persist_debug_simulation_candidate_run(
            store,
            registry_bundle_ref,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            simulation_result_ref=state_ref,
            node_ref_payload_groups=[
                [
                    value.model_dump(mode="json") if isinstance(value, ArtifactRef) else value
                    for value in node_refs
                ]
                for node_refs in node_ref_groups
            ],
            run_dir=cas_root / "runs" / run_id,
        )
        runtime_context.run_index.refresh(force=True)
        url = f"/api/v1/debug/runs/{run_id}/nodes/simulate/simulation-result"
        response = (
            client.get(url, params={"artifact_id": str(profile_a.artifact_id)})
            if explicit
            else client.get(url)
        )

        assert response.status_code == expected_status, f"{case_name}: {response.text}"
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        if expected_status == 200:
            assert payload["debug"]["node_id"] == "test.simulate.row0@1.0.0"
            assert payload["debug"]["artifact_ref"]["artifact_id"] == str(profile_a.artifact_id)
            assert (
                payload["debug"]["artifact_ref"]["manifest_profile_sha256"]
                == profile_a.manifest_profile_sha256
            )
        else:
            assert "debug" not in payload, f"{case_name}: {payload}"
            if expected_code is not None:
                assert payload["code"] == expected_code, f"{case_name}: {payload}"
