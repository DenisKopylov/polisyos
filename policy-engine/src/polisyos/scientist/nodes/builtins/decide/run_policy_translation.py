"""Public decide run policy translation module API."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _is_policy_mode,
    _parse_model,
    _resolve_candidate,
    _resolve_readiness_contract,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_promotion import (
    _load_cross_graph_profile,
    _load_distributional_report,
    _load_search_uncertainty,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
)
from polisyos.scientist.policy_design.output import PolicyArtifactBuilder, PolicyArtifactBuildInput
from polisyos.scientist.policy_design.translator import (
    PolicyTranslatorWorker,
    TranslatorInputBundle,
)
from polisyos.scientist.methods.search.judge_stack import JudgeVerdict, PolicyPromotionResult
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistrySnapshot
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    enforce_phase5_publication,
    run_phase5_artifact_preflight,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_policy_translation@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Policy Translation",
    description="Generate a PolicyBrief for contract-bound promoted policy artifacts.",
    tags=["builtin", "decide", "policy_design", "translator"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.workflow_id",
        "params.policy_mode",
        "params.policy_candidate_schema",
        "params.policy_evaluation",
        "params.policy_promotion_result",
        "params.judge_verdict",
        "params.policy_brief",
        f"artifacts_index.{ARTIFACT_DECISION_READINESS_CONTRACT_REF}",
        f"artifacts_index.{ARTIFACT_STRESS_TEST_REPORT_REF}",
    ],
    state_writes=[
        "params.policy_brief",
        "policy_brief_ref",
        f"artifacts_index.{ARTIFACT_POLICY_BRIEF_REF}",
        f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
    ],
    produces=[
        ARTIFACT_POLICY_BRIEF_REF,
        ARTIFACT_VALIDATION_REPORT_REF,
        ARTIFACT_JUDGE_VERDICT_REF,
    ],
)


@dataclass(frozen=True)
class RunPolicyTranslationNode:
    """Run policy translation node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if not _is_policy_mode(state):
            return NodeOutcome(status="skip", state=state)
        existing = state.params.get("policy_brief")
        if isinstance(existing, dict) and state.policy_brief_ref is not None:
            return NodeOutcome(status="ok", state=state)

        readiness_ref = state.artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
        readiness = _resolve_readiness_contract(ctx, state, readiness_ref)
        if not _brief_required(readiness):
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info", message="Readiness does not require PolicyBrief translation."
                    )
                ],
            )

        promotion_result = _parse_model(
            state.params.get("policy_promotion_result"),
            PolicyPromotionResult,
        )
        if promotion_result is None or not promotion_result.promotion_decision.promoted:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="Promotion path did not produce a promoted artifact; skip translation.",
                    )
                ],
            )

        candidate, candidate_ref = _resolve_candidate(ctx, state)
        if candidate is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Policy translation requires a policy candidate.",
                ),
            )

        build_input = _policy_build_input(
            ctx, state, candidate, candidate_ref, readiness, promotion_result
        )
        builder = PolicyArtifactBuilder()
        constraint_report = builder._build_constraint_report(build_input)
        subgroup_report = builder._build_subgroup_report(build_input)
        uncertainty_report = builder._build_uncertainty_report(build_input)
        transport_report = builder._build_transportability_report(build_input)
        gate_packet = builder._build_governance_gate_packet(build_input)
        implementation_plan = builder._build_implementation_plan(build_input)
        dossier = builder._build_dossier(
            source=build_input,
            constraint_report=constraint_report,
            subgroup_report=subgroup_report,
            uncertainty_report=uncertainty_report,
            transport_report=transport_report,
            gate_packet=gate_packet,
            implementation_plan=implementation_plan,
        )
        translator_bundle = TranslatorInputBundle(
            dossier=dossier,
            readiness_contract=readiness,
            constraint_report=constraint_report,
            subgroup_report=subgroup_report,
            uncertainty_report=uncertainty_report,
            implementation_plan=implementation_plan,
            run_id=state.run_id,
        )
        brief, brief_ref = PolicyTranslatorWorker().translate_and_persist(
            ctx.store, translator_bundle
        )
        publication = run_phase5_artifact_preflight(
            ctx,
            state,
            Phase5ArtifactPreflightInput(
                artifact_ref=brief_ref,
                artifact_kind="scientist.policy_brief",
                artifact_payload=brief.model_dump(mode="json"),
                generated_for="scientist.policy_brief",
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
                    message="Phase 5 validation blocked policy brief publication",
                    details={
                        "validation_report_ref": str(publication.validation_ref.artifact_id),
                        "verdict": publication.validation_report.verdict,
                        "readiness": publication.validation_report.readiness,
                        "gate_failures": list(publication.validation_report.gate_failures),
                    },
                ),
            )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["policy_brief"] = brief.model_dump(mode="json")
        new_state.policy_brief_ref = brief_ref
        new_state.artifacts_index[ARTIFACT_POLICY_BRIEF_REF] = brief_ref
        validation_ref = ArtifactRef.model_validate(dict(publication.validation_ref))
        new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
        if publication.judge_verdict_ref is not None:
            new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = publication.judge_verdict_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                artifact
                for artifact in (brief_ref, validation_ref, publication.judge_verdict_ref)
                if artifact is not None
            ],
            events=[
                NodeEvent(
                    level="info",
                    message="Policy brief translated.",
                    attrs={"readiness": readiness.readiness_level.value},
                )
            ],
        )


def _brief_required(readiness: DecisionReadinessContract | None) -> bool:
    if readiness is None:
        return False
    required = {
        DecisionReadiness.EXTERNAL_BRIEFING,
        DecisionReadiness.SIMULATION_READY,
        DecisionReadiness.RECOMMENDATION_READY,
        DecisionReadiness.DEPLOYMENT_READY,
    }
    return readiness.readiness_level in required


def _policy_build_input(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate,
    candidate_ref,
    readiness: DecisionReadinessContract,
    promotion_result: PolicyPromotionResult,
) -> PolicyArtifactBuildInput:
    evaluation_vector = _parse_model(
        state.params.get("policy_evaluation"),
        __import__(
            "polisyos.scientist.policy_design.objectives", fromlist=["PolicyEvaluationVector"]
        ).PolicyEvaluationVector,
    )
    judge_verdict = _parse_model(state.params.get("judge_verdict"), JudgeVerdict)
    if judge_verdict is None:
        judge_verdict = promotion_result.judge_verdict
    return PolicyArtifactBuildInput(
        loop_id=str(state.params.get("policy_loop_id") or state.run_id),
        run_id=state.run_id,
        candidate=candidate,
        candidate_hash=candidate.candidate_hash(),
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
        evaluation_ref=None,
        pareto_snapshot=_parse_model(
            state.params.get("pareto_registry_snapshot"), ParetoRegistrySnapshot
        ),
        promotion_result=promotion_result,
        judge_verdict=judge_verdict,
        readiness_contract=readiness,
        readiness_ref=promotion_result.readiness_ref,
        distributional_report=_load_distributional_report(ctx, state),
        cross_graph_profile=_load_cross_graph_profile(ctx, state),
        uncertainty_envelope=_load_search_uncertainty(ctx, state),
        stress_test_report=None,
        stress_test_report_ref=state.artifacts_index.get(ARTIFACT_STRESS_TEST_REPORT_REF),
        policy_brief=None,
        translator_compliance=None,
        constraint_findings=[],
        mutation_hints=[],
        metadata={"workflow_id": str(state.params.get("workflow_id") or "")},
    )


__all__ = ["RunPolicyTranslationNode"]
