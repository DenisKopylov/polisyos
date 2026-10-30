"""RES-03 B13 witness for the real simulation-to-user read path."""

from __future__ import annotations

import json
import sqlite3
from contextlib import ExitStack
from dataclasses import replace
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts._profiled_ref import profile_bound_ref
from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    CanonInfo,
    EnvInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef, DataViewRequestRef
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    SimulationResult,
)
from polisyos.core.contracts.runtime import RuntimeApiProblem
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.services.debug import SimulationResultProjectionError
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.orchestration.workflows.builder import (
    build_execution_context,
    build_registry_with_builtin_nodes,
)
from polisyos.scientist.orchestration.workflows.default import default_workflow_spec
from tests._helpers.control_worker import stop_embedded_control_worker

pytestmark = pytest.mark.integration

_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL_ID = "cell-a"


def _artifact_ref_contract_identity(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    """Return every serialized identity field that binds a CAS artifact reference."""
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _coerce_manifest_model(value: Any, model: Any) -> Any:
    """Coerce IR or core manifest metadata into the core model used by CAS."""
    if value is None or isinstance(value, model):
        return value
    if isinstance(value, dict):
        return model.model_validate(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model.model_validate(model_dump(mode="python"))
    return value


def _coerce_put_options(
    opts: PutOptions,
    *,
    tenant_context: ArtifactTenantContextInfo | None,
) -> PutOptions:
    """Adapt core and IR write options without dropping manifest metadata."""
    raw_inputs = getattr(opts, "inputs", None)
    inputs = (
        None
        if raw_inputs is None
        else [_coerce_manifest_model(item, InputRef) for item in raw_inputs]
    )
    return PutOptions(
        kind=opts.kind,
        media_type=opts.media_type,
        schema=_coerce_manifest_model(getattr(opts, "schema", None), SchemaInfo),
        producer=_coerce_manifest_model(getattr(opts, "producer", None), ProducerInfo),
        env=_coerce_manifest_model(getattr(opts, "env", None), EnvInfo),
        inputs=inputs,
        canon=_coerce_manifest_model(getattr(opts, "canon", None), CanonInfo),
        governance=_coerce_manifest_model(
            getattr(opts, "governance", None), ArtifactGovernanceInfo
        ),
        tenant_context=tenant_context,
        same_input_closure=_coerce_manifest_model(
            getattr(opts, "same_input_closure", None),
            ArtifactSameInputClosureInfo,
        ),
        authority=_coerce_manifest_model(getattr(opts, "authority", None), ArtifactAuthorityInfo),
    )


class _TenantScopedCAS(FileSystemCAS):
    """Make this real-route witness persist explicit tenant-scoped manifests."""

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        tenant_context = getattr(opts, "tenant_context", None) or ArtifactTenantContextInfo(
            tenant_id=_TENANT_ID,
            cell_id=_CELL_ID,
        )
        return super().put_json(
            obj,
            _coerce_put_options(opts, tenant_context=tenant_context),
            canon_spec,
            return_selected_profile=return_selected_profile,
        )

    def put_json_unscoped(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Persist an intentionally unscoped negative fixture."""
        return super().put_json(
            obj,
            _coerce_put_options(opts, tenant_context=None),
            canon_spec,
        )

    def put_json_for_tenant(
        self,
        obj: object,
        opts: PutOptions,
        *,
        tenant_id: str,
        cell_id: str | None,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Persist a fixture through a CAS view owned by its manifest tenant."""
        tenant_store = self.for_tenant(tenant_id, cell_id)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            return tenant_store.put_json(
                obj,
                _coerce_put_options(
                    opts,
                    tenant_context=ArtifactTenantContextInfo(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    ),
                ),
                canon_spec,
            )


def _assert_authority_surface_conflict(response: Any) -> None:
    assert response.status_code == 409, response.text
    problem = RuntimeApiProblem.model_validate_json(response.content, strict=True)
    assert problem.status == problem.status_code == 409
    assert problem.code == "authority_surface_admission_blocked"
    assert problem.extensions is not None
    decision = problem.extensions["authority_surface_decision"]
    assert decision["reason"] == "authority_surface_signal_missing"
    assert decision["blocking"] is True
    assert decision["visible_downgrade"] is True
    assert decision["integrity_status"] == "verified"


def _metadata(component_id: str, display_name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(component_id),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=display_name,
        description=f"{display_name} RES-03 witness node",
        tags=["test", "res-03"],
        capabilities=Capability.SCIENTIST_NODE,
    )


class _LaterFailureNode:
    """Fail after a real simulation while retaining the simulation reference."""

    def __init__(self) -> None:
        self.seen_simulation_ref: Any = None
        self._spec = NodeSpec(
            metadata=_metadata(
                "scientist.node_res03_later_failure@1.0.0",
                "RES-03 later failure",
            ),
            state_reads=[f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.seen_simulation_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if self.seen_simulation_ref is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="res03.missing_simulation",
                    message="The later stage did not receive the simulation result",
                ),
            )
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code="res03.later_failure",
                message="Deterministic later-stage failure after simulation",
                details={
                    "scope": {
                        "upstream_node": "run_simulation",
                        "failed_node": "later_failure",
                        "simulation_result_ref": str(self.seen_simulation_ref.artifact_id),
                    },
                    "reason": "RES-03 verification input",
                },
            ),
        )


class _DependentNode:
    """Represent a dependent output that must be invalidated by the failure."""

    def __init__(self) -> None:
        self._spec = NodeSpec(
            metadata=_metadata(
                "scientist.node_res03_dependent@1.0.0",
                "RES-03 dependent output",
            ),
            state_reads=[f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}"],
            state_writes=["params.res03_dependent_output"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx, state
        raise AssertionError("dependent output must not execute after its upstream failure")


class _IndependentSiblingNode:
    """Prove that an independent sibling still runs on the retained state."""

    def __init__(self) -> None:
        self.seen_simulation_ref: Any = None
        self._spec = NodeSpec(
            metadata=_metadata(
                "scientist.node_res03_independent@1.0.0",
                "RES-03 independent sibling",
            ),
            state_reads=[f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}"],
            state_writes=["params.res03_independent_ran"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.seen_simulation_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        new_state = state.model_copy(deep=True)
        new_state.params["res03_independent_ran"] = True
        return NodeOutcome(status="ok", state=new_state)


def _produce_sql_snapshot(
    tmp_path,
    store: FileSystemCAS,
) -> tuple[DataViewRequestRef, DataSnapshotRef]:
    """Produce one real profile-bound snapshot from a controlled SQLite source."""
    db_path = tmp_path / "policy-inputs.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE policy_inputs (income REAL NOT NULL, note TEXT)")
        connection.executemany(
            "INSERT INTO policy_inputs VALUES (?, ?)",
            [(12.5, "first"), (25.0, None)],
        )
    connector_registry = ConnectorRegistry()
    connector_registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{db_path}",
            headers={"X-SQL-Table": "policy_inputs"},
        ),
    )
    request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="res03_controlled_sql_inputs",
            view_type="table",
            metrics=["policy_inputs"],
        ),
        PutOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    data_view_request_ref = DataViewRequestRef.model_validate(
        profile_bound_ref(store, request_ref).model_dump(mode="python")
    )
    try:
        snapshot_ref = DefaultFabricPort(connector_registry=connector_registry).snapshot(
            store,
            data_view_request_ref,
        )
    finally:
        connector_registry.shutdown()
    return data_view_request_ref, snapshot_ref


def _build_real_trinity(registry_bundle_ref: Any, data_snapshot_ref: DataSnapshotRef) -> Any:
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="res03_problem", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="res03_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="res03_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        ),
    )
    return trinity


