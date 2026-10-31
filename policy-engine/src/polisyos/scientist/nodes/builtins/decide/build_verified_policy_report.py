"""Public decide build verified policy report module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.scientist import (
    PolicyOptionSetRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _CURRENT_POLICY_PROJECTION_WRITE_PATHS,
    _CURRENT_POLICY_PROMOTION_PARAM_KEYS,
    project_policy_promotion_state,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeEvent,
    NodeInputContract,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    enforce_phase5_publication,
    run_phase5_artifact_preflight,
)
from polisyos.scientist.validation.policy_verified import (
    load_policy_option_set,
    load_policy_request_frame,
    load_source_verification_report,
    persist_verified_policy_report,
)
from polisyos.scientist.validation.policy_verified.currentness import (
    VERIFIED_POLICY_REPORT_SOURCE_READ_PATHS,
    resolve_current_verified_policy_report,
)
from polisyos.scientist.validation.policy_verified.selection import (
    require_selected_policy_source_bindings,
    select_policy_source_ref,
)
from polisyos.scientist.validation.policy_verified.service import build_verified_policy_report

if TYPE_CHECKING:
    from polisyos.ir.governance.validation import ValidationReport
    from polisyos.scientist.validation.policy_verified.models import PolicyReportCompositionBinding


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
    state_reads=list(VERIFIED_POLICY_REPORT_SOURCE_READ_PATHS),
    state_writes=list(
        dict.fromkeys(
            [
                "verified_policy_report_ref",
                f"artifacts_index.{ARTIFACT_VERIFIED_POLICY_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                *_CURRENT_POLICY_PROJECTION_WRITE_PATHS,
            ]
        )
    ),
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
        state = project_policy_promotion_state(
            state,
            ctx=ctx,
            branch_write_paths=_SPEC.state_writes,
        )
        existing_ref = state.verified_policy_report_ref or state.artifacts_index.get(
            ARTIFACT_VERIFIED_POLICY_REPORT_REF
        )
        if existing_ref is not None:
            admission = resolve_current_verified_policy_report(ctx, state, existing_ref)
            if admission.is_current:
                return NodeOutcome(status="ok", state=state)
            state = branch_state(state, write_paths=_SPEC.state_writes).state
            state.verified_policy_report_ref = None
            state.artifacts_index.pop(ARTIFACT_VERIFIED_POLICY_REPORT_REF, None)
        try:
            request_ref = select_policy_source_ref(
                state.policy_request_ref,
                state.artifacts_index.get(ARTIFACT_POLICY_REQUEST_FRAME_REF),
            )
            option_ref = select_policy_source_ref(
                state.policy_option_set_ref,
                state.artifacts_index.get(ARTIFACT_POLICY_OPTION_SET_REF),
            )
            report_ref = select_policy_source_ref(
                state.source_verification_report_ref,
                state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF),
            )
        except ValueError:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="policy_source_selection_conflict",
                    message="Selected policy-source references disagree.",
                ),
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
        if (
            option_set.request_id != frame.request_id
            or verification_report.request_id != frame.request_id
        ):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="policy_request_source_mismatch",
                    message="Selected policy options or source verification belong to a different request.",
                ),
            )
        try:
            require_selected_policy_source_bindings(
                ctx.store,
                request_ref=request_ref,
                option_ref=option_ref,
                source_report_ref=report_ref,
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="policy_source_binding_not_established",
                    message="Policy sources do not bind the selected request and verification report.",
                ),
            )
        payload = build_verified_policy_report(state, frame, verification_report, option_set)
        payload_ref = persist_verified_policy_report(
            ctx.store,
            payload,
            inputs=[
                input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
                input_ref_from_artifact_ref(option_ref, role="policy_option_set"),
                input_ref_from_artifact_ref(report_ref, role="source_verification_report"),
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


_COMPOSITION_COMPONENT_ID = "scientist.node_build_verified_policy_report@1.1.0"
_COMPOSITION_REF_PATHS = (
    "artifacts_index.verified_policy_body_ref",
    "artifacts_index.verified_policy_candidate_ref",
    "artifacts_index.phase5_candidate_assessment_ref",
    "reports_index.governance_report_ref",
    *(
        f"{mapping}.{role}"
        for role in (
            "fairness_audit_report_ref",
            "shift_diagnostic_report_ref",
            "sensitivity_analysis_bundle_ref",
            "sensitivity_result_ref",
            "explanation_bundle_ref",
        )
        for mapping in ("artifacts_index", "reports_index")
    ),
)
_COMPOSITION_READ_PATHS = (
    "schema_version",
    "run_id",
    "execution_profile",
    *_COMPOSITION_REF_PATHS,
    "params.high_impact",
    "params.phase5_requires_fairness",
    "params.protected_attributes",
    "params.phase5_require_advisor_consensus",
    "params.phase5_require_judge_verdict",
    "params.phase5_enforce_publication",
)
_COMPOSITION_WRITE_PATHS = (
    "verified_policy_report_ref",
    "artifacts_index.verified_policy_report_ref",
    "artifacts_index.validation_report_ref",
)
_COMPOSITION_SPEC = InputAwareNodeSpec(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse(_COMPOSITION_COMPONENT_ID),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Compose Limited Verified Policy Report",
        description="Compose exact completed policy stages while preserving unresolved authority.",
        tags=["builtin", "decide", "policy_verified", "limited"],
        capabilities=Capability.SCIENTIST_NODE,
    ),
    state_reads=list(_COMPOSITION_READ_PATHS),
    state_writes=list(_COMPOSITION_WRITE_PATHS),
    produces=[ARTIFACT_VERIFIED_POLICY_REPORT_REF, ARTIFACT_VALIDATION_REPORT_REF],
    input_contract=NodeInputContract(
        component_id=_COMPOSITION_COMPONENT_ID,
        contract_id="policy_verified_completion.v1",
        state_paths=_COMPOSITION_READ_PATHS,
        artifact_ref_paths=_COMPOSITION_REF_PATHS,
    ),
)


@dataclass(frozen=True)
class BuildVerifiedPolicyReportCompositionNode:
    """Compose admitted stages into an honest limited report, never an approval."""

    @property
    def spec(self) -> InputAwareNodeSpec:
        """Return the fixed Engine-enforced completion input and output contract."""
        return _COMPOSITION_SPEC

    def validate_cache_hit(
        self, ctx: ExecutionContext, state: ExperimentState, cached_outcome: NodeOutcome
    ) -> bool:
        """Require a fresh admitted composition occurrence rather than a cached role."""
        return False

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Consume only fixed owner-admitted facts and persist a non-publishable result."""
        from polisyos.ir.governance.validation import persist_validation_report
        from polisyos.scientist.orchestration.engine.input_ports import (
            NodeInputPortError,
            read_verified_policy_completion_admission,
        )
        from polisyos.scientist.validation.policy_verified.models import (
            PolicyReportCompositionBinding,
            _compose_limited_policy_report,
            _policy_composition_inputs,
            load_verified_policy_body,
        )

        try:
            admission = read_verified_policy_completion_admission(ctx, state)
            if (
                admission.status != "current"
                or admission.run_id != state.run_id
                or admission.purpose != "limited_policy_composition"
                or admission.requirement_authority != "not_established"
                or admission.publishable is not False
            ):
                raise NodeInputPortError("policy_composition_sources_not_established")
            binding = PolicyReportCompositionBinding(
                run_id=admission.run_id,
                body_ref=admission.body_ref,
                candidate_ref=admission.candidate_ref,
                phase5_assessment_ref=admission.phase5_assessment_ref,
                initial_governance_ref=admission.initial_governance_ref,
                final_governance_ref=admission.final_governance_ref,
                selected_input_ref=admission.input_state_ref,
                selected_attempt_ref=admission.selected_attempt_ref,
            )
            report = _compose_limited_policy_report(
                load_verified_policy_body(ctx.store, binding.body_ref), binding
            )
            report_ref = persist_verified_policy_report(ctx.store, report)
            validation = _limited_composition_validation(report_ref, binding)
            validation_ref = ArtifactRef.model_validate(
                persist_validation_report(
                    ensure_ir_artifact_store(ctx.store),
                    validation,
                    inputs=[
                        input_ref_from_artifact_ref(report_ref, role="limited_policy_report"),
                        *_policy_composition_inputs(binding),
                    ],
                ).model_dump(mode="json")
            )
            after = read_verified_policy_completion_admission(ctx, state)
            if after != admission or after.status != "current":
                raise NodeInputPortError("policy_composition_sources_changed")
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="policy_composition_not_established",
                    message="Completed policy stages do not establish the selected limited composition.",
                    details={"reason": str(exc)},
                ),
            )
        output = branch_state(state, write_paths=_COMPOSITION_WRITE_PATHS).state
        output.verified_policy_report_ref = report_ref
        output.artifacts_index[ARTIFACT_VERIFIED_POLICY_REPORT_REF] = report_ref
        output.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
        return NodeOutcome(
            status="ok",
            state=output,
            artifacts=[report_ref, validation_ref],
            events=[
                NodeEvent(
                    level="warn",
                    code="limited_policy_composition_completed",
                    message="Policy stages composed with unresolved publication authority.",
                    attrs={"result_status": "limited", "publishable": False},
                )
            ],
        )


