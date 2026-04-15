"""Public planning run source verification module API."""
from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    LegalCandidatePackRef,
    LegalSourcePackRef,
    PolicyRequestFrameRef,
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
    persist_source_verification_report,
)
from polisyos.scientist.policy_verified.service import verify_source_pack

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
        "policy_request_ref",
        "legal_candidate_pack_ref",
        "legal_source_pack_ref",
        "params.max_verifier_calls",
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
        if state.source_verification_report_ref is not None and ARTIFACT_SOURCE_VERIFICATION_REPORT_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        request_ref = state.policy_request_ref or state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF)
        candidate_ref = state.legal_candidate_pack_ref or state.artifacts_index.get(ARTIFACT_LEGAL_CANDIDATE_PACK_REF)
        source_ref = state.legal_source_pack_ref or state.artifacts_index.get(ARTIFACT_LEGAL_SOURCE_PACK_REF)
        if request_ref is None or candidate_ref is None or source_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message="Missing policy verification inputs; source verification skipped.")],
            )
        frame = load_policy_request_frame(ctx.store, PolicyRequestFrameRef.model_validate(request_ref.model_dump()))
        candidate_pack = load_legal_candidate_pack(
            ctx.store, LegalCandidatePackRef.model_validate(candidate_ref.model_dump())
        )
        source_pack = load_legal_source_pack(
            ctx.store, LegalSourcePackRef.model_validate(source_ref.model_dump())
        )
        report = verify_source_pack(ctx, state, frame, candidate_pack, source_pack)
        report_ref = persist_source_verification_report(
            ctx.store,
            report,
            inputs=[
                InputRef(artifact_id=request_ref.artifact_id, role="policy_request_frame"),
                InputRef(artifact_id=candidate_ref.artifact_id, role="legal_candidate_pack"),
                InputRef(artifact_id=source_ref.artifact_id, role="legal_source_pack"),
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
                    message="Source verification completed.",
                    attrs={"verified_claims": len(report.verified_claims), "gaps": len(report.unresolved_critical_gaps)},
                )
            ],
        )


__all__ = ["RunSourceVerificationNode"]
