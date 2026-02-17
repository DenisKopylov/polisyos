from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_ready_to_run@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Ready To Run Gate",
    description="Hard gate that blocks execute stage when preflight is not ready.",
    tags=["builtin", "planning", "gate"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=["params.preflight_ready", "params.preflight_diagnostics"],
    state_writes=[],
    produces=[],
)


@dataclass(frozen=True)
class ReadyToRunNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        ready = bool(state.params.get("preflight_ready"))
        if ready:
            return NodeOutcome(
                status="ok",
                state=state,
                events=[NodeEvent(level="info", message="Ready-to-run gate passed")],
            )
        diagnostics = state.params.get("preflight_diagnostics")
        error = NodeError(
            code=node_errors.ERROR_INVALID_STATE,
            message="Ready-to-run gate blocked execute stage",
            details={"preflight_diagnostics": diagnostics if isinstance(diagnostics, list) else []},
        )
        return NodeOutcome(
            status="fail",
            state=state,
            events=[NodeEvent(level="error", message="Ready-to-run gate blocked workflow")],
            error=error,
        )


__all__ = ["ReadyToRunNode"]
