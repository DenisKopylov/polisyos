"""RES-03 B13 witness for the real simulation-to-user read path."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
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
    store = FileSystemCAS(tmp_path / "cas")
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
        manifest_response = client.get(f"/api/v1/artifacts/{simulation_ref.artifact_id}")
        content_response = client.get(f"/api/v1/artifacts/{simulation_ref.artifact_id}/content")
        lineage_response = client.get(f"/api/v1/artifacts/{simulation_ref.artifact_id}/lineage")

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

    assert manifest_response.status_code == 200, manifest_response.text
    manifest_view = manifest_response.json()["artifact"]
    assert manifest_view["kind"] == "foundry.simulation_result"
    assert {item["role"] for item in manifest_view["inputs"]} >= {
        "exec_plan",
        "input.data_snapshot_ref",
    }

    assert content_response.status_code == 200, content_response.text
    content_preview = content_response.json()["artifact"]["preview"]
    assert content_preview["exec_plan_ref"]
    assert content_preview["state_snapshot_ref"]

    assert lineage_response.status_code == 200, lineage_response.text
    lineage = lineage_response.json()["lineage"]
    assert lineage["is_complete"] is True
    lineage_roles = {
        *(node["role"] for node in lineage["nodes"] if node.get("role") is not None),
        *(edge["role"] for edge in lineage["edges"]),
    }
    assert {"exec_plan", "input.data_snapshot_ref"} <= lineage_roles
