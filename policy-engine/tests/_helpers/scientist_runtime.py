from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.feedback.core import (
    DecisionFeedbackService,
    build_monitoring_contract_from_packet,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService

_WORKFLOW_ID = "scientist_reliability_chain"
_NODE_IDS = {
    "agent": "scientist.test_agent@1.0.0",
    "search": "scientist.test_search@1.0.0",
    "simulation": "scientist.test_simulation@1.0.0",
    "governance": "scientist.test_governance@1.0.0",
    "decision": "scientist.test_decision@1.0.0",
}
_BASELINE_SIMULATION_RESULTS = {
    "policy_cost": 100.0,
    "group_fairness_gap": 0.02,
    "rmse_holdout": 1.0,
}
_BASELINE_BACKTEST = {
    "overall_mae": 0.001,
    "overall_rmse": 0.002,
    "prediction_mode_effective": "holdout",
    "trust_eligible": True,
}


def put_rows_data_snapshot(
    store: FileSystemCAS,
    rows: Sequence[Mapping[str, Any]],
) -> DataSnapshotRef:
    data_ref = store.put_json(
        {"rows": [dict(item) for item in rows]},
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="foundry.state_snapshot", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    snapshot = DataSnapshot(data_ref=StateSnapshotRef(artifact_id=data_ref.artifact_id))
    snapshot_ref = store.put_json(
        snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    return DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)


def build_execution_context(
    store: FileSystemCAS,
    *,
    run_id: str,
) -> tuple[ExecutionContext, Any]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"scientist.runtime.{run_id}"),
    )
    return ctx, bundle.bundle_ref


def build_initial_state(
    store: FileSystemCAS,
    *,
    run_id: str,
    registry_bundle_ref: Any,
    actual_rows: Sequence[Mapping[str, Any]],
) -> ExperimentState:
    data_snapshot_ref = put_rows_data_snapshot(store, actual_rows)
    return ExperimentState(
        run_id=run_id,
        inputs={
            "registry_bundle_ref": registry_bundle_ref,
            "data_snapshot_ref": data_snapshot_ref,
        },
        params={"question": "How should we redesign the policy?"},
    )


def default_actual_rows() -> list[dict[str, float]]:
    return [
        {
            "policy_cost": 102.0,
            "group_fairness_gap": 0.025,
            "rmse_holdout": 1.01,
        }
    ]


def regression_actual_rows() -> list[dict[str, float]]:
    return [
        {
            "policy_cost": 145.0,
            "group_fairness_gap": 0.25,
            "rmse_holdout": 4.5,
        }
    ]


def build_linear_workflow_spec(
    *,
    search_retry: int = 0,
    error_policy: str = "fail_fast",
) -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id=_WORKFLOW_ID,
        error_policy=error_policy,
        nodes=[
            NodeInvocation(alias="agent", node_id=ComponentId.parse(_NODE_IDS["agent"])),
            NodeInvocation(
                alias="search",
                node_id=ComponentId.parse(_NODE_IDS["search"]),
                depends_on=["agent"],
                retry=RetryPolicy(max_retries=search_retry, backoff_base_s=0.1, jitter="none")
                if search_retry
                else None,
            ),
            NodeInvocation(
                alias="simulation",
                node_id=ComponentId.parse(_NODE_IDS["simulation"]),
                depends_on=["search"],
            ),
            NodeInvocation(
                alias="governance",
                node_id=ComponentId.parse(_NODE_IDS["governance"]),
                depends_on=["simulation"],
            ),
            NodeInvocation(
                alias="decision",
                node_id=ComponentId.parse(_NODE_IDS["decision"]),
                depends_on=["governance"],
            ),
        ],
    )


def load_json_artifact(store: FileSystemCAS, artifact_id: str) -> dict[str, Any]:
    payload = from_canonical_bytes(store.get_bytes(ArtifactID.model_validate(artifact_id)))
    if not isinstance(payload, dict):
        raise TypeError(f"artifact {artifact_id} did not decode to an object")
    return payload


