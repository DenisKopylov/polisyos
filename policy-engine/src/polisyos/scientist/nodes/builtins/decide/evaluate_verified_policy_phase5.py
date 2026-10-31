"""Run candidate-only Phase-5 judges on an Engine-admitted restricted input."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.methods.search.judge_stack import persist_candidate_judge_verdict
from polisyos.scientist.methods.search.judge_threshold_basis import (
    resolve_judge_threshold_basis,
    selected_judge_threshold_registry,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_VERIFIED_POLICY_BODY_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeError,
    NodeEvent,
    NodeInputContract,
    NodeOutcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.policy_design.option_program_contracts import (
    OPTION_PROGRAM_CORRESPONDENCE_NOT_ESTABLISHED,
)
from polisyos.scientist.policy_design.schema import load_policy_candidate_schema
from polisyos.scientist.validation.policy_verified import load_verified_policy_body
from polisyos.scientist.validation.policy_verified.phase5_candidate import (
    Phase5CandidateAssessment,
    evaluate_phase5_candidate,
    load_phase5_candidate_assessment,
    persist_phase5_candidate_assessment,
)

_COMPONENT_ID = "scientist.node_evaluate_verified_policy_phase5@1.0.0"
_CONTRACT_ID = "policy_verified_phase5.v1"
_CANDIDATE_REF = "verified_policy_candidate_ref"
_RESULT_REF = "phase5_candidate_assessment_ref"
_BODY_PATH = f"artifacts_index.{ARTIFACT_VERIFIED_POLICY_BODY_REF}"
_CANDIDATE_PATH = f"artifacts_index.{_CANDIDATE_REF}"
_GOVERNANCE_PATH = f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}"
_INPUT_PATHS = (
    "schema_version",
    "run_id",
    "execution_profile",
    _BODY_PATH,
    _CANDIDATE_PATH,
    _GOVERNANCE_PATH,
)
_METADATA = ComponentMetadata(
    component_id=ComponentId.parse(_COMPONENT_ID),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Evaluate Verified Policy Candidate Phase 5",
    description="Run six judges on selected sources as a non-publishable candidate diagnostic.",
    tags=["builtin", "decide", "policy_verified", "candidate"],
    capabilities=Capability.SCIENTIST_NODE,
)
_SPEC = InputAwareNodeSpec(
    metadata=_METADATA,
    state_reads=list(_INPUT_PATHS),
    state_writes=[f"artifacts_index.{_RESULT_REF}"],
    produces=[_RESULT_REF],
    input_contract=NodeInputContract(
        contract_id=_CONTRACT_ID,
        component_id=_COMPONENT_ID,
        state_paths=_INPUT_PATHS,
        artifact_ref_paths=(_BODY_PATH, _CANDIDATE_PATH, _GOVERNANCE_PATH),
    ),
)


def _failure(state: ExperimentState, code: str) -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code=code, message="Phase-5 candidate sources or evaluation are not established."
        ),
    )


def _same_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.manifest_profile_sha256 is not None
        and artifact_ref_identity_key(left) == artifact_ref_identity_key(right)
    )


@dataclass(frozen=True)
class EvaluateVerifiedPolicyPhase5Node:
    """Produce an attempt-bound diagnostic, never a publication verdict."""

    @property
    def spec(self) -> InputAwareNodeSpec:
        """Return the fixed restricted-input contract."""
        return _SPEC

    def validate_cache_hit(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
        cached_outcome: NodeOutcome,
    ) -> bool:
        """Require a fresh Engine attempt and source admission for every diagnostic."""
        return False

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Consume only Engine-admitted sources and emit their candidate diagnostic."""
        try:
            from polisyos.scientist.orchestration.engine.input_ports import (
                read_input_port_basis,
                read_verified_policy_phase5_admission,
            )

            selection = read_input_port_basis(ctx, state)
            admission = read_verified_policy_phase5_admission(ctx, state)
            body_ref = state.artifacts_index.get(ARTIFACT_VERIFIED_POLICY_BODY_REF)
            candidate_ref = state.artifacts_index.get(_CANDIDATE_REF)
            governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
            if (
                selection.run_id != state.run_id
                or selection.component_id != _COMPONENT_ID
                or selection.contract_id != _CONTRACT_ID
                or admission.status != "current"
                or admission.governance_report is None
                or not _same_ref(body_ref, admission.body_ref)
                or not _same_ref(candidate_ref, admission.candidate_ref)
                or not _same_ref(governance_ref, admission.governance_ref)
            ):
                return _failure(state, "phase5_source_admission_not_established")
            assert body_ref is not None
            assert candidate_ref is not None
            assert governance_ref is not None
            body = load_verified_policy_body(ctx.store, body_ref)
            candidate = load_policy_candidate_schema(ctx.store, candidate_ref)
            evaluation = evaluate_phase5_candidate(
                ctx.store,
                candidate=candidate,
                candidate_ref=candidate_ref,
                governance_report=admission.governance_report,
                run_id=state.run_id,
                body=body,
            )
            if evaluation.verdict is None or evaluation.threshold_basis_ref is None:
                return _failure(state, evaluation.reason or "phase5_evaluation_not_established")
            basis_ref = evaluation.threshold_basis_ref
            judge_inputs = [
                input_ref_from_artifact_ref(ref, role=role)
                for role, ref in (
                    ("verified_body", body_ref),
                    ("policy_candidate", candidate_ref),
                    ("governance_assessment", governance_ref),
                    ("threshold_basis", basis_ref),
                    ("selected_input", selection.input_state_ref),
                    ("selected_attempt", selection.basis_ref),
                )
            ]
            judge_ref = persist_candidate_judge_verdict(
                ctx.store, evaluation.verdict, inputs=judge_inputs
            )
            result = Phase5CandidateAssessment(
                run_id=state.run_id,
                body_ref=body_ref,
                candidate_ref=candidate_ref,
                governance_ref=governance_ref,
                threshold_basis_ref=basis_ref,
                judge_verdict_ref=judge_ref,
                selected_input_ref=selection.input_state_ref,
                selected_attempt_ref=selection.basis_ref,
                threshold_uses=evaluation.threshold_uses,
                validation_profiles=evaluation.validation_profiles,
                limitation_codes=(
                    OPTION_PROGRAM_CORRESPONDENCE_NOT_ESTABLISHED,
                    *(() if not body.needs_expert_review else ("source_expert_review_required",)),
                    *(
                        ("source_critical_gaps_unresolved",)
                        if any(
                            gap.severity == "critical" and not gap.resolved
                            for gap in body.unresolved_critical_gaps
                        )
                        else ()
                    ),
                    *(() if evaluation.reason is None else (evaluation.reason,)),
                ),
            )
            result_ref = persist_phase5_candidate_assessment(ctx.store, result)
            if load_phase5_candidate_assessment(ctx.store, result_ref) != result:
                return _failure(state, "phase5_result_not_established")
            threshold = resolve_judge_threshold_basis(
                ctx.store, basis_ref, selected_judge_threshold_registry()
            )
            if threshold.status != "current":
                return _failure(state, "phase5_threshold_registry_changed")
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
            return _failure(state, "phase5_source_admission_not_established")
        output = branch_state(state, write_paths=_SPEC.state_writes).state
        output.artifacts_index[_RESULT_REF] = result_ref
        return NodeOutcome(
            status="ok",
            state=output,
            artifacts=[result_ref, judge_ref, basis_ref],
            events=[
                NodeEvent(level="info", message="Candidate-only Phase-5 diagnostic completed.")
            ],
        )


__all__ = ["EvaluateVerifiedPolicyPhase5Node"]
