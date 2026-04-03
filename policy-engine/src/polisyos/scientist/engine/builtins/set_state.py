"""Public builtins set state module API."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState, JsonScalar

_SET_STATE_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_set_state@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Set state",
    description="Set a key in ExperimentState.params.",
    tags=["builtin"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SET_STATE_SPEC = NodeSpec(
    metadata=_SET_STATE_METADATA,
    state_writes=["params"],
)

_ALLOWED_TYPES = (str, int, bool, Decimal)


@dataclass(frozen=True)
class SetStateNode:
    """Set state node implementation."""
    params: dict[str, JsonScalar] | None = None

    @property
    def spec(self) -> NodeSpec:
        return _SET_STATE_SPEC

    def bind(self, params: dict[str, JsonScalar]) -> "SetStateNode":
        return SetStateNode(params=params)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        params = self.params or {}
        key = params.get("key")
        value = params.get("value")
        if not isinstance(key, str):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="node.params",
                    message="set_state requires string param 'key'",
                ),
            )
        if not isinstance(value, _ALLOWED_TYPES):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="node.params",
                    message="set_state requires scalar param 'value'",
                ),
            )
        new_state = state.model_copy(deep=True)
        new_state.params[key] = value
        return NodeOutcome(status="ok", state=new_state)
