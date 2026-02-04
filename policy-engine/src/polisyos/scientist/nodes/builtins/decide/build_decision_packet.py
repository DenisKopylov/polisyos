from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.scientist import DecisionPacketRef, GovernanceReportRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_METRICS_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestrator.decision_packet import build_decision_packet
from polisyos.scientist.orchestrator.run_record import build_run_record

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Decision Packet",
    description="Create the DecisionPacket artifact from available reports and metrics.",
    tags=["builtin", "decide"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=["params", "reports_index", "artifacts_index"],
    state_writes=[f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}"],
    produces=[ARTIFACT_DECISION_PACKET_REF],
)


@dataclass(frozen=True)
class BuildDecisionPacketNode:
    """Build a DecisionPacket from the engine state."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        seed = int(state.params.get("random_seed", 0) or 0)
        run_record = build_run_record(run_id=state.run_id, seed=seed)

        legacy_state: dict[str, Any] = {
            "run_id": state.run_id,
            "ir": None,
            "simulation_results": None,
            "feedback": None,
            "audit_trail": [],
            "validation_trace": None,
        }

        metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
        if metrics_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
                metrics = Metrics.model_validate(payload)
                legacy_state["simulation_results"] = dict(metrics.values)
            except Exception:
                legacy_state["simulation_results"] = None

        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(governance_ref.artifact_id))
                report = GovernanceReport.model_validate(payload)
                legacy_state["feedback"] = {
                    "verdict": report.verdict.upper(),
                    "issues": report.issues,
                }
            except Exception:
                legacy_state["feedback"] = None

        packet = build_decision_packet(legacy_state, run_record, include_card=True)
        if governance_ref is not None:
            packet.governance_report_ref = GovernanceReportRef.model_validate(
                governance_ref.model_dump()
            )

        inputs: list[InputRef] = []
        if metrics_ref is not None:
            inputs.append(InputRef(artifact_id=metrics_ref.artifact_id, role="metrics"))
        if governance_ref is not None:
            inputs.append(InputRef(artifact_id=governance_ref.artifact_id, role="governance_report"))

        packet_ref_payload = ctx.store.put_json(
            packet,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version=packet.schema_version,
                ),
                inputs=inputs or None,
            ),
        )
        packet_ref = DecisionPacketRef(artifact_id=packet_ref_payload.artifact_id)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref

        return NodeOutcome(status="ok", state=new_state, artifacts=[packet_ref])
