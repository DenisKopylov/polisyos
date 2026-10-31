"""Public planning plan policy request module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.methods.research_dag.projections import RESEARCH_DAG_FEATURE_FLAG
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    INPUT_RESEARCH_INTENT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.validation.policy_verified import (
    persist_policy_request_frame,
)
from polisyos.scientist.validation.policy_verified.service import (
    build_policy_request_frame,
    policy_request_scope_reason,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_plan_policy_request@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Plan Policy Request",
    description="Create the typed policy request frame for verified Scientist mode.",
    tags=["builtin", "planning", "policy_verified"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    # The legacy producer receives the complete state maps; preserve that
    # actual basis until it is moved to a physically restricted input port.
    state_reads=["run_id", "execution_profile", "inputs", "params", "artifacts_index"],
    state_writes=[
        "policy_request_ref",
        f"artifacts_index.{ARTIFACT_POLICY_REQUEST_FRAME_REF}",
        "params.policy_answer_mode",
        "execution_profile",
    ],
    produces=[ARTIFACT_POLICY_REQUEST_FRAME_REF],
)


@dataclass(frozen=True)
class PlanPolicyRequestNode:
    """Planning entrypoint that normalizes request params into a persisted policy request frame.

    Reads policy-question inputs and jurisdiction hints, writes `policy_request_ref`,
    the request-frame artifact ref, `params.policy_answer_mode`, and the verified
    execution profile consumed by downstream sourcing nodes.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        frame = build_policy_request_frame(ctx, state)
        reason = policy_request_scope_reason(frame)
        if reason is not None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code=reason, message="Policy request scope is not established."),
            )
        intent_ref = state.inputs.get(INPUT_RESEARCH_INTENT_REF)
        inputs = (
            [input_ref_from_artifact_ref(intent_ref, role="research_intent")]
            if intent_ref is not None
            else None
        )
        frame_ref = persist_policy_request_frame(ctx.store, frame, inputs=inputs)
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.policy_request_ref = frame_ref
        new_state.artifacts_index[ARTIFACT_POLICY_REQUEST_FRAME_REF] = frame_ref
        new_state.params.setdefault("policy_answer_mode", "verified_async")
        new_state.execution_profile = new_state.execution_profile or "policy_verified_async"
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[frame_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Policy request frame created.",
                    attrs={
                        "jurisdiction": frame.jurisdiction,
                        "request_id": frame.request_id,
                        "research_dag_sidecar": bool(
                            state.params.get("research_dag_enabled")
                            or state.params.get(RESEARCH_DAG_FEATURE_FLAG)
                        ),
                    },
                )
            ],
        )


__all__ = ["PlanPolicyRequestNode"]
