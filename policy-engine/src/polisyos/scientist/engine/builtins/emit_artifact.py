"""Public builtins emit artifact module API."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState

_EMIT_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_emit_artifact@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Emit artifact",
    description="Emit a dummy JSON artifact into CAS.",
    tags=["builtin"],
    capabilities=Capability.SCIENTIST_NODE,
)

_EMIT_SPEC = NodeSpec(
    metadata=_EMIT_METADATA,
    state_writes=["artifacts_index"],
    produces=["artifact"],
)


@dataclass(frozen=True)
class EmitArtifactNode:
    """Bootstrap node that writes a JSON payload to CAS and records its ref in `artifacts_index`."""
    params: dict[str, object] | None = None

    @property
    def spec(self) -> NodeSpec:
        return _EMIT_SPEC

    def bind(self, params: dict[str, object]) -> "EmitArtifactNode":
        return EmitArtifactNode(params=params)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        params = self.params or {}
        key = params.get("key")
        payload = params.get("payload")
        if not isinstance(key, str):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="node.params",
                    message="emit_artifact requires string param 'key'",
                ),
            )
        if not isinstance(payload, dict):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="node.params",
                    message="emit_artifact requires dict param 'payload'",
                ),
            )
        ref = ctx.store.put_json(
            payload,
            PutOptions(kind="scientist.builtin.dummy", media_type="application/json"),
        )
        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[key] = ref
        return NodeOutcome(status="ok", state=new_state, artifacts=[ref])
