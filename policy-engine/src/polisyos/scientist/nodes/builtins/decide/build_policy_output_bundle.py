"""Public decide build policy output bundle module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.analytics.cross_graph import load_cross_graph_evidence_profile
from polisyos.ir.analytics.distributional import load_distributional_report
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.scientist.governance.calibration_validation import (
    load_calibration_validation_bundle,
)
from polisyos.scientist.governance.stress_scenarios import load_stress_test_report
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.methods.search.judge_stack import (
    JudgeVerdict,
    PolicyPromotionResult,
    to_search_uncertainty_envelope,
)
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistrySnapshot
from polisyos.scientist.methods.search.readiness import (
    DecisionReadinessContract,
    load_decision_readiness_contract,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS,
    _CURRENT_POLICY_PROJECTION_WRITE_PATHS,
    _CURRENT_POLICY_PROMOTION_PARAM_KEYS,
    _is_policy_mode_state,
    _resolve_current_policy_promotion_result,
    project_policy_promotion_state,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CHAMPION_POLICY_DOSSIER_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONSTRAINT_SATISFACTION_REPORT_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_GOVERNANCE_GATE_PACKET_REF,
    ARTIFACT_IMPLEMENTATION_PLAN_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_POLICY_FRONTIER_REPORT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_POLICY_TRANSPORTABILITY_REPORT_REF,
    ARTIFACT_POLICY_UNCERTAINTY_REPORT_REF,
    ARTIFACT_REJECTED_ALTERNATIVES_SUMMARY_REF,
    ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF,
    ARTIFACT_RESEARCH_DAG_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_SUBGROUP_IMPACT_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    PolicyArtifactBundle,
    PolicyBrief,
    _resolve_run_local_candidate_frontier_report_ref,
    load_policy_artifact_bundle,
    load_replayable_audit_bundle,
)
from polisyos.scientist.policy_design.phase3 import (
    _load_bound_candidate_source_state,
    resolve_phase3_gate,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    load_policy_candidate_schema,
)
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    enforce_phase5_publication,
    run_phase5_artifact_preflight,
)

_LOGGER = get_logger(__name__)
_OPTIONAL_ARTIFACT_LOAD_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_SNAPSHOT_MODEL_DUMP_ERRORS = (
    AttributeError,
    TypeError,
    ValueError,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_policy_output_bundle@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Policy Output Bundle",
    description="Compose the typed policy artifact bundle for policy-design workflow.",
    tags=["builtin", "decide", "policy_design"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.workflow_id",
        "params.policy_mode",
        "params.policy_candidate_schema",
        "params.policy_candidate_ref",
        "params.policy_candidate_id",
        "params.policy_evaluation",
        "params.pareto_registry_snapshot",
        "params.policy_promotion_result",
        "params.judge_verdict",
        "params.decision_readiness_contract",
        "params.policy_brief",
        "params.translator_compliance",
        "params.funnel_outcome",
        "params._funnel_outcome",
        "params.audit_refs",
        "params.actionable_side_information_refs",
        "inputs",
        "artifacts_index",
        "reports_index",
        "policy_output_bundle_ref",
        *(f"params.{key}" for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS),
        "params.reported_policy_promotion_history",
    ],
    state_writes=list(
        dict.fromkeys(
            [
                "policy_output_bundle_ref",
                "policy_brief_ref",
                "champion_policy_dossier_ref",
                f"artifacts_index.{ARTIFACT_POLICY_OUTPUT_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_POLICY_FRONTIER_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_CHAMPION_POLICY_DOSSIER_REF}",
                f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
                f"artifacts_index.{ARTIFACT_POLICY_BRIEF_REF}",
                f"artifacts_index.{ARTIFACT_CONSTRAINT_SATISFACTION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_SUBGROUP_IMPACT_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_POLICY_UNCERTAINTY_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_POLICY_TRANSPORTABILITY_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_GOVERNANCE_GATE_PACKET_REF}",
                f"artifacts_index.{ARTIFACT_IMPLEMENTATION_PLAN_REF}",
                f"artifacts_index.{ARTIFACT_REJECTED_ALTERNATIVES_SUMMARY_REF}",
                f"artifacts_index.{ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_DECISION_READINESS_CONTRACT_REF}",
                f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                *_CURRENT_POLICY_PROJECTION_WRITE_PATHS,
            ]
        )
    ),
    produces=[
        ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
        ARTIFACT_VALIDATION_REPORT_REF,
        ARTIFACT_JUDGE_VERDICT_REF,
    ],
)


@dataclass(frozen=True)
class BuildPolicyOutputBundleNode:
    """Build policy output bundle node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if not _is_policy_mode(state):
            return NodeOutcome(status="skip", state=state)
        state = project_policy_promotion_state(state, ctx=ctx)
        current_promotion_result, _promotion_reason = _resolve_current_policy_promotion_result(
            state
        )
        if (
            state.policy_output_bundle_ref is not None
            and ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in state.artifacts_index
        ):
            try:
                existing_bundle = load_policy_artifact_bundle(
                    ctx.store, state.policy_output_bundle_ref
                )
            except _OPTIONAL_ARTIFACT_LOAD_ERRORS:
                existing_bundle = None
            if existing_bundle is not None and not (
                existing_bundle.promotion_result is not None
                and existing_bundle.promotion_result.promotion_decision.promoted
                and current_promotion_result is None
            ):
                return NodeOutcome(status="ok", state=state)

        candidate, candidate_ref = _resolve_candidate(ctx, state)
        if candidate is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Policy output bundle requires a policy candidate or Trinity input.",
                ),
            )

        evaluation_vector = _parse_model(
            state.params.get("policy_evaluation"),
            PolicyEvaluationVector,
        )
        promotion_result = current_promotion_result
        if promotion_result is None:
            judge_verdict = None
            readiness_ref = None
            readiness_contract = None
        else:
            judge_verdict = _parse_model(state.params.get("judge_verdict"), JudgeVerdict)
            if judge_verdict is None:
                judge_verdict = promotion_result.judge_verdict
            readiness_ref = state.artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
            readiness_contract = _resolve_readiness_contract(ctx, state, readiness_ref)
            if readiness_contract is None:
                readiness_contract = promotion_result.readiness_contract
                readiness_ref = promotion_result.readiness_ref

        if evaluation_vector is None and promotion_result is None and readiness_contract is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=(
                        "Policy output bundle requires at least one of policy_evaluation, "
                        "policy_promotion_result, or decision_readiness_contract."
                    ),
                ),
            )

        pareto_snapshot = _parse_model(
            state.params.get("pareto_registry_snapshot"),
            ParetoRegistrySnapshot,
        )
        expected_frontier_loop_id = str(
            state.params.get("policy_loop_id") or f"{state.run_id}:policy_search"
        )
        run_local_frontier_ref, frontier_ref_reason = (
            _resolve_run_local_candidate_frontier_report_ref(
                ctx.store,
                state.artifacts_index.get(ARTIFACT_POLICY_FRONTIER_REPORT_REF),
                expected_run_id=state.run_id,
                expected_loop_id=expected_frontier_loop_id,
            )
        )
        if promotion_result is None:
            policy_brief = None
            translator_compliance = None
        else:
            policy_brief = _parse_model(state.params.get("policy_brief"), PolicyBrief)
            translator_compliance = _parse_model(
                state.params.get("translator_compliance"),
                TranslatorComplianceResult,
            )
        degraded_events: list[NodeEvent] = []
        if frontier_ref_reason not in {None, "frontier_source_report_absent"}:
            degraded_events.append(
                NodeEvent(
                    level="warn",
                    message="Run-local frontier evidence was not preserved into the policy bundle.",
                    code="policy_output_bundle.frontier_source_not_preserved",
                    attrs={"reason": frontier_ref_reason},
                )
            )
        if pareto_snapshot is not None:
            degraded_events.append(
                NodeEvent(
                    level="warn",
                    message=(
                        "Registry snapshot was not used as a complete source denominator; "
                        "the frontier remains candidate-limited."
                    ),
                    code="policy_output_bundle.frontier_source_denominator_not_established",
                    attrs={"reason": "independent_source_reconciliation_missing"},
                )
            )

        stress_test_ref = state.artifacts_index.get(ARTIFACT_STRESS_TEST_REPORT_REF)
        calibration_validation_ref = state.artifacts_index.get(
            ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF
        )
        distributional_report = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF),
            artifact_key=ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
            reason="distributional_report_load_failed",
            loader=lambda ref: load_distributional_report(
                _ensure_ir_artifact_store(ctx.store), ref
            ),
        )
        cross_graph_profile = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF),
            artifact_key=ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
            reason="cross_graph_profile_load_failed",
            loader=lambda ref: load_cross_graph_evidence_profile(
                _ensure_ir_artifact_store(ctx.store), ref
            ),
        )
        stress_test_report = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=stress_test_ref,
            artifact_key=ARTIFACT_STRESS_TEST_REPORT_REF,
            reason="stress_test_report_load_failed",
            loader=lambda ref: load_stress_test_report(ctx.store, ref),
        )
        calibration_validation_bundle = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=calibration_validation_ref,
            artifact_key=ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
            reason="calibration_validation_bundle_load_failed",
            loader=lambda ref: load_calibration_validation_bundle(ctx.store, ref),
        )
        uncertainty_envelope = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=state.artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF),
            artifact_key=ARTIFACT_CAUSAL_ENVELOPE_REF,
            reason="uncertainty_envelope_load_failed",
            loader=lambda ref: to_search_uncertainty_envelope(
                load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref)
            ),
        )
        upstream_audit_refs, actionable_side_information_refs = _collect_upstream_refs(state)
        phase3_gate = resolve_phase3_gate(ctx, state, candidate=candidate)
        if not phase3_gate.gate_passed:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=(
                        "Policy output bundle is blocked by Phase 3 certificate gate: "
                        + ", ".join(phase3_gate.blocking_reasons)
                    ),
                ),
            )

        build_input = PolicyArtifactBuildInput(
            loop_id=str(state.params.get("policy_loop_id") or state.run_id),
            run_id=state.run_id,
            candidate=candidate,
            candidate_hash=candidate.candidate_hash(),
            candidate_ref=candidate_ref,
            evaluation_vector=evaluation_vector,
            evaluation_ref=_maybe_artifact_ref(state.params.get("policy_evaluation_ref")),
            pareto_snapshot=None,
            run_local_frontier_report_ref=run_local_frontier_ref,
            run_local_frontier_report_loop_id=expected_frontier_loop_id,
            promotion_result=promotion_result,
            judge_verdict=judge_verdict,
            readiness_contract=readiness_contract,
            readiness_ref=readiness_ref,
            distributional_report=distributional_report,
            cross_graph_profile=cross_graph_profile,
            uncertainty_envelope=uncertainty_envelope,
            stress_test_report=stress_test_report,
            stress_test_report_ref=stress_test_ref,
            calibration_validation_bundle=calibration_validation_bundle,
            calibration_validation_bundle_ref=calibration_validation_ref,
            policy_brief=policy_brief,
            translator_compliance=translator_compliance,
            phase3_gate=phase3_gate,
            constraint_findings=_string_list(state.params.get("constraint_findings")),
            mutation_hints=_string_list(state.params.get("mutation_hints")),
            audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
            runtime_input_refs=dict(state.inputs),
            runtime_artifacts_index=_snapshot_policy_runtime_artifacts_index(
                state.artifacts_index,
                current_promotion_result=current_promotion_result,
            ),
            runtime_reports_index=dict(state.reports_index),
            runtime_params_snapshot=_snapshot_policy_runtime_params(
                state.params,
                current_promotion_result=current_promotion_result,
            ),
            execution_profile=state.execution_profile,
            metadata={
                "workflow_id": str(state.params.get("workflow_id") or ""),
                "research_dag_status": (
                    "available"
                    if state.artifacts_index.get(ARTIFACT_RESEARCH_DAG_REF) is not None
                    else "legacy_missing"
                ),
            },
        )
        if not isinstance(ctx, ClaimCapableExecutionContext):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="claim_ledger_owner_not_established",
                    message="claim_ledger_owner_not_established",
                ),
            )
        try:
            bundle_ref = PolicyArtifactBuilder().build(
                ctx.store,
                build_input,
                claim_owner=ctx.claim_ledger_owner,
            )
        except ValueError as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=str(exc),
                ),
            )
        bundle = load_policy_artifact_bundle(ctx.store, bundle_ref)
        publication = run_phase5_artifact_preflight(
            ctx,
            state,
            Phase5ArtifactPreflightInput(
                artifact_ref=bundle_ref,
                artifact_kind="scientist.policy_artifact_bundle",
                artifact_payload=bundle.model_dump(mode="json"),
                generated_for="scientist.policy_artifact_bundle",
                analyst_facing=True,
                base_readiness="ready",
            ),
        )
        try:
            enforce_phase5_publication(publication)
        except Phase5ValidationBlocked:
            new_state = branch_state(
                state,
                write_paths=(
                    f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                    f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                ),
            ).state
            new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = ArtifactRef.model_validate(
                dict(publication.validation_ref)
            )
            if publication.judge_verdict_ref is not None:
                new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = (
                    publication.judge_verdict_ref
                )
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=[
                    artifact
                    for artifact in (
                        ArtifactRef.model_validate(dict(publication.validation_ref)),
                        publication.judge_verdict_ref,
                    )
                    if artifact is not None
                ],
                events=[
                    NodeEvent(
                        level="error",
                        message="Phase 5 validation blocked policy output publication.",
                    )
                ],
                error=NodeError(
                    code="phase5_validation_failed",
                    message="Phase 5 validation blocked analyst-facing policy output",
                    details={
                        "validation_report_ref": str(publication.validation_ref.artifact_id),
                        "verdict": publication.validation_report.verdict,
                        "readiness": publication.validation_report.readiness,
                        "gate_failures": list(publication.validation_report.gate_failures),
                    },
                ),
            )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.policy_output_bundle_ref = bundle_ref
        new_state.policy_brief_ref = bundle.policy_brief_ref
        new_state.champion_policy_dossier_ref = bundle.champion_policy_dossier_ref
        new_state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF] = bundle_ref
        new_state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] = (
            bundle.policy_frontier_report_ref
        )
        new_state.artifacts_index[ARTIFACT_CHAMPION_POLICY_DOSSIER_REF] = (
            bundle.champion_policy_dossier_ref
        )
        if bundle.claims_ref is not None:
            new_state.artifacts_index[ARTIFACT_CLAIMS_REF] = bundle.claims_ref
        new_state.artifacts_index[ARTIFACT_POLICY_BRIEF_REF] = bundle.policy_brief_ref
        new_state.artifacts_index[ARTIFACT_CONSTRAINT_SATISFACTION_REPORT_REF] = (
            bundle.constraint_satisfaction_report_ref
        )
        new_state.artifacts_index[ARTIFACT_SUBGROUP_IMPACT_REPORT_REF] = (
            bundle.subgroup_impact_report_ref
        )
        new_state.artifacts_index[ARTIFACT_POLICY_UNCERTAINTY_REPORT_REF] = (
            bundle.uncertainty_report_ref
        )
        new_state.artifacts_index[ARTIFACT_POLICY_TRANSPORTABILITY_REPORT_REF] = (
            bundle.transportability_report_ref
        )
        new_state.artifacts_index[ARTIFACT_GOVERNANCE_GATE_PACKET_REF] = (
            bundle.governance_gate_packet_ref
        )
        new_state.artifacts_index[ARTIFACT_IMPLEMENTATION_PLAN_REF] = bundle.implementation_plan_ref
        new_state.artifacts_index[ARTIFACT_REJECTED_ALTERNATIVES_SUMMARY_REF] = (
            bundle.rejected_alternatives_summary_ref
        )
        new_state.artifacts_index[ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF] = (
            bundle.replayable_audit_bundle_ref
        )
        if bundle.decision_readiness_contract_ref is not None:
            new_state.artifacts_index[ARTIFACT_DECISION_READINESS_CONTRACT_REF] = (
                bundle.decision_readiness_contract_ref
            )
        new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = ArtifactRef.model_validate(
            dict(publication.validation_ref)
        )
        if publication.judge_verdict_ref is not None:
            new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = publication.judge_verdict_ref

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                artifact
                for artifact in (
                    bundle_ref,
                    bundle.claims_ref,
                    ArtifactRef.model_validate(dict(publication.validation_ref)),
                    publication.judge_verdict_ref,
                )
                if artifact is not None
            ],
            events=[
                *degraded_events,
                NodeEvent(
                    level="info",
                    message="Policy artifact bundle created.",
                    attrs={
                        "candidate_id": candidate.candidate_id,
                        "has_readiness": bundle.decision_readiness_contract_ref is not None,
                        "has_claims": bundle.claims_ref is not None,
                        "has_stress_test": bundle.stress_test_report_ref is not None,
                    },
                ),
            ],
        )


