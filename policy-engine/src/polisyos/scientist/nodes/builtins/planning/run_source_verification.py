"""Public planning run source verification module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    LegalCandidatePackRef,
    LegalSourcePackRef,
    PolicyRequestFrameRef,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
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
    load_legal_candidate_pack,
    load_legal_source_pack,
    load_policy_request_frame,
    persist_source_verification_report,
)
from polisyos.scientist.validation.policy_verified.selection import select_policy_source_ref
from polisyos.scientist.validation.policy_verified.service import verify_source_pack

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_source_verification@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Source Verification",
    description="Verify legal candidate bundles against original sources and emit quote-backed claims.",
    tags=["builtin", "planning", "policy_verified", "legal"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "execution_profile",
        "inputs",
        "params",
        "artifacts_index",
        "policy_request_ref",
        "legal_candidate_pack_ref",
        "legal_source_pack_ref",
    ],
    state_writes=[
        "source_verification_report_ref",
        f"artifacts_index.{ARTIFACT_SOURCE_VERIFICATION_REPORT_REF}",
        "params.verification_cycles_completed",
    ],
    produces=[ARTIFACT_SOURCE_VERIFICATION_REPORT_REF],
)


@dataclass(frozen=True)
class RunSourceVerificationNode:
    """Planning DAG node that verifies cited legal claims and records unresolved evidence gaps.

    Reads the request frame plus legal candidate/source packs, then writes the
    source-verification report ref and updated verification-cycle counters used
    by drafting, gap review, and governance.
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
            candidate_ref = select_policy_source_ref(
                state.legal_candidate_pack_ref,
                state.artifacts_index.get(ARTIFACT_LEGAL_CANDIDATE_PACK_REF),
            )
            source_ref = select_policy_source_ref(
                state.legal_source_pack_ref,
                state.artifacts_index.get(ARTIFACT_LEGAL_SOURCE_PACK_REF),
            )
        except ValueError:
            return NodeOutcome(
                status="fail",
                state=_without_current_report(state),
                error=NodeError(
                    code="policy_source_selection_conflict",
                    message="Policy-source selectors disagree.",
                ),
            )
        if request_ref is None or candidate_ref is None or source_ref is None:
            return NodeOutcome(
                status="skip",
                state=_without_current_report(state),
                events=[
                    NodeEvent(
                        level="warn",
                        message="Missing policy verification inputs; source verification skipped.",
                    )
                ],
            )
        frame = load_policy_request_frame(
            ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump())
        )
        candidate_pack = load_legal_candidate_pack(
            ctx.store, LegalCandidatePackRef.model_validate(candidate_ref.model_dump())
        )
        source_pack = load_legal_source_pack(
            ctx.store, LegalSourcePackRef.model_validate(source_ref.model_dump())
        )
        if (
            candidate_pack.request_id != frame.request_id
            or source_pack.request_id != frame.request_id
        ):
            return NodeOutcome(
                status="fail",
                state=_without_current_report(state),
                error=NodeError(
                    code="policy_request_source_mismatch",
                    message="Legal sources belong to a different policy request.",
                ),
            )
        report = verify_source_pack(ctx, state, frame, candidate_pack, source_pack)
        report_ref = persist_source_verification_report(
            ctx.store,
            report,
            inputs=[
                input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
                input_ref_from_artifact_ref(candidate_ref, role="legal_candidate_pack"),
                input_ref_from_artifact_ref(source_ref, role="legal_source_pack"),
            ],
        )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.source_verification_report_ref = report_ref
        new_state.artifacts_index[ARTIFACT_SOURCE_VERIFICATION_REPORT_REF] = report_ref
        new_state.params["verification_cycles_completed"] = report.verification_cycles_completed
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[report_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Legal source candidates collected; "
                        "independent legal verification is not established."
                    ),
                    attrs={
                        "legal_verification_status": report.legal_verification_status,
                        "candidate_claims": len(report.legal_claim_candidates),
                        "verified_claims": "not_established",
                        "gaps": len(report.unresolved_critical_gaps),
                    },
                )
            ],
        )


def _without_current_report(state: ExperimentState) -> ExperimentState:
    """Keep an unverified prior report out of this direct output projection."""
    if (
        state.source_verification_report_ref is None
        and ARTIFACT_SOURCE_VERIFICATION_REPORT_REF not in state.artifacts_index
    ):
        return state
    projected = branch_state(state, write_paths=_SPEC.state_writes).state
    projected.source_verification_report_ref = None
    projected.artifacts_index.pop(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF, None)
    return projected


__all__ = ["RunSourceVerificationNode"]