def _build_workflow() -> WorkflowSpec:
    base = default_workflow_spec()
    pre_simulation_aliases = {
        "start",
        "build_data_snapshot",
        "build_execution_plan",
        "build_method_catalog_snapshot",
        "run_preflight",
        "ready_to_run",
        "bind_foundry_inputs",
        "run_data_plane_gate",
        "compile_foundry",
        "compile_cross_graph_evidence",
        "resolve_parameters",
        "run_simulation",
    }
    selected = [node for node in base.nodes if node.alias in pre_simulation_aliases]
    assert {node.alias for node in selected} == pre_simulation_aliases
    # This reduced-DAG witness exercises CompileFoundryNode's real strict linker
    # while isolating RES-03 from the full default-workflow route. It omits the
    # standalone LinkTrinityNode; the earlier CAS-conflict explanation was not
    # reproduced: both writers succeeded with the same report ID and payload,
    # but returned distinct manifest-selected views. This test is not evidence
    # for the 23-node default workflow, which has a separate route test.
    selected = [
        (
            node.model_copy(
                update={
                    "depends_on": [
                        dependency for dependency in node.depends_on if dependency != "link_trinity"
                    ]
                }
            )
            if node.alias == "compile_foundry"
            else node
        )
        for node in selected
    ]
    return WorkflowSpec(
        workflow_id="res_03_real_route",
        required_binds=base.required_binds,
        error_policy="continue",
        nodes=[
            *selected,
            NodeInvocation(
                alias="later_failure",
                node_id=ComponentId.parse("scientist.node_res03_later_failure@1.0.0"),
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="dependent_after_failure",
                node_id=ComponentId.parse("scientist.node_res03_dependent@1.0.0"),
                depends_on=["later_failure"],
            ),
            NodeInvocation(
                alias="independent_sibling",
                node_id=ComponentId.parse("scientist.node_res03_independent@1.0.0"),
                depends_on=["run_simulation"],
            ),
        ],
    )