def _is_policy_mode(state: ExperimentState) -> bool:
    return _is_policy_mode_state(state)


def _prepare_policy_candidate_state_for_direct_consumer(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    preserve_source_bound_candidate_bundle: bool = False,
) -> ExperimentState:
    """Remove caller promotion state, retaining only a fully source-bound candidate bundle."""
    if not _is_policy_mode(state):
        return state
    preserved_state_refs: dict[str, ArtifactRef] = {}
    preserved_artifact_refs: dict[str, ArtifactRef] = {}
    if preserve_source_bound_candidate_bundle:
        candidate_view = project_policy_promotion_state(state, archive_prior=False, ctx=ctx)
        candidate, candidate_ref = _resolve_candidate(ctx, candidate_view)
        existing_ref = _current_policy_output_bundle_ref(state)
        if (
            candidate is not None
            and existing_ref is not None
            and _candidate_only_bundle_matches_source(
                ctx,
                candidate_view,
                existing_ref,
                candidate=candidate,
                candidate_ref=candidate_ref,
            )
        ):
            bundle = load_policy_artifact_bundle(ctx.store, existing_ref)
            preserved_state_refs = {
                "policy_output_bundle_ref": existing_ref,
                "policy_brief_ref": bundle.policy_brief_ref,
                "champion_policy_dossier_ref": bundle.champion_policy_dossier_ref,
            }
            preserved_artifact_refs = {
                ARTIFACT_POLICY_OUTPUT_BUNDLE_REF: existing_ref,
                ARTIFACT_POLICY_FRONTIER_REPORT_REF: bundle.policy_frontier_report_ref,
                ARTIFACT_CHAMPION_POLICY_DOSSIER_REF: bundle.champion_policy_dossier_ref,
                ARTIFACT_POLICY_BRIEF_REF: bundle.policy_brief_ref,
                ARTIFACT_CONSTRAINT_SATISFACTION_REPORT_REF: (
                    bundle.constraint_satisfaction_report_ref
                ),
                ARTIFACT_SUBGROUP_IMPACT_REPORT_REF: bundle.subgroup_impact_report_ref,
                ARTIFACT_POLICY_UNCERTAINTY_REPORT_REF: bundle.uncertainty_report_ref,
                ARTIFACT_POLICY_TRANSPORTABILITY_REPORT_REF: bundle.transportability_report_ref,
                ARTIFACT_GOVERNANCE_GATE_PACKET_REF: bundle.governance_gate_packet_ref,
                ARTIFACT_IMPLEMENTATION_PLAN_REF: bundle.implementation_plan_ref,
                ARTIFACT_REJECTED_ALTERNATIVES_SUMMARY_REF: (
                    bundle.rejected_alternatives_summary_ref
                ),
                ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF: bundle.replayable_audit_bundle_ref,
            }
            if bundle.claims_ref is not None:
                preserved_artifact_refs[ARTIFACT_CLAIMS_REF] = bundle.claims_ref
    return project_policy_promotion_state(
        state,
        ctx=ctx,
        preserved_state_refs=preserved_state_refs,
        preserved_artifact_refs=preserved_artifact_refs,
    )


