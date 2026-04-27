"""Public decide build verified policy report module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    PolicyOptionSetRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
)
from polisyos.scientist.policy_verified import (
    load_policy_option_set,
    load_policy_request_frame,
    load_source_verification_report,
    persist_verified_policy_report,
)
from polisyos.scientist.policy_verified.service import build_verified_policy_report
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    enforce_phase5_publication,
    run_phase5_artifact_preflight,
)

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
        f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
    ],
    produces=[
        ARTIFACT_VERIFIED_POLICY_REPORT_REF,
        ARTIFACT_VALIDATION_REPORT_REF,
        ARTIFACT_JUDGE_VERDICT_REF,
    ],
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
        publication = run_phase5_artifact_preflight(
            ctx,
            state,
            Phase5ArtifactPreflightInput(
                artifact_ref=payload_ref,
                artifact_kind="scientist.verified_policy_report",
                artifact_payload=payload.model_dump(mode="json"),
                generated_for="scientist.verified_policy_report",
                analyst_facing=True,
                base_readiness="ready",
            ),
        )
        try:
            enforce_phase5_publication(publication)
        except Phase5ValidationBlocked:
            validation_ref = ArtifactRef.model_validate(dict(publication.validation_ref))
            new_state = branch_state(
                state,
                write_paths=(
                    f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                    f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                ),
            ).state
            new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
            if publication.judge_verdict_ref is not None:
                new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = (
                    publication.judge_verdict_ref
                )
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=[
                    artifact
                    for artifact in (validation_ref, publication.judge_verdict_ref)
                    if artifact is not None
                ],
                error=NodeError(
                    code="phase5_validation_failed",
                    message="Phase 5 validation blocked verified policy report publication",
                    details={
                        "validation_report_ref": str(publication.validation_ref.artifact_id),
                        "verdict": publication.validation_report.verdict,
                        "readiness": publication.validation_report.readiness,
                        "gate_failures": list(publication.validation_report.gate_failures),
                    },
                ),
            )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.verified_policy_report_ref = payload_ref
        new_state.artifacts_index[ARTIFACT_VERIFIED_POLICY_REPORT_REF] = payload_ref
        validation_ref = ArtifactRef.model_validate(dict(publication.validation_ref))
        new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
        if publication.judge_verdict_ref is not None:
            new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = publication.judge_verdict_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                artifact
                for artifact in (payload_ref, validation_ref, publication.judge_verdict_ref)
                if artifact is not None
            ],
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