def build_linear_registry(
    store: FileSystemCAS,
    *,
    governance_mode: str = "approve",
    search_failures: int = 0,
    decision_failures: int = 0,
) -> tuple[NodeRegistry, dict[str, ScenarioNode]]:
    feedback_service = DecisionFeedbackService(store)
    validity_service = DecisionValidityService(store)
    registry = NodeRegistry()

    def _agent_handler(
        node: ScenarioNode,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        del node, ctx
        new_state = state.model_copy(deep=True)
        new_state.params["agent_draft"] = "draft_ready"
        return NodeOutcome(status="ok", state=new_state)

    def _search_handler(
        node: ScenarioNode,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        del ctx
        if node.calls <= search_failures:
            raise TimeoutError("simulated search tool timeout")
        new_state = state.model_copy(deep=True)
        new_state.params["search_evidence_count"] = 3
        new_state.params["search_summary"] = "evidence gathered"
        return NodeOutcome(status="ok", state=new_state)

    def _simulation_handler(
        node: ScenarioNode,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        del node, ctx
        new_state = state.model_copy(deep=True)
        new_state.params["simulation_results"] = dict(_BASELINE_SIMULATION_RESULTS)
        new_state.params["backtest"] = dict(_BASELINE_BACKTEST)
        return NodeOutcome(status="ok", state=new_state)

    def _governance_handler(
        node: ScenarioNode,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        del node, ctx
        if governance_mode == "reject":
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="governance.reject",
                    message="governance rejected publication",
                ),
            )
        new_state = state.model_copy(deep=True)
        new_state.params["governance_status"] = "approved"
        return NodeOutcome(status="ok", state=new_state)

    def _decision_handler(
        node: ScenarioNode,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        if node.calls <= decision_failures:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="node.decision_transient",
                    message="transient decision publication failure",
                ),
            )

        new_state = state.model_copy(deep=True)
        data_snapshot_ref = _artifact_id(state.inputs.get("data_snapshot_ref"))
        simulation_results = dict(
            state.params.get("simulation_results") or _BASELINE_SIMULATION_RESULTS
        )
        backtest = dict(state.params.get("backtest") or _BASELINE_BACKTEST)
        packet_payload = {
            "schema_version": "3.4",
            "workflow_id": _WORKFLOW_ID,
            "run_id": state.run_id,
            "simulation_results": simulation_results,
            "backtest": backtest,
            "inputs": {"data_snapshot_ref": data_snapshot_ref},
            "governance": {"status": str(state.params.get("governance_status") or "unknown")},
        }

        contract = build_monitoring_contract_from_packet(
            run_id=state.run_id,
            decision_lineage_key=f"lineage::{state.run_id}",
            anchor_at=ctx.run.run_manifest.started_at,
            packet_payload=packet_payload,
        )
        if contract is None:
            raise AssertionError("monitoring contract must be materialized for the decision packet")
        contract_ref = feedback_service.persist_monitoring_contract(contract)
        packet_payload["feedback_loop"] = {"monitoring_contract_ref": contract_ref}

        packet_ref = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(name="scientist.decision_packet", version="3.4"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        envelope = DecisionValidityEnvelope(
            decision_lineage_key=f"lineage::{state.run_id}",
            policy_fingerprint=f"policy::{state.run_id}",
            data_basis=DecisionBasisSection(
                dependencies=[
                    DecisionDependencyRef(
                        kind=DecisionDependencyKind.DATASET,
                        key=f"dataset::{state.run_id}",
                        artifact_id=data_snapshot_ref,
                        label="fixture dataset",
                    )
                ]
            ),
        )
        baseline = DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=DecisionValidityStatus.ACTIVE,
            dependency_keys=envelope.dependency_keys(),
        )
        validity_service.register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=envelope,
            baseline=baseline,
            monitoring_contract_ref=contract_ref,
        )

        new_state.artifacts_index["decision_packet_ref"] = packet_ref
        new_state.params["decision_packet_ref"] = str(packet_ref.artifact_id)
        new_state.params["monitoring_contract_ref"] = contract_ref
        return NodeOutcome(status="ok", state=new_state)

    nodes = {
        "agent": ScenarioNode(
            raw_component_id=_NODE_IDS["agent"],
            display_name="Agent",
            handler=_agent_handler,
            state_writes=["params.agent_draft"],
        ),
        "search": ScenarioNode(
            raw_component_id=_NODE_IDS["search"],
            display_name="Search",
            handler=_search_handler,
            state_reads=["params.agent_draft"],
            state_writes=["params.search_evidence_count", "params.search_summary"],
        ),
        "simulation": ScenarioNode(
            raw_component_id=_NODE_IDS["simulation"],
            display_name="Simulation",
            handler=_simulation_handler,
            state_reads=["params.search_evidence_count"],
            state_writes=["params.simulation_results", "params.backtest"],
        ),
        "governance": ScenarioNode(
            raw_component_id=_NODE_IDS["governance"],
            display_name="Governance",
            handler=_governance_handler,
            state_reads=["params.simulation_results"],
            state_writes=["params.governance_status"],
        ),
        "decision": ScenarioNode(
            raw_component_id=_NODE_IDS["decision"],
            display_name="Decision",
            handler=_decision_handler,
            state_reads=[
                "params.simulation_results",
                "params.governance_status",
                "inputs.data_snapshot_ref",
            ],
            state_writes=[
                "artifacts_index",
                "params.decision_packet_ref",
                "params.monitoring_contract_ref",
            ],
        ),
    }
    for node in nodes.values():
        registry.register(node)
    return registry, nodes


def _artifact_id(value: Any) -> str:
    artifact_id = getattr(value, "artifact_id", value)
    return str(artifact_id)


def _meta(raw_component_id: str, display_name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw_component_id),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=display_name,
        description=f"{display_name} fixture node",
        tags=["test", "scientist"],
        capabilities=Capability.SCIENTIST_NODE,
    )


@dataclass
class ScenarioNode:
    raw_component_id: str
    display_name: str
    handler: Callable[[ScenarioNode, ExecutionContext, ExperimentState], NodeOutcome]
    state_reads: list[str] | None = None
    state_writes: list[str] | None = None
    calls: int = 0

    def __post_init__(self) -> None:
        self._spec = NodeSpec(
            metadata=_meta(self.raw_component_id, self.display_name),
            state_reads=list(self.state_reads or []),
            state_writes=list(self.state_writes or []),
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        return self.handler(self, ctx, state)