def _current_policy_output_bundle_ref(state: ExperimentState) -> ArtifactRef | None:
    state_ref = state.policy_output_bundle_ref
    indexed_ref = state.artifacts_index.get(ARTIFACT_POLICY_OUTPUT_BUNDLE_REF)
    if state_ref is None or indexed_ref is None:
        return None
    if artifact_ref_identity_key(state_ref) != artifact_ref_identity_key(indexed_ref):
        return None
    return state_ref


def _candidate_only_bundle_matches_source(
    ctx: ExecutionContext,
    state: ExperimentState,
    bundle_ref: ArtifactRef,
    *,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef | None,
) -> bool:
    """Recompute the persisted candidate-only bundle's complete runtime source binding."""
    try:
        bundle = load_policy_artifact_bundle(ctx.store, bundle_ref)
        audit = load_replayable_audit_bundle(ctx.store, bundle.replayable_audit_bundle_ref)
    except _OPTIONAL_ARTIFACT_LOAD_ERRORS:
        return False

    if (
        bundle.candidate_id != candidate.candidate_id
        or bundle.metadata.get("candidate_hash") != candidate.candidate_hash()
        or bundle.decision_readiness_contract_ref is not None
        or bundle.metadata.get("judge_composite_decision") is not None
        or audit.run_id != state.run_id
        or audit.execution_profile != state.execution_profile
        or audit.workflow_id != (str(state.params.get("workflow_id") or "") or None)
        or audit.readiness_ref is not None
        or not _same_artifact_ref(candidate_ref, audit.candidate_ref)
        or not _same_artifact_ref(
            _maybe_artifact_ref(state.params.get("policy_evaluation_ref")),
            audit.evaluation_ref,
        )
    ):
        return False

    for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS:
        if key == "policy_promotion_projection_status":
            status = audit.runtime_params_snapshot.get(key)
            if status is not None and not (
                isinstance(status, Mapping)
                and status.get("status") == "reported_only"
                and status.get("authority_status") == "not_established"
            ):
                return False
        elif key in audit.runtime_params_snapshot:
            return False
    if any(key in audit.runtime_artifacts_index for key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS):
        return False

    expected_params = _candidate_runtime_params(state.params)
    observed_params = _candidate_runtime_params(audit.runtime_params_snapshot)
    if expected_params != observed_params:
        return False
    return (
        _artifact_ref_mappings_match(state.inputs, audit.runtime_input_refs)
        and _artifact_ref_mappings_match(
            {
                key: value
                for key, value in state.artifacts_index.items()
                if key not in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS
            },
            audit.runtime_artifacts_index,
        )
        and _artifact_ref_mappings_match(state.reports_index, audit.runtime_reports_index)
    )