def _limited_composition_validation(
    report_ref: ArtifactRef, binding: PolicyReportCompositionBinding
) -> ValidationReport:
    """Project known unresolved authority into the existing validation-report owner."""
    from polisyos.ir.governance.validation import Phase5GateComponent, ValidationReport
    from polisyos.scientist.validation.policy_verified.models import PolicyReportCompositionBinding

    binding = PolicyReportCompositionBinding.model_validate(binding.model_dump(mode="python"))

    unresolved = (
        "requirement_authority_not_established",
        "legal_claim_verification_not_established",
        "option_program_correspondence_not_established",
    )
    return ValidationReport(
        error_summary="Limited policy composition; publication authority is not established.",
        issues=[],
        verdict="blocked",
        readiness="blocked",
        artifact_ref=str(report_ref.artifact_id),
        artifact_kind=report_ref.kind,
        phase5_components=[
            Phase5GateComponent(
                name=reason,
                status="blocked",
                required=True,
                blockers=[reason],
                summary="This composition preserves the unresolved claim boundary.",
            )
            for reason in unresolved
        ],
        gate_failures=list(unresolved),
        evidence_refs=[str(report_ref.artifact_id)],
        normalized_payload={
            "purpose": binding.purpose,
            "result_status": binding.result_status,
            "requirement_authority": binding.requirement_authority,
            "publishable": binding.publishable,
            "composition": binding.model_dump(mode="json"),
        },
        generated_for="scientist.verified_policy_report.limited_composition",
    )


__all__ = ["BuildVerifiedPolicyReportCompositionNode", "BuildVerifiedPolicyReportNode"]
