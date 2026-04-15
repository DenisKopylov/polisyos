"""Public planning draft policy options module API."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
)
from polisyos.scientist.policy_verified import (
    load_policy_request_frame,
    load_source_verification_report,
    persist_policy_option_set,
)
from polisyos.scientist.policy_verified.service import draft_policy_option_set

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_draft_policy_options@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Draft Policy Options",
    description="Draft verified and hypothesis policy options from source-verified legal claims.",
    tags=["builtin", "planning", "policy_verified"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "policy_request_ref",
        "source_verification_report_ref",
        "params.allow_hypotheses",
    ],
    state_writes=[
        "policy_option_set_ref",
        f"artifacts_index.{ARTIFACT_POLICY_OPTION_SET_REF}",
    ],
    produces=[ARTIFACT_POLICY_OPTION_SET_REF],
)


@dataclass(frozen=True)
class DraftPolicyOptionsNode:
    """Planning DAG node that turns verified legal claims into verified and hypothesis-backed options.

    Reads the request frame and source-verification report, then writes the
    `policy_option_set_ref` artifact used by formalization, simulation, and final reporting.
    """
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if state.policy_option_set_ref is not None and ARTIFACT_POLICY_OPTION_SET_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)
        request_ref = state.policy_request_ref or state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF)
        report_ref = state.source_verification_report_ref or state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF)
        if request_ref is None or report_ref is None:
            return NodeOutcome(status="skip", state=state)
        frame = load_policy_request_frame(ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump()))
        report = load_source_verification_report(
            ctx.store, SourceVerificationReportRef.model_validate(report_ref.model_dump())
        )
        option_set = draft_policy_option_set(state, frame, report)
        option_ref = persist_policy_option_set(
            ctx.store,
            option_set,
            inputs=[
                InputRef(artifact_id=request_ref.artifact_id, role="policy_request_frame"),
                InputRef(artifact_id=report_ref.artifact_id, role="source_verification_report"),
            ],
        )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.policy_option_set_ref = option_ref
        new_state.artifacts_index[ARTIFACT_POLICY_OPTION_SET_REF] = option_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[option_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Policy options drafted.",
                    attrs={"verified_options": len(option_set.verified_options), "hypothesis_options": len(option_set.hypothesis_options)},
                )
            ],
        )


__all__ = ["DraftPolicyOptionsNode"]
