"""Public planning draft policy options module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
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
    load_policy_request_frame,
    load_source_verification_report,
    persist_policy_option_set,
)
from polisyos.scientist.validation.policy_verified.selection import select_policy_source_ref
from polisyos.scientist.validation.policy_verified.service import draft_policy_option_set

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
        "artifacts_index",
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
        try:
            request_ref = select_policy_source_ref(
                state.policy_request_ref,
                state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF),
            )
            report_ref = select_policy_source_ref(
                state.source_verification_report_ref,
                state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF),
            )
        except ValueError:
            return NodeOutcome(
                status="fail",
                state=_without_current_options(state),
                error=NodeError(
                    code="policy_source_selection_conflict",
                    message="Selected policy-source references disagree.",
                ),
            )
        if request_ref is None or report_ref is None:
            return NodeOutcome(status="skip", state=_without_current_options(state))
        frame = load_policy_request_frame(
            ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump())
        )
        report = load_source_verification_report(
            ctx.store, SourceVerificationReportRef.model_validate(report_ref.model_dump())
        )
        if report.request_id != frame.request_id:
            return NodeOutcome(
                status="fail",
                state=_without_current_options(state),
                error=NodeError(
                    code="policy_request_source_mismatch",
                    message="Source verification belongs to a different policy request.",
                ),
            )
        option_set = draft_policy_option_set(state, frame, report)
        option_ref = persist_policy_option_set(
            ctx.store,
            option_set,
            inputs=[
                input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
                input_ref_from_artifact_ref(report_ref, role="source_verification_report"),
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
                    attrs={
                        "verified_options": len(option_set.verified_options),
                        "hypothesis_options": len(option_set.hypothesis_options),
                    },
                )
            ],
        )


def _without_current_options(state: ExperimentState) -> ExperimentState:
    """Keep an unverified prior option out of the current output projection."""
    if (
        state.policy_option_set_ref is None
        and ARTIFACT_POLICY_OPTION_SET_REF not in state.artifacts_index
    ):
        return state
    projected = branch_state(state, write_paths=_SPEC.state_writes).state
    projected.policy_option_set_ref = None
    projected.artifacts_index.pop(ARTIFACT_POLICY_OPTION_SET_REF, None)
    return projected


__all__ = ["DraftPolicyOptionsNode"]
