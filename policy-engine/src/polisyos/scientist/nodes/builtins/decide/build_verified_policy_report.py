"""Public decide build verified policy report module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    PolicyOptionSetRef,
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
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
)
from polisyos.scientist.policy_verified import (
    load_policy_option_set,
    load_policy_request_frame,
    load_source_verification_report,
    persist_verified_policy_report,
)
from polisyos.scientist.policy_verified.service import build_verified_policy_report

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_verified_policy_report@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Verified Policy Report",
    description="Compose the final verified-plus-hypotheses policy report for Scientist production mode.",
    tags=["builtin", "decide", "policy_verified"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "policy_request_ref",
        "policy_option_set_ref",
        "source_verification_report_ref",
        "params.needs_expert_review",
        "artifacts_index",
    ],
    state_writes=[
        "verified_policy_report_ref",
        f"artifacts_index.{ARTIFACT_VERIFIED_POLICY_REPORT_REF}",
    ],
    produces=[ARTIFACT_VERIFIED_POLICY_REPORT_REF],
)


@dataclass(frozen=True)
class BuildVerifiedPolicyReportNode:
    """Build verified policy report node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if (
            state.verified_policy_report_ref is not None
            and ARTIFACT_VERIFIED_POLICY_REPORT_REF in state.artifacts_index
        ):
            return NodeOutcome(status="ok", state=state)
        request_ref = state.policy_request_ref or state.artifacts_index.get(
            ARTIFACT_POLICY_REQUEST_FRAME_REF
        )
        option_ref = state.policy_option_set_ref or state.artifacts_index.get(
            ARTIFACT_POLICY_OPTION_SET_REF
        )
        report_ref = state.source_verification_report_ref or state.artifacts_index.get(
            ARTIFACT_SOURCE_VERIFICATION_REPORT_REF
        )
        if request_ref is None or option_ref is None or report_ref is None:
            return NodeOutcome(status="skip", state=state)
        frame = load_policy_request_frame(
            ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump())
        )
        option_set = load_policy_option_set(
            ctx.store, PolicyOptionSetRef.model_validate(option_ref.model_dump())
        )
        verification_report = load_source_verification_report(
            ctx.store, SourceVerificationReportRef.model_validate(report_ref.model_dump())
        )
        payload = build_verified_policy_report(state, frame, verification_report, option_set)
        payload_ref = persist_verified_policy_report(
            ctx.store,
            payload,
            inputs=[
                InputRef(artifact_id=request_ref.artifact_id, role="policy_request_frame"),
                InputRef(artifact_id=option_ref.artifact_id, role="policy_option_set"),
                InputRef(artifact_id=report_ref.artifact_id, role="source_verification_report"),
            ],
        )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.verified_policy_report_ref = payload_ref
        new_state.artifacts_index[ARTIFACT_VERIFIED_POLICY_REPORT_REF] = payload_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[payload_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Verified policy report created.",
                    attrs={
                        "verified_findings": len(payload.verified_findings),
                        "needs_expert_review": payload.needs_expert_review,
                    },
                )
            ],
        )


__all__ = ["BuildVerifiedPolicyReportNode"]
