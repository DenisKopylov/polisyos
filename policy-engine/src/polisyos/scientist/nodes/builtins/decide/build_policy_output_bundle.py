"""Public decide build policy output bundle module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.analytics.cross_graph import load_cross_graph_evidence_profile
from polisyos.ir.analytics.distributional import load_distributional_report
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.governance.calibration_validation import (
    load_calibration_validation_bundle,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
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
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    PolicyBrief,
    load_policy_artifact_bundle,
)
from polisyos.scientist.policy_design.phase3 import resolve_phase3_gate
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    load_policy_candidate_schema,
)
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult
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
    ],
    state_writes=[
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
    ],
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
        if (
            state.policy_output_bundle_ref is not None
            and ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in state.artifacts_index
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
        promotion_result = _parse_model(
            state.params.get("policy_promotion_result"),
            PolicyPromotionResult,
        )
        judge_verdict = _parse_model(state.params.get("judge_verdict"), JudgeVerdict)
        if judge_verdict is None and promotion_result is not None:
            judge_verdict = promotion_result.judge_verdict
        readiness_ref = state.artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
        readiness_contract = _resolve_readiness_contract(ctx, state, readiness_ref)
        if readiness_contract is None and promotion_result is not None:
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
        policy_brief = _parse_model(state.params.get("policy_brief"), PolicyBrief)
        translator_compliance = _parse_model(
            state.params.get("translator_compliance"),
            TranslatorComplianceResult,
        )
        degraded_events: list[NodeEvent] = []

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
            loader=lambda ref: load_distributional_report(ctx.store, ref),
        )
        cross_graph_profile = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF),
            artifact_key=ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
            reason="cross_graph_profile_load_failed",
            loader=lambda ref: load_cross_graph_evidence_profile(ctx.store, ref),
        )
        stress_test_report = _load_optional_artifact(
            ctx,
            state,
            degraded_events,
            artifact_ref=stress_test_ref,
            artifact_key=ARTIFACT_STRESS_TEST_REPORT_REF,
            reason="stress_test_report_load_failed",
            loader=lambda ref: StressTestReport.model_validate(
                from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
            ),
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
                load_uncertainty_envelope(ctx.store, ref)
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
            pareto_snapshot=pareto_snapshot,
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
            runtime_artifacts_index=dict(state.artifacts_index),
            runtime_reports_index=dict(state.reports_index),
            runtime_params_snapshot=_snapshot_runtime_params(state.params),
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
        try:
            bundle_ref = PolicyArtifactBuilder().build(ctx.store, build_input)
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
    workflow_id = str(state.params.get("workflow_id") or "").strip().lower()
    if workflow_id == "scientist_policy_design":
        return True
    raw = state.params.get("policy_mode")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _resolve_candidate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[PolicyCandidateSchema | None, ArtifactRef | None]:
    payload = state.params.get("policy_candidate_schema")
    if isinstance(payload, dict):
        return PolicyCandidateSchema.model_validate(payload), None
    ref = _maybe_artifact_ref(state.params.get("policy_candidate_ref"))
    if ref is not None:
        return load_policy_candidate_schema(ctx.store, ref), ref
    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return None, None
    bundle = TrinityBundle.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
    )
    return (
        PolicyCandidateSchema.from_trinity_bundle(
            bundle,
            candidate_id=str(state.params.get("policy_candidate_id") or state.run_id),
            metadata={"workflow_id": str(state.params.get("workflow_id") or "")},
        ),
        trinity_ref,
    )


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
    seen: set[str] = set()
    for item in items:
        artifact_id = str(item.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(item)
    return output


def _snapshot_runtime_params(params: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _snapshot_runtime_value(value) for key, value in params.items()}


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
