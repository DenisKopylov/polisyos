"""Public planning run source gap review module API."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    LegalCandidatePackRef,
    LegalSourcePackRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
)
from polisyos.scientist.policy_verified import (
    load_legal_candidate_pack,
    load_legal_source_pack,
    load_policy_request_frame,
    load_source_verification_report,
    persist_legal_candidate_pack,
    persist_legal_source_pack,
    persist_source_verification_report,
)
from polisyos.scientist.policy_verified.service import recover_source_gaps

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_source_gap_review@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Source Gap Review",
    description="Assess remaining legal source coverage gaps and mark unresolved critical gaps.",
    tags=["builtin", "planning", "policy_verified", "legal"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "policy_request_ref",
        "legal_candidate_pack_ref",
        "legal_source_pack_ref",
        "source_verification_report_ref",
        "params.max_gap_review_calls",
        "params.max_source_docs",
        "params.max_reference_hops",
        "params.verification_cycles_completed",
    ],
    state_writes=[
        "legal_candidate_pack_ref",
        f"artifacts_index.{ARTIFACT_LEGAL_CANDIDATE_PACK_REF}",
        "legal_source_pack_ref",
        f"artifacts_index.{ARTIFACT_LEGAL_SOURCE_PACK_REF}",
        "source_verification_report_ref",
        f"artifacts_index.{ARTIFACT_SOURCE_VERIFICATION_REPORT_REF}",
        "params.needs_expert_review",
        "params.verification_cycles_completed",
    ],
    produces=[
        ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
        ARTIFACT_LEGAL_SOURCE_PACK_REF,
        ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ],
)


@dataclass(frozen=True)
class RunSourceGapReviewNode:
    """Planning DAG node that retries unresolved source gaps and rewrites the legal evidence pack.

    It requires the request frame, candidate pack, source pack, and a prior
    verification report, then writes updated candidate/source/report refs plus
    expert-review and verification-cycle markers into workflow state.
    """
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        request_ref = state.policy_request_ref or state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF)
        candidate_ref = state.legal_candidate_pack_ref or state.artifacts_index.get(ARTIFACT_LEGAL_CANDIDATE_PACK_REF)
        source_ref = state.legal_source_pack_ref or state.artifacts_index.get(ARTIFACT_LEGAL_SOURCE_PACK_REF)
        report_ref = state.source_verification_report_ref or state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF)
        if request_ref is None or candidate_ref is None or source_ref is None or report_ref is None:
            return NodeOutcome(status="skip", state=state)

        frame = load_policy_request_frame(ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump()))
        candidate_pack = load_legal_candidate_pack(
            ctx.store, LegalCandidatePackRef.model_validate(candidate_ref.model_dump())
        )
        source_pack = load_legal_source_pack(
            ctx.store, LegalSourcePackRef.model_validate(source_ref.model_dump())
        )
        report = load_source_verification_report(
            ctx.store, SourceVerificationReportRef.model_validate(report_ref.model_dump())
        )
        updated_candidate_pack, updated_source_pack, updated = recover_source_gaps(
            ctx,
            state,
            frame,
            candidate_pack,
            source_pack,
            report,
        )
        updated_candidate_ref = persist_legal_candidate_pack(
            ctx.store,
            updated_candidate_pack,
            inputs=[InputRef(artifact_id=request_ref.artifact_id, role="policy_request_frame")],
        )
        updated_source_ref = persist_legal_source_pack(
            ctx.store,
            updated_source_pack,
            inputs=[InputRef(artifact_id=updated_candidate_ref.artifact_id, role="legal_candidate_pack")],
        )
        updated_ref = persist_source_verification_report(
            ctx.store,
            updated,
            inputs=[
                InputRef(artifact_id=request_ref.artifact_id, role="policy_request_frame"),
                InputRef(artifact_id=updated_candidate_ref.artifact_id, role="legal_candidate_pack"),
                InputRef(artifact_id=updated_source_ref.artifact_id, role="legal_source_pack"),
            ],
        )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.legal_candidate_pack_ref = updated_candidate_ref
        new_state.artifacts_index[ARTIFACT_LEGAL_CANDIDATE_PACK_REF] = updated_candidate_ref
        new_state.legal_source_pack_ref = updated_source_ref
        new_state.artifacts_index[ARTIFACT_LEGAL_SOURCE_PACK_REF] = updated_source_ref
        new_state.source_verification_report_ref = updated_ref
        new_state.artifacts_index[ARTIFACT_SOURCE_VERIFICATION_REPORT_REF] = updated_ref
        new_state.params["needs_expert_review"] = updated.needs_expert_review
        new_state.params["verification_cycles_completed"] = updated.verification_cycles_completed
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[updated_candidate_ref, updated_source_ref, updated_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Source gap review completed.",
                    attrs={
                        "critical_gaps": len(updated.unresolved_critical_gaps),
                        "needs_expert_review": updated.needs_expert_review,
                        "verification_cycles_completed": updated.verification_cycles_completed,
                    },
                )
            ],
        )


__all__ = ["RunSourceGapReviewNode"]
