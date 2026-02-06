from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.scientist import DecisionPacketRef
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

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.0.1"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Decision Packet",
    description="Create the DecisionPacket artifact from available reports and metrics.",
    tags=["builtin", "decide"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=["run_id", "params", "reports_index", "artifacts_index"],
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
        packet_payload: dict[str, object] = {
            "schema_version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": state.run_id,
            "run_record": {
                "schema_version": "2.0",
                "run_id": state.run_id,
                "seed": seed,
                "engine": "scientist.engine",
            },
            "simulation_results": None,
            "governance": None,
            "artifacts": {},
            "notes": [],
        }

        metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
        if metrics_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
                metrics = Metrics.model_validate(payload)
                packet_payload["simulation_results"] = dict(metrics.values)
                packet_payload["artifacts"] = {
                    **dict(packet_payload["artifacts"]),
                    "metrics_ref": str(metrics_ref.artifact_id),
                }
            except Exception:
                packet_payload["simulation_results"] = None

        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(governance_ref.artifact_id))
                report = GovernanceReport.model_validate(payload)
                packet_payload["governance"] = {
                    "verdict": report.verdict,
                    "issues": report.issues,
                    "notes": report.notes,
                }
                packet_payload["artifacts"] = {
                    **dict(packet_payload["artifacts"]),
                    "governance_report_ref": str(governance_ref.artifact_id),
                }
            except Exception:
                packet_payload["governance"] = None

        inputs: list[InputRef] = []
        if metrics_ref is not None:
            inputs.append(InputRef(artifact_id=metrics_ref.artifact_id, role="metrics"))
        if governance_ref is not None:
            inputs.append(InputRef(artifact_id=governance_ref.artifact_id, role="governance_report"))

        packet_ref_payload = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version="2.0",
                ),
                inputs=inputs or None,
            ),
        )
        packet_ref = DecisionPacketRef(artifact_id=packet_ref_payload.artifact_id)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref

        return NodeOutcome(status="ok", state=new_state, artifacts=[packet_ref])
