from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    PolicyOptionSetRef,
    PolicyRequestFrameRef,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_verified import (
    load_policy_option_set,
    load_policy_request_frame,
)
from polisyos.scientist.policy_verified.service import formalize_policy_option_set

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_formalize_verified_policy@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Formalize Verified Policy",
    description="Formalize verified policy options into a Trinity bundle for downstream Foundry execution.",
    tags=["builtin", "compile", "policy_verified"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "policy_request_ref",
        "policy_option_set_ref",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
    ],
    state_writes=[f"inputs.{INPUT_TRINITY_BUNDLE_REF}"],
    produces=[INPUT_TRINITY_BUNDLE_REF],
)


@dataclass(frozen=True)
class FormalizeVerifiedPolicyNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if INPUT_TRINITY_BUNDLE_REF in state.inputs:
            return NodeOutcome(status="ok", state=state)
        request_ref = state.policy_request_ref or state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF)
        option_ref = state.policy_option_set_ref or state.artifacts_index.get(ARTIFACT_POLICY_OPTION_SET_REF)
        if request_ref is None or option_ref is None:
            return NodeOutcome(status="skip", state=state)
        frame = load_policy_request_frame(ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump()))
        option_set = load_policy_option_set(
            ctx.store, PolicyOptionSetRef.model_validate(option_ref.model_dump())
        )
        trinity_ref = formalize_policy_option_set(ctx, state, frame, option_set)
        if trinity_ref is None:
            return NodeOutcome(status="skip", state=state)
        new_state = state.model_copy(deep=True)
        new_state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref
        new_state.params["policy_trinity_generated"] = True
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[trinity_ref],
            events=[NodeEvent(level="info", message="Verified policy formalized into Trinity bundle.")],
        )


__all__ = ["FormalizeVerifiedPolicyNode"]