def test_res_03_real_simulation_later_failure_reaches_user_route(
    tmp_path,
    request: pytest.FixtureRequest,
) -> None:
    """Persist a real simulation, then expose the later failure and invalidation."""
    store = _TenantScopedCAS(tmp_path / "cas", tenant_id=_TENANT_ID, cell_id=_CELL_ID)

    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        registry_bundle = build_default_registry_bundle(store)
        data_view_request_ref, data_snapshot_ref = _produce_sql_snapshot(tmp_path, store)
        trinity = _build_real_trinity(registry_bundle.bundle_ref, data_snapshot_ref)
        trinity_tenant_context = ArtifactTenantContextInfo(
            tenant_id=_TENANT_ID,
            cell_id=_CELL_ID,
        )
        trinity_selected_ref = persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            trinity,
            tenant_context=trinity_tenant_context,
        )
        trinity_ref = ArtifactRef.model_validate(trinity_selected_ref.model_dump(mode="python"))
        trinity_manifest = store.get_manifest(trinity_ref)
        assert trinity_manifest.tenant_context == trinity_tenant_context
        assert trinity_manifest.canon == CanonInfo.from_spec(CanonSpec(forbid_floats=False))
        assert store.verify(trinity_ref).ok
        app = create_runtime_api_app(
            cas_root=store.root,
            core_runs_root=store.root / "runs",
            allow_unscoped_artifacts=True,
            allow_fixture_identity=True,
            enable_security_middlewares=False,
        )
        client_lifecycle = ExitStack()
        request.addfinalizer(client_lifecycle.close)
        client = client_lifecycle.enter_context(TestClient(app, raise_server_exceptions=False))
        control_service = app.state._control_service
        stop_embedded_control_worker(control_service)
        launch_response = client.post(
            "/api/v1/control/runs",
            json={
                "data_source": {
                    "data_view_request_ref": data_view_request_ref.model_dump(mode="json")
                },
                "trinity_bundle_ref": str(trinity_ref.artifact_id),
                "params": {"workflow_id": "scientist_default"},
            },
        )
        assert launch_response.status_code == 200, launch_response.text
        launch = launch_response.json()
        run_id = launch["run_id"]
        control_job_id = launch["job_id"]
        admitted_job = control_service._control_store.get_job(control_job_id)
        assert admitted_job is not None
        assert admitted_job.run_id == run_id
        assert admitted_job.kind == "workflow_run"
        assert admitted_job.payload_ref is not None
        admitted_payload = control_service._load_payload_ref(
            admitted_job.payload_ref,
            kind="runtime.control_job_payload.workflow_run",
        )
        admitted_request_ref = ArtifactRef.model_validate(
            admitted_payload["state_payload"]["inputs"]["data_view_request_ref"]
        )
        assert _artifact_ref_contract_identity(admitted_request_ref) == (
            _artifact_ref_contract_identity(data_view_request_ref)
        )
        assert admitted_payload["data_view_request_intent"]["profile_origin"] == ("caller_selected")
        created_outbox_event = control_service._control_store.get_job_created_outbox_event(
            control_job_id
        )
        assert created_outbox_event.topic == "control.job.created"
        assert created_outbox_event.run_id == run_id
        state = ExperimentState(
            run_id=run_id,
            control_job_id=control_job_id,
            inputs={
                "trinity_bundle_ref": trinity_ref,
                "registry_bundle_ref": registry_bundle.bundle_ref,
                "data_snapshot_ref": data_snapshot_ref,
                "data_view_request_ref": data_view_request_ref,
            },
            params={
                # The actual SQL income rows seed the agent population. The
                # tax-rate default keeps the existing simulation mechanics
                # runnable and makes the bound state distinct from its source.
                "foundry_input_binding_rules": [
                    FoundryInputBindingRule(
                        binding_id="res03.sql_income",
                        source_path="income",
                        target_slot_id="agents.income",
                        required=True,
                        notes=["bind actual SQLite producer rows into Foundry"],
                    ),
                    FoundryInputBindingRule(
                        binding_id="res03.fixture_tax_rate",
                        source_path="fixture.tax_rate",
                        target_slot_id="global.tax_rate",
                        default_value=Decimal("0.1"),
                        notes=["test fixture makes bound snapshot distinct"],
                    ),
                ]
            },
        )

        later_failure = _LaterFailureNode()
        dependent = _DependentNode()
        independent = _IndependentSiblingNode()
        registry: NodeRegistry = build_registry_with_builtin_nodes(include_discovered_nodes=False)
        registry.register(later_failure)
        registry.register(dependent)
        registry.register(independent)

        ctx = build_execution_context(
            store,
            registry_bundle.bundle_ref,
            run_id=run_id,
            foundry=DefaultFoundryPort(),
        )
        # This fixture runs a custom failing-sibling DAG through the low-level
        # executor, so persist the real admitted job backlink that the normal
        # workflow launcher propagates before execution.
        ctx.run.update_manifest(control_job_id=control_job_id)
        result = WorkflowExecutor(ctx, registry).execute(_build_workflow(), state)

    records = {record.alias: record for record in result.report.nodes}
    simulation_ref = result.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    simulation_manifest = store.get_manifest(simulation_ref.artifact_id)
    simulation_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(simulation_ref.artifact_id))
    )

    assert result.report.status == "fail"
    assert simulation_result.exec_plan_ref is not None
    assert simulation_result.state_snapshot_ref is not None
    simulated_state = load_state_snapshot(
        store,
        snapshot_ref=simulation_result.state_snapshot_ref,
    )
    assert simulated_state.agents.income.shape == (2,)
    assert all(float(value) > 0 for value in simulated_state.agents.income.tolist())
    assert records["run_simulation"].status == "ok"
    assert records["later_failure"].status == "fail"
    assert records["later_failure"].error is not None
    assert records["later_failure"].error.code == "res03.later_failure"
    assert records["later_failure"].error.details["scope"]["simulation_result_ref"] == str(
        simulation_ref.artifact_id
    )
    assert records["dependent_after_failure"].status == "skip"
    assert records["dependent_after_failure"].skip_reason == "upstream_failed"
    assert not records["dependent_after_failure"].artifacts
    assert records["independent_sibling"].status == "ok"
    simulation_ref_identity = _artifact_ref_contract_identity(simulation_ref)
    assert _artifact_ref_contract_identity(later_failure.seen_simulation_ref) == (
        simulation_ref_identity
    )
    assert _artifact_ref_contract_identity(independent.seen_simulation_ref) == (
        simulation_ref_identity
    )
    assert (
        _artifact_ref_contract_identity(
            simulation_ref.model_copy(update={"kind": "foundry.other_artifact"})
        )
        != simulation_ref_identity
    )
    assert (
        _artifact_ref_contract_identity(
            simulation_ref.model_copy(update={"manifest_profile_sha256": f"sha256:{'a' * 64}"})
        )
        != simulation_ref_identity
    )
    assert result.state.params["res03_independent_ran"] is True
    assert "res03_dependent_output" not in result.state.params

    input_roles = {item.role for item in simulation_manifest.inputs}
    assert {
        "exec_plan",
        "input.input_bindings_ref",
        "input.data_snapshot_ref",
        "input.bound_state_snapshot_ref",
        "state_snapshot",
    } <= input_roles

    run_details_response = client.get(f"/api/v1/runs/{run_id}")
    run_summaries_response = client.get("/api/v1/runs", params={"q": run_id})
    workflow_response = client.get(f"/api/v1/runs/{run_id}/workflow")
    evidence_context_response = client.get(f"/api/v1/runs/{run_id}/evidence-context")
    assert evidence_context_response.status_code == 200, evidence_context_response.text
    evidence_context = evidence_context_response.json()["context"]
    assert _artifact_ref_contract_identity(
        ArtifactRef.model_validate(evidence_context["data_snapshot_ref"])
    ) == (_artifact_ref_contract_identity(data_snapshot_ref))
    assert _artifact_ref_contract_identity(
        ArtifactRef.model_validate(evidence_context["data_view_request_ref"])
    ) == (_artifact_ref_contract_identity(data_view_request_ref))
    assert evidence_context["data_view_request_profile_status"] == "caller_selected_profile"
    assert not any(
        warning.startswith("data_view_request_") for warning in evidence_context["warnings"]
    )
    errors_response = client.get(f"/api/v1/debug/runs/{run_id}/errors")
    candidate_response = client.get(
        f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
    )
    wrong_node_response = client.get(
        f"/api/v1/debug/runs/{run_id}/nodes/later_failure/simulation-result"
    )
    missing_node_response = client.get(
        f"/api/v1/debug/runs/{run_id}/nodes/missing_node/simulation-result"
    )
    wrong_ref_response = client.get(
        f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result",
        params={"artifact_id": str(data_snapshot_ref.artifact_id)},
    )
    wrong_run_response = client.get(
        "/api/v1/debug/runs/R_res03_foreign/nodes/later_failure/simulation-result"
    )
    manifest_response = client.get(f"/api/v1/artifacts/{simulation_ref.artifact_id}")
    content_response = client.get(f"/api/v1/artifacts/{simulation_ref.artifact_id}/content")
    lineage_response = client.get(f"/api/v1/artifacts/{simulation_ref.artifact_id}/lineage")

    blob_path, _manifest_path = store._paths(simulation_ref.artifact_id)
    original_bytes = blob_path.read_bytes()
    blob_path.write_bytes(original_bytes + b"tampered")
    try:
        tampered_response = client.get(
            f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
        )
    finally:
        blob_path.write_bytes(original_bytes)

    workflow_report_ref = result.state.reports_index["workflow_report"]
    report_blob_path, _report_manifest_path = store._paths(workflow_report_ref.artifact_id)
    report_original_bytes = report_blob_path.read_bytes()
    report_blob_path.write_bytes(report_original_bytes + b"tampered")
    try:
        binding_tampered_response = client.get(
            f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
        )
    finally:
        report_blob_path.write_bytes(report_original_bytes)

    runtime_context = app.state.runtime_container.runtime_api_context
    indexed_run = runtime_context.run_index.get_run(run_id)

    # Preserve the real successful report and all other state while removing only
    # the retained result reference. The owner-selected state is a real verified
    # CAS artifact; the index selection is an explicit test seam for this negative.
    assert candidate_response.status_code == 200, candidate_response.text
    state_without_result = result.state.model_copy(deep=True)
    removed_ref = state_without_result.artifacts_index.pop(ARTIFACT_SIMULATION_RESULT_REF)
    assert removed_ref == simulation_ref
    assert records["run_simulation"].status == "ok"
    assert records["independent_sibling"].status == "ok"
    assert result.report.status == "fail"
    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        missing_result_state_ref = store.put_json(
            state_without_result,
            PutOptions(
                kind="scientist.experiment_state",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.ExperimentState",
                    version=state_without_result.schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert store.verify(missing_result_state_ref).ok
    assert missing_result_state_ref != indexed_run.experiment_state_ref
    removed_ref_run = replace(indexed_run, experiment_state_ref=missing_result_state_ref)
    assert removed_ref_run.workflow_report_ref == indexed_run.workflow_report_ref
    with patch.object(runtime_context.run_index, "get_run", return_value=removed_ref_run):
        retained_ref_removed_response = client.get(
            f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
        )
    assert retained_ref_removed_response.status_code == 409, retained_ref_removed_response.text
    problem = RuntimeApiProblem.model_validate_json(
        retained_ref_removed_response.content, strict=True
    )
    assert problem.status == problem.status_code == 409
    assert problem.code == "simulation_result_ref_missing"
    restored_response = client.get(
        f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
    )
    assert restored_response.status_code == 200, restored_response.text
    assert (
        restored_response.json()["debug"]["artifact_ref"]
        == (candidate_response.json()["debug"]["artifact_ref"])
    )

    rebound_fixture_counter = 0

    def _get_candidate_in_owner_scope(run: Any, *, alias: str) -> Any:
        """Call the service as the persisted run owner, as HTTP middleware does."""
        tenant_id = run.details.tenant_id
        cell_id = run.details.cell_id
        assert (tenant_id, cell_id) == (_TENANT_ID, _CELL_ID)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            return runtime_context.debug.get_simulation_result_candidate(run, alias=alias)

    def _assert_fixture_ref_is_owned(
        ref: ArtifactRef,
        *,
        tenant_id: str,
        cell_id: str,
    ) -> None:
        """Prove a negative fixture exists and verifies in its actual owner scope."""
        owner_store = store.for_tenant(tenant_id, cell_id)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            manifest = owner_store.get_manifest(ref.artifact_id)
            verification = owner_store.verify(ref.artifact_id)
        assert manifest.tenant_context == ArtifactTenantContextInfo(
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        assert verification.ok

    def _run_rebound_to(
        candidate_ref: ArtifactRef,
        *,
        state_run_id: str = run_id,
        report_run_id: str = run_id,
        state_tenant_id: str = _TENANT_ID,
        state_cell_id: str | None = _CELL_ID,
        report_tenant_id: str = _TENANT_ID,
        report_cell_id: str | None = _CELL_ID,
        state_schema_version: str | None = None,
        report_schema_version: str | None = None,
        state_payload_schema_version: str | None = None,
        report_payload_schema_version: str | None = None,
        state_ref_kind: str | None = None,
        state_ref_media_type: str | None = None,
        report_ref_kind: str | None = None,
        report_ref_media_type: str | None = None,
        node_ref_kind: str | None = None,
        node_ref_media_type: str | None = None,
        node_ref_override: ArtifactRef | None = None,
        node_ref_conflicting_kind: str | None = None,
        node_ref_conflicting_media_type: str | None = None,
    ) -> Any:
        nonlocal rebound_fixture_counter
        rebound_fixture_counter += 1
        # Keep each rebound payload unique: deliberate tenant/schema profile changes
        # must not collide with the CAS's immutable manifest profile.
        rebound_state = result.state.model_copy(update={"run_id": state_run_id}, deep=True)
        rebound_state.params["res03_fixture_variant"] = rebound_fixture_counter
        rebound_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = candidate_ref
        state_payload = (
            rebound_state.model_copy(update={"schema_version": state_payload_schema_version})
            if state_payload_schema_version is not None
            else rebound_state
        )
        state_options = PutOptions(
            kind="scientist.experiment_state",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.ExperimentState",
                version=state_schema_version or result.state.schema_version,
            ),
        )
        if (state_tenant_id, state_cell_id) == (_TENANT_ID, _CELL_ID):
            state_ref = store.put_json(
                state_payload,
                state_options,
                canon_spec=CanonSpec(forbid_floats=False),
            )
        else:
            state_ref = store.put_json_for_tenant(
                state_payload,
                state_options,
                tenant_id=state_tenant_id,
                cell_id=state_cell_id,
                canon_spec=CanonSpec(forbid_floats=False),
            )
        if state_ref_kind is not None or state_ref_media_type is not None:
            state_ref = state_ref.model_copy(
                update={
                    key: value
                    for key, value in {
                        "kind": state_ref_kind,
                        "media_type": state_ref_media_type,
                    }.items()
                    if value is not None
                }
            )
        rebound_nodes = []
        for node in result.report.nodes:
            if node.alias != "run_simulation":
                if node.alias == "independent_sibling":
                    rebound_nodes.append(
                        node.model_copy(
                            update={"duration_ms": node.duration_ms + rebound_fixture_counter}
                        )
                    )
                else:
                    rebound_nodes.append(node)
                continue
            node_artifacts = [
                (node_ref_override or candidate_ref)
                if ref.artifact_id == simulation_ref.artifact_id
                else ref
                for ref in node.artifacts
            ]
            if node_ref_kind is not None or node_ref_media_type is not None:
                node_artifacts = [
                    ref.model_copy(
                        update={
                            key: value
                            for key, value in {
                                "kind": node_ref_kind,
                                "media_type": node_ref_media_type,
                            }.items()
                            if value is not None
                        }
                    )
                    if ref.artifact_id == candidate_ref.artifact_id
                    else ref
                    for ref in node_artifacts
                ]
            if node_ref_conflicting_kind is not None or node_ref_conflicting_media_type is not None:
                node_artifacts.append(
                    candidate_ref.model_copy(
                        update={
                            key: value
                            for key, value in {
                                "kind": node_ref_conflicting_kind,
                                "media_type": node_ref_conflicting_media_type,
                            }.items()
                            if value is not None
                        }
                    )
                )
            rebound_nodes.append(node.model_copy(update={"artifacts": node_artifacts}))
        report_options = PutOptions(
            kind="scientist.workflow_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowReport",
                version=report_schema_version or "1.0",
            ),
        )
        report_payload = result.report.model_copy(
            update={
                "nodes": rebound_nodes,
                "run_id": report_run_id,
                **(
                    {"schema_version": report_payload_schema_version}
                    if report_payload_schema_version is not None
                    else {}
                ),
            }
        )
        if (report_tenant_id, report_cell_id) == (_TENANT_ID, _CELL_ID):
            report_ref = store.put_json(report_payload, report_options)
        else:
            report_ref = store.put_json_for_tenant(
                report_payload,
                report_options,
                tenant_id=report_tenant_id,
                cell_id=report_cell_id,
            )
        if report_ref_kind is not None or report_ref_media_type is not None:
            report_ref = report_ref.model_copy(
                update={
                    key: value
                    for key, value in {
                        "kind": report_ref_kind,
                        "media_type": report_ref_media_type,
                    }.items()
                    if value is not None
                }
            )
        return replace(
            indexed_run,
            experiment_state_ref=state_ref,
            workflow_report_ref=report_ref,
        )

    # Bind the actual producer bytes to the current exact view at this test
    # boundary. If the producer returned a legacy profileless ref, this does
    # not attest which manifest view the earlier producer selected.
    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        exact_simulation_ref = ArtifactRef.model_validate(
            profile_bound_ref(store, simulation_ref).model_dump(mode="python")
        )
        actual_bytes = store.get_bytes(exact_simulation_ref)
        actual_manifest = store.get_manifest(exact_simulation_ref)
        alternate_ref = store.put_bytes(
            actual_bytes,
            PutOptions(
                kind=exact_simulation_ref.kind,
                media_type=exact_simulation_ref.media_type,
                schema=actual_manifest.artifact_schema,
                producer=ProducerInfo(
                    component="polisyos.tests.res03.profile_adversary", version="1"
                ),
                tenant_context=actual_manifest.tenant_context,
            ),
            return_selected_profile=True,
        )
        assert store.verify(exact_simulation_ref).ok
        assert store.verify(alternate_ref).ok
        assert store.get_bytes(alternate_ref) == actual_bytes
    assert exact_simulation_ref.manifest_profile_sha256 is not None
    assert alternate_ref.artifact_id == exact_simulation_ref.artifact_id
    assert alternate_ref.manifest_profile_sha256 != exact_simulation_ref.manifest_profile_sha256

    exact_run = _run_rebound_to(exact_simulation_ref)
    conflicting_run = _run_rebound_to(exact_simulation_ref, node_ref_override=alternate_ref)
    candidate_url = f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
    selector_params = (None, {"artifact_id": str(exact_simulation_ref.artifact_id)})
    for params in selector_params:
        with patch.object(runtime_context.run_index, "get_run", return_value=exact_run):
            exact_response = client.get(candidate_url, params=params)
        assert exact_response.status_code == 200, exact_response.text
        exact_debug = exact_response.json()["debug"]
        assert ArtifactRef.model_validate(exact_debug["artifact_ref"]) == exact_simulation_ref
        assert exact_debug["authority_status"] == "non_authority"
    for params in selector_params:
        with patch.object(runtime_context.run_index, "get_run", return_value=conflicting_run):
            conflicting_response = client.get(candidate_url, params=params)
        assert conflicting_response.status_code == 409, conflicting_response.text
        assert conflicting_response.json()["code"] == "simulation_result_node_binding_mismatch"
        assert "debug" not in conflicting_response.json()

    # Remove only the profile portion of the binding check. The real served
    # consumer must then reveal the A/B escape with its success markers intact.
    from polisyos.runtime.http.services import debug as debug_service

    def identity_without_profile(
        expected: ArtifactRef, candidates: tuple[ArtifactRef, ...]
    ) -> None:
        expected_identity = (expected.artifact_id, expected.kind, expected.media_type)
        assert candidates and all(
            (candidate.artifact_id, candidate.kind, candidate.media_type) == expected_identity
            for candidate in candidates
        )

    with (
        patch.object(
            debug_service, "_require_exact_artifact_ref_binding", identity_without_profile
        ),
        patch.object(runtime_context.run_index, "get_run", return_value=conflicting_run),
    ):
        exposed_response = client.get(candidate_url)
    assert exposed_response.status_code == 200, exposed_response.text
    exposed = exposed_response.json()["debug"]
    assert ArtifactRef.model_validate(exposed["artifact_ref"]) == exact_simulation_ref
    assert exposed["projection_class"] == "candidate_reference_only"
    assert exposed["authority_status"] == "non_authority"
    assert exposed["integrity_status"] == "verified"

    unscoped_ref = store.put_json_unscoped(
        simulation_result.model_copy(
            update={"notes": [*simulation_result.notes, "RES-03 unscoped negative"]}
        ),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
        ),
    )
    foreign_ref = store.put_json_for_tenant(
        simulation_result.model_copy(
            update={"notes": [*simulation_result.notes, "RES-03 foreign-tenant negative"]}
        ),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
        ),
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        cell_id="cell-b",
    )
    _assert_fixture_ref_is_owned(
        foreign_ref,
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        cell_id="cell-b",
    )
    malformed_ref = store.put_json(
        {"schema_version": "1.3"},
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
        ),
    )
    wrong_schema_ref = store.put_json_for_tenant(
        simulation_result.model_copy(
            update={"notes": [*simulation_result.notes, "RES-03 schema negative"]}
        ),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="9.9"),
        ),
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
    )
    wrong_kind_ref = foreign_ref.model_copy(update={"kind": "wrong.artifact_kind"})
    wrong_media_ref = foreign_ref.model_copy(update={"media_type": "text/plain"})
    with pytest.raises(SimulationResultProjectionError) as unscoped_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(unscoped_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as foreign_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(foreign_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as malformed_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(malformed_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as wrong_schema_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(wrong_schema_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as wrong_kind_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(wrong_kind_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as wrong_media_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(wrong_media_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as stale_state_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(unscoped_ref, state_run_id="R_res03_stale"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as missing_state_error:
        _get_candidate_in_owner_scope(
            replace(_run_rebound_to(foreign_ref), experiment_state_ref=None),
            alias="run_simulation",
        )
    foreign_cell_state_run = _run_rebound_to(simulation_ref, state_cell_id="cell-foreign")
    _assert_fixture_ref_is_owned(
        foreign_cell_state_run.experiment_state_ref,
        tenant_id=_TENANT_ID,
        cell_id="cell-foreign",
    )
    with pytest.raises(SimulationResultProjectionError) as foreign_cell_state_error:
        _get_candidate_in_owner_scope(foreign_cell_state_run, alias="run_simulation")
    foreign_cell_report_run = _run_rebound_to(simulation_ref, report_cell_id="cell-foreign")
    _assert_fixture_ref_is_owned(
        foreign_cell_report_run.workflow_report_ref,
        tenant_id=_TENANT_ID,
        cell_id="cell-foreign",
    )
    with pytest.raises(SimulationResultProjectionError) as foreign_cell_report_error:
        _get_candidate_in_owner_scope(foreign_cell_report_run, alias="run_simulation")
    with pytest.raises(SimulationResultProjectionError) as unsupported_state_schema_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(simulation_ref, state_schema_version="9.9"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as unsupported_report_schema_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(simulation_ref, report_schema_version="9.9"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as state_ref_kind_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                state_ref_kind="wrong.binding_kind",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as report_ref_media_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                report_ref_media_type="text/plain",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as node_ref_kind_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                node_ref_kind="wrong.binding_kind",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as node_ref_media_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                node_ref_media_type="text/plain",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as mixed_node_ref_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                node_ref_conflicting_kind="wrong.binding_kind",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as state_payload_schema_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                state_payload_schema_version="9.9",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as report_payload_schema_error:
        _get_candidate_in_owner_scope(
            _run_rebound_to(
                simulation_ref,
                report_payload_schema_version="9.9",
            ),
            alias="run_simulation",
        )
    assert unscoped_error.value.code == "simulation_result_tenant_unscoped"
    # A correctly B-owned artifact is refused by A's CAS reader before the
    # projection service can inspect or disclose the foreign tenant manifest.
    assert foreign_error.value.code == "simulation_result_unavailable"
    assert malformed_error.value.code == "simulation_result_payload_invalid"
    assert wrong_schema_error.value.code == "simulation_result_schema_mismatch"
    assert wrong_kind_error.value.code == "simulation_result_ref_manifest_mismatch"
    assert wrong_media_error.value.code == "simulation_result_ref_manifest_mismatch"
    assert stale_state_error.value.code == "simulation_result_binding_run_mismatch"
    assert missing_state_error.value.code == "simulation_result_binding_missing"
    # Correctly scoped foreign-cell binding artifacts exist, but the run's A/cell-a
    # reader cannot load them through the ownership-enforcing CAS view.
    assert foreign_cell_state_error.value.code == "simulation_result_binding_unavailable"
    assert foreign_cell_report_error.value.code == "simulation_result_binding_unavailable"
    assert unsupported_state_schema_error.value.code == "simulation_result_binding_schema_mismatch"
    assert unsupported_report_schema_error.value.code == "simulation_result_binding_schema_mismatch"
    assert state_ref_kind_error.value.code == "simulation_result_binding_ref_mismatch"
    assert report_ref_media_error.value.code == "simulation_result_binding_ref_mismatch"
    assert node_ref_kind_error.value.code == "simulation_result_node_binding_mismatch"
    assert node_ref_media_error.value.code == "simulation_result_node_binding_mismatch"
    assert mixed_node_ref_error.value.code == "simulation_result_node_binding_mismatch"
    assert state_payload_schema_error.value.code == "simulation_result_binding_schema_mismatch"
    assert report_payload_schema_error.value.code == "simulation_result_binding_schema_mismatch"

    audit_path = store.root / "runtime" / "audit" / "access.jsonl"
    audit_entries = [
        json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(
        entry["resource_kind"] == "runtime.simulation_result_candidate"
        and entry["resource_id"].startswith(f"{run_id}:run_simulation:")
        for entry in audit_entries
    )

    assert run_details_response.status_code == 200, run_details_response.text
    run_details = run_details_response.json()["run"]
    assert run_details["run_id"] == run_id
    assert run_details["control_job_id"] == control_job_id
    # Preserve terminal failure; the completed simulation remains independently readable.
    assert run_details["status"] == "fail"
    assert run_details["has_workflow_report"] is True
    assert run_details["workflow_report_ref"]["artifact_id"] == str(workflow_report_ref.artifact_id)

    assert run_summaries_response.status_code == 200, run_summaries_response.text
    run_summaries = [
        summary for summary in run_summaries_response.json()["runs"] if summary["run_id"] == run_id
    ]
    assert len(run_summaries) == 1
    assert run_summaries[0]["status"] == "fail"
    assert run_summaries[0]["run_terminality"] == "terminal"

    assert workflow_response.status_code == 200, workflow_response.text
    workflow_payload = workflow_response.json()["workflow"]
    workflow_nodes = {node["alias"]: node for node in workflow_payload["nodes"]}
    summary = workflow_payload["summary"]
    assert summary["status"] == "fail"
    assert summary["ok_count"] >= 1
    assert summary["fail_count"] >= 1
    assert summary["skip_count"] >= 1
    assert summary["node_count"] == (
        summary["ok_count"] + summary["fail_count"] + summary["skip_count"]
    )
    assert workflow_nodes["run_simulation"]["status"] == "ok"
    assert str(simulation_ref.artifact_id) in workflow_nodes["run_simulation"]["artifact_ids"]
    assert workflow_nodes["later_failure"]["status"] == "fail"
    assert workflow_nodes["dependent_after_failure"]["status"] == "skip"
    assert workflow_nodes["dependent_after_failure"]["skip_reason"] == "upstream_failed"
    assert workflow_nodes["independent_sibling"]["status"] == "ok"

    assert errors_response.status_code == 200, errors_response.text
    route_errors = errors_response.json()["errors"]
    later_error = next(
        error for error in route_errors if error.get("node_alias") == "later_failure"
    )
    assert later_error["code"] == "res03.later_failure"
    assert later_error["details"]["scope"]["simulation_result_ref"] == str(
        simulation_ref.artifact_id
    )

    assert candidate_response.status_code == 200, candidate_response.text
    candidate_payload = candidate_response.json()["debug"]
    assert candidate_payload["run_id"] == run_id
    assert candidate_payload["node_alias"] == "run_simulation"
    assert candidate_payload["artifact_ref"]["artifact_id"] == str(simulation_ref.artifact_id)
    assert candidate_payload["projection_class"] == "candidate_reference_only"
    assert candidate_payload["authority_status"] == "non_authority"
    assert candidate_payload["integrity_status"] == "verified"
    assert candidate_payload["simulation_result"]["exec_plan_ref"]

    assert wrong_node_response.status_code == 409, wrong_node_response.text
    assert wrong_node_response.json()["code"] == "simulation_result_node_binding_missing"
    assert missing_node_response.status_code == 404, missing_node_response.text
    assert missing_node_response.json()["code"] == "simulation_result_node_not_found"
    assert wrong_ref_response.status_code == 409, wrong_ref_response.text
    assert wrong_ref_response.json()["code"] == "simulation_result_node_binding_mismatch"
    assert wrong_run_response.status_code == 404, wrong_run_response.text
    assert tampered_response.status_code == 409, tampered_response.text
    assert tampered_response.json()["code"] == "simulation_result_integrity_failed"
    assert binding_tampered_response.status_code == 409, binding_tampered_response.text
    assert binding_tampered_response.json()["code"] == (
        "simulation_result_binding_integrity_failed"
    )

    _assert_authority_surface_conflict(manifest_response)
    _assert_authority_surface_conflict(content_response)
    _assert_authority_surface_conflict(lineage_response)


def test_sql_dataframe_source_binds_into_a_real_foundry_state(tmp_path) -> None:
    """Trace a controlled SQL request through CAS into Foundry's binding consumer."""
    db_path = tmp_path / "policy-inputs.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE policy_inputs (income REAL NOT NULL, note TEXT)")
        connection.executemany(
            "INSERT INTO policy_inputs VALUES (?, ?)",
            [(12.5, "first"), (25.0, None)],
        )

    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{db_path}",
            headers={"X-SQL-Table": "policy_inputs"},
        ),
    )
    store = FileSystemCAS(tmp_path / "cas")
    request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="res03_controlled_sql_inputs",
            view_type="table",
            metrics=["policy_inputs"],
        ),
        PutOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    data_view_request_ref = DataViewRequestRef.model_validate(
        profile_bound_ref(store, request_ref).model_dump(mode="python")
    )
    try:
        data_snapshot_ref = DefaultFabricPort(connector_registry=registry).snapshot(
            store,
            data_view_request_ref,
        )
    finally:
        registry.shutdown()

    snapshot = DataSnapshot.model_validate(from_canonical_bytes(store.get_bytes(data_snapshot_ref)))
    records = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
    snapshot_manifest = store.get_manifest(data_snapshot_ref)
    request_edges = [
        edge for edge in snapshot_manifest.inputs if edge.role == "data_view_request_ref"
    ]
    assert records == [
        {"income": 12.5, "note": "first"},
        {"income": 25.0, "note": None},
    ]
    assert data_snapshot_ref.manifest_profile_sha256 is not None
    assert len(request_edges) == 1
    assert request_edges[0].artifact_id == data_view_request_ref.artifact_id
    assert request_edges[0].manifest_profile_sha256 == data_view_request_ref.manifest_profile_sha256

    registry_bundle = build_default_registry_bundle(store)
    built = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle.bundle_ref,
        rules=[
            FoundryInputBindingRule(
                binding_id="res03.sql_income",
                source_path="income",
                target_slot_id="agents.income",
                required=True,
            )
        ],
    )
    foundry_state = load_state_snapshot(store, snapshot_ref=built.bound_state_snapshot_ref)
    assert foundry_state.agents.income.tolist() == [12.5, 25.0]
