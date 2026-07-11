"""Public compile formalize verified policy module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.nodes.builtins.state_keys import INPUT_TRINITY_BUNDLE_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.service import (
    POLICY_VERIFIED_HARDCODED_FORMALIZER_STRANGLED,
)

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
        "artifacts_index",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
    ],
    state_writes=[],
    produces=[INPUT_TRINITY_BUNDLE_REF],
)


@dataclass(frozen=True)
class FormalizeVerifiedPolicyNode:
    """Require a caller-supplied Trinity bundle for verified-policy compilation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        if INPUT_TRINITY_BUNDLE_REF in state.inputs:
            return NodeOutcome(status="ok", state=state)
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code=POLICY_VERIFIED_HARDCODED_FORMALIZER_STRANGLED,
                message="Verified-policy compilation requires a supplied real Trinity bundle.",
                details={"required": [INPUT_TRINITY_BUNDLE_REF]},
            ),
        )


__all__ = ["FormalizeVerifiedPolicyNode"]