def _candidate_runtime_params(params: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _snapshot_runtime_params(dict(params))
    for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS:
        snapshot.pop(key, None)
    snapshot.pop("reported_policy_promotion_history", None)
    return snapshot


def _same_artifact_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return artifact_ref_identity_key(left) == artifact_ref_identity_key(right)


def _artifact_ref_mappings_match(
    left: Mapping[str, ArtifactRef],
    right: Mapping[str, ArtifactRef],
) -> bool:
    return set(left) == set(right) and all(
        _same_artifact_ref(left[key], right[key]) for key in left
    )


def _resolve_candidate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[PolicyCandidateSchema | None, ArtifactRef | None]:
    source_state = _load_bound_candidate_source_state(ctx, state)
    if source_state is not None:
        state = source_state
    source_pointer = _candidate_source_pointer(state)
    payload = state.params.get("policy_candidate_schema")
    if source_pointer == "/params/policy_candidate_schema":
        return PolicyCandidateSchema.model_validate(payload), None
    ref = _maybe_artifact_ref(state.params.get("policy_candidate_ref"))
    if source_pointer == "/params/policy_candidate_ref" and ref is not None:
        return load_policy_candidate_schema(ctx.store, ref), ref
    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if source_pointer is None or trinity_ref is None:
        return None, None
    bundle = load_trinity_bundle_artifact(_ensure_ir_artifact_store(ctx.store), trinity_ref)
    return (
        PolicyCandidateSchema.from_trinity_bundle(
            bundle,
            candidate_id=str(state.params.get("policy_candidate_id") or state.run_id),
            metadata={"workflow_id": str(state.params.get("workflow_id") or "")},
        ),
        trinity_ref,
    )


def _candidate_source_pointer(state: ExperimentState) -> str | None:
    """Return the canonical runtime-state pointer selected by source precedence."""
    if isinstance(state.params.get("policy_candidate_schema"), dict):
        return "/params/policy_candidate_schema"
    if _maybe_artifact_ref(state.params.get("policy_candidate_ref")) is not None:
        return "/params/policy_candidate_ref"
    if state.inputs.get(INPUT_TRINITY_BUNDLE_REF) is not None:
        return f"/inputs/{INPUT_TRINITY_BUNDLE_REF}"
    return None


def _resolve_readiness_contract(
    ctx: ExecutionContext,
    state: ExperimentState,
    readiness_ref: ArtifactRef | None,
) -> DecisionReadinessContract | None:
    payload = state.params.get("decision_readiness_contract")
    parsed = _parse_model(payload, DecisionReadinessContract)
    if parsed is not None:
        return parsed
    if readiness_ref is not None:
        return load_decision_readiness_contract(ctx.store, readiness_ref)
    return None


def _parse_model(value: Any, model_cls: type[Any]) -> Any | None:
    if value is None:
        return None
    if isinstance(value, model_cls):
        return value
    if isinstance(value, dict):
        return model_cls.model_validate(value)
    return None


def _maybe_artifact_ref(value: Any) -> ArtifactRef | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        return ArtifactRef.model_validate(value)
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _collect_upstream_refs(
    state: ExperimentState,
) -> tuple[list[ArtifactRef], list[ArtifactRef]]:
    audit_refs = _coerce_artifact_ref_list(state.params.get("audit_refs"))
    actionable_refs = _coerce_artifact_ref_list(
        state.params.get("actionable_side_information_refs")
    )
    raw_funnel = state.params.get("funnel_outcome") or state.params.get("_funnel_outcome")
    if isinstance(raw_funnel, FunnelOutcome):
        audit_refs.extend(raw_funnel.audit_refs)
        actionable_refs.extend(raw_funnel.actionable_side_information_refs)
    elif isinstance(raw_funnel, dict):
        audit_refs.extend(_coerce_artifact_ref_list(raw_funnel.get("audit_refs")))
        actionable_refs.extend(
            _coerce_artifact_ref_list(raw_funnel.get("actionable_side_information_refs"))
        )
    return _dedupe_artifact_refs(audit_refs), _dedupe_artifact_refs(actionable_refs)


def _coerce_artifact_ref_list(value: Any) -> list[ArtifactRef]:
    if not isinstance(value, list):
        return []
    refs: list[ArtifactRef] = []
    for item in value:
        ref = _maybe_artifact_ref(item)
        if ref is not None:
            refs.append(ref)
    return refs


def _dedupe_artifact_refs(items: list[ArtifactRef]) -> list[ArtifactRef]:
    output: list[ArtifactRef] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in items:
        identity = artifact_ref_identity_key(item)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(item)
    return output


def _snapshot_runtime_params(params: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _snapshot_runtime_value(value) for key, value in params.items()}


def _snapshot_policy_runtime_params(
    params: dict[str, Any],
    *,
    current_promotion_result: PolicyPromotionResult | None,
) -> dict[str, Any]:
    """Keep caller promotion fields out of a current bundle without an owner receipt."""
    snapshot = dict(params)
    if current_promotion_result is None:
        for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS:
            snapshot.pop(key, None)
    return _snapshot_runtime_params(snapshot)


def _snapshot_policy_runtime_artifacts_index(
    artifacts_index: dict[str, ArtifactRef],
    *,
    current_promotion_result: PolicyPromotionResult | None,
) -> dict[str, ArtifactRef]:
    """Exclude stale bundle-output refs from a candidate-only bundle snapshot."""
    snapshot = dict(artifacts_index)
    if current_promotion_result is None:
        for key in _CURRENT_POLICY_OUTPUT_ARTIFACT_KEYS:
            snapshot.pop(key, None)
    return snapshot


def _snapshot_runtime_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_snapshot_runtime_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _snapshot_runtime_value(item) for key, item in value.items()}
    if isinstance(value, ArtifactRef):
        return value.model_dump(mode="json")
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump(mode="json")
        except _SNAPSHOT_MODEL_DUMP_ERRORS:
            try:
                return model_dump()
            except _SNAPSHOT_MODEL_DUMP_ERRORS:
                return str(value)
    return str(value)


def _load_optional_artifact(
    ctx: ExecutionContext,
    state: ExperimentState,
    events: list[NodeEvent],
    *,
    artifact_ref: ArtifactRef | None,
    artifact_key: str,
    reason: str,
    loader,
) -> Any | None:
    if artifact_ref is None:
        return None
    try:
        return loader(artifact_ref)
    except _OPTIONAL_ARTIFACT_LOAD_ERRORS as exc:
        envelope = emit_degraded_path(
            component="scientist.build_policy_output_bundle",
            operation="load_optional_artifact",
            reason=reason,
            exc=exc,
            details={
                "run_id": state.run_id,
                "artifact_key": artifact_key,
                "artifact_id": str(artifact_ref.artifact_id),
            },
            log=_LOGGER,
        )
        events.append(
            NodeEvent(
                level="warn",
                message="Policy output bundle optional artifact degraded",
                code="policy_output_bundle.optional_artifact_degraded",
                attrs={
                    "reason": str(envelope.get("reason", reason)),
                    "artifact_key": artifact_key,
                    "error_type": str(envelope.get("error_type", exc.__class__.__name__)),
                },
            )
        )
        return None


__all__ = ["BuildPolicyOutputBundleNode"]
