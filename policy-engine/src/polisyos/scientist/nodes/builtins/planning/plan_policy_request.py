"""Public planning plan policy request module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_POLICY_REQUEST_FRAME_REF
from polisyos.scientist.validation.policy_verified import (
    persist_policy_request_frame,
)
from polisyos.scientist.validation.policy_verified.service import build_policy_request_frame
from polisyos.scientist.methods.research_dag.projections import RESEARCH_DAG_FEATURE_FLAG

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
    state_reads=[
        "inputs.research_intent_ref",
        "params.policy_question",
        "params.policy_request",
        "params.problem_statement",
        "params.policy_request_jurisdiction",
        "params.policy_request_as_of",
        "params.policy_request_domain",
        "params.research_dag_enabled",
        "artifacts_index",
    ],
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
        if (
            state.policy_request_ref is not None
            and ARTIFACT_POLICY_REQUEST_FRAME_REF in state.artifacts_index
        ):
            return NodeOutcome(status="ok", state=state)

        frame = build_policy_request_frame(ctx, state)
        frame_ref = persist_policy_request_frame(ctx.store, frame)
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
