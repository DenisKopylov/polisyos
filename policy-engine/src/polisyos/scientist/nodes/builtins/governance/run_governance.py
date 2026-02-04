from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import GovernanceReportRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_governance@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Governance",
    description="Evaluate governance gates and emit GovernanceReport.",
    tags=["builtin", "governance"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=["params"],
    state_writes=[f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}"],
    produces=[REPORT_GOVERNANCE_REPORT_REF],
)


@dataclass(frozen=True)
class RunGovernanceNode:
    """Minimal governance node for E1.7 happy path."""

    default_verdict: Literal["approve", "needs_revision", "reject", "human_gate"] = "approve"

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "RunGovernanceNode":
        if not params:
            return self
        verdict = params.get("default_verdict", self.default_verdict)
        return replace(self, default_verdict=str(verdict))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        verdict = self.default_verdict
        issues: list[dict[str, Any]] = []

        require_human_gate = bool(state.params.get("require_human_gate"))
        gate_decision = state.params.get("gate_decision")
        if require_human_gate and gate_decision is None:
            verdict = "human_gate"
        elif isinstance(gate_decision, str):
            if gate_decision.lower() in {"reject", "rejected", "deny", "denied"}:
                verdict = "reject"
            elif gate_decision.lower() in {"approve", "approved", "allow"}:
                verdict = "approve"

        report = GovernanceReport(verdict=verdict, issues=issues)
        report_ref_payload = ctx.store.put_json(
            report,
            PutOptions(
                kind="scientist.governance_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.GovernanceReport",
                    version=report.schema_version,
                ),
            ),
        )
        report_ref = GovernanceReportRef(artifact_id=report_ref_payload.artifact_id)

        new_state = state.model_copy(deep=True)
        new_state.reports_index[REPORT_GOVERNANCE_REPORT_REF] = report_ref

        event = NodeEvent(level="info", message=f"Governance verdict: {verdict}")
        return NodeOutcome(status="ok", state=new_state, artifacts=[report_ref], events=[event])
