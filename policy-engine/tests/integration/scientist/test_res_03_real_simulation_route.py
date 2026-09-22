"""RES-03 B13 witness for the real simulation-to-user read path."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.services.debug import SimulationResultProjectionError
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_SIMULATION_RESULT_REF
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

pytestmark = pytest.mark.integration

_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL_ID = "cell-a"


class _TenantScopedCAS(FileSystemCAS):
    """Make this real-route witness persist explicit tenant-scoped manifests."""

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        if opts.tenant_context is None:
            opts = replace(
                opts,
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=_TENANT_ID,
                    cell_id=_CELL_ID,
                ),
            )
        return super().put_json(obj, opts, canon_spec)

    def put_json_unscoped(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Persist an intentionally unscoped negative fixture."""
        return super().put_json(obj, opts, canon_spec)

    def put_json_for_tenant(
        self,
        obj: object,
        opts: PutOptions,
        *,
        tenant_id: str,
        cell_id: str | None,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Persist a fixture with a deliberately foreign manifest tenant."""
        return super().put_json(
            obj,
            replace(
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
    payload = response.json()
    assert payload["code"] == "authority_surface_admission_blocked"
    decision = payload["authority_surface_decision"]
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


def _put_data_snapshot(
    store: FileSystemCAS,
    state_snapshot_ref: StateSnapshotRef,
) -> DataSnapshotRef:
    snapshot = DataSnapshot(data_ref=state_snapshot_ref)
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    return DataSnapshotRef(artifact_id=ref.artifact_id)


def _build_real_trinity(store: FileSystemCAS, registry_bundle_ref: Any) -> Any:
    base_state = GlobalState.empty(n_agents=5, n_firms=2)
    snapshot_payload = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_payload.artifact_id)
    data_snapshot_ref = _put_data_snapshot(store, state_snapshot_ref)

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
    return trinity, data_snapshot_ref


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
    # The bounded witness exercises CompileFoundryNode's real strict linker.
    # The standalone LinkTrinityNode is omitted because both nodes persist the
    # same deterministic report with incompatible CAS input-role profiles; the
    # default-workflow ownership conflict is tracked separately from RES-03.
    selected = [
        (
            node.model_copy(
                update={
                    "depends_on": [
                        dependency
                        for dependency in node.depends_on
                        if dependency != "link_trinity"
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


def test_res_03_real_simulation_later_failure_reaches_user_route(tmp_path) -> None:
    """Persist a real simulation, then expose the later failure and invalidation."""
    store = _TenantScopedCAS(tmp_path / "cas", tenant_id=_TENANT_ID, cell_id=_CELL_ID)
    run_id = "R_res03_real_route"

    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        registry_bundle = build_default_registry_bundle(store)
        trinity, data_snapshot_ref = _build_real_trinity(store, registry_bundle.bundle_ref)
        trinity_ref = store.put_json(
            trinity,
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.TrinityBundle",
                    version=trinity.schema_version,
                ),
            ),
        )
        state = ExperimentState(
            run_id=run_id,
            inputs={
                "trinity_bundle_ref": trinity_ref,
                "registry_bundle_ref": registry_bundle.bundle_ref,
                "data_snapshot_ref": data_snapshot_ref,
            },
            params={
                # The state-snapshot compatibility path loads the source state
                # verbatim.  Bind one real slot so the persisted bound snapshot
                # has distinct bytes before CAS adds its input lineage profile.
                "foundry_input_binding_rules": [
                    FoundryInputBindingRule(
                        binding_id="res03.fixture_tax_rate",
                        source_path="fixture.tax_rate",
                        target_slot_id="global.tax_rate",
                        default_value=Decimal("0.1"),
                        notes=["test fixture makes bound snapshot distinct"],
                    )
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
        result = WorkflowExecutor(ctx, registry).execute(_build_workflow(), state)

    records = {record.alias: record for record in result.report.nodes}
    simulation_ref = result.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    simulation_manifest = store.get_manifest(simulation_ref.artifact_id)
    simulation_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(simulation_ref.artifact_id))
    )

    assert result.report.status == "fail"
    assert simulation_result.exec_plan_ref is not None
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
    assert later_failure.seen_simulation_ref == simulation_ref
    assert independent.seen_simulation_ref == simulation_ref
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

    app = create_runtime_api_app(
        cas_root=store.root,
        core_runs_root=store.root / "runs",
        allow_unscoped_artifacts=True,
        allow_fixture_identity=True,
        enable_security_middlewares=False,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        workflow_response = client.get(f"/api/v1/runs/{run_id}/workflow")
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

        blob_path, _manifest_path = store.get_paths(simulation_ref.artifact_id)
        original_bytes = blob_path.read_bytes()
        blob_path.write_bytes(original_bytes + b"tampered")
        try:
            tampered_response = client.get(
                f"/api/v1/debug/runs/{run_id}/nodes/run_simulation/simulation-result"
            )
        finally:
            blob_path.write_bytes(original_bytes)

        workflow_report_ref = result.state.reports_index["workflow_report"]
        report_blob_path, _report_manifest_path = store.get_paths(
            workflow_report_ref.artifact_id
        )
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
    ) -> Any:
        rebound_state = result.state.model_copy(update={"run_id": state_run_id}, deep=True)
        rebound_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = candidate_ref
        state_payload = (
            rebound_state.model_copy(
                update={"schema_version": state_payload_schema_version}
            )
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
                rebound_nodes.append(node)
                continue
            node_artifacts = [
                candidate_ref
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
            rebound_nodes.append(
                node.model_copy(
                    update={
                        "artifacts": node_artifacts
                    }
                )
            )
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
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(unscoped_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as foreign_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(foreign_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as malformed_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(malformed_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as wrong_schema_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(wrong_schema_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as wrong_kind_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(wrong_kind_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as wrong_media_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(wrong_media_ref),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as stale_state_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(unscoped_ref, state_run_id="R_res03_stale"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as missing_state_error:
        runtime_context.debug.get_simulation_result_candidate(
            replace(_run_rebound_to(foreign_ref), experiment_state_ref=None),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as foreign_cell_state_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(simulation_ref, state_cell_id="cell-foreign"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as foreign_cell_report_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(simulation_ref, report_cell_id="cell-foreign"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as unsupported_state_schema_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(simulation_ref, state_schema_version="9.9"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as unsupported_report_schema_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(simulation_ref, report_schema_version="9.9"),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as state_ref_kind_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(
                simulation_ref,
                state_ref_kind="wrong.binding_kind",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as report_ref_media_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(
                simulation_ref,
                report_ref_media_type="text/plain",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as node_ref_kind_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(
                simulation_ref,
                node_ref_kind="wrong.binding_kind",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as node_ref_media_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(
                simulation_ref,
                node_ref_media_type="text/plain",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as state_payload_schema_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(
                simulation_ref,
                state_payload_schema_version="9.9",
            ),
            alias="run_simulation",
        )
    with pytest.raises(SimulationResultProjectionError) as report_payload_schema_error:
        runtime_context.debug.get_simulation_result_candidate(
            _run_rebound_to(
                simulation_ref,
                report_payload_schema_version="9.9",
            ),
            alias="run_simulation",
        )
    assert unscoped_error.value.code == "simulation_result_tenant_unscoped"
    assert foreign_error.value.code == "simulation_result_tenant_binding_mismatch"
    assert malformed_error.value.code == "simulation_result_payload_invalid"
    assert wrong_schema_error.value.code == "simulation_result_schema_mismatch"
    assert wrong_kind_error.value.code == "simulation_result_ref_manifest_mismatch"
    assert wrong_media_error.value.code == "simulation_result_ref_manifest_mismatch"
    assert stale_state_error.value.code == "simulation_result_binding_run_mismatch"
    assert missing_state_error.value.code == "simulation_result_binding_missing"
    assert foreign_cell_state_error.value.code == "simulation_result_binding_tenant_mismatch"
    assert foreign_cell_report_error.value.code == "simulation_result_binding_tenant_mismatch"
    assert (
        unsupported_state_schema_error.value.code
        == "simulation_result_binding_schema_mismatch"
    )
    assert (
        unsupported_report_schema_error.value.code
        == "simulation_result_binding_schema_mismatch"
    )
    assert state_ref_kind_error.value.code == "simulation_result_binding_ref_mismatch"
    assert report_ref_media_error.value.code == "simulation_result_binding_ref_mismatch"
    assert node_ref_kind_error.value.code == "simulation_result_node_binding_mismatch"
    assert node_ref_media_error.value.code == "simulation_result_node_binding_mismatch"
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

    assert workflow_response.status_code == 200, workflow_response.text
    workflow_nodes = {node["alias"]: node for node in workflow_response.json()["workflow"]["nodes"]}
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
