from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any

from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, CanonViolation, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.methods.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    STRATEGIC_GAMING_SUITE_ID,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.funnel.level0_static import Level0StaticValidator
from polisyos.scientist.methods.search.funnel.level1_heuristic import Level1CheapHeuristic
from polisyos.scientist.methods.search.funnel.level2_causal import Level2CausalPlausibility
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _RuntimeSession,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    build_vulnerabilities,
    load_causal_report,
    load_distributional_report_for_state,
    load_governance_report,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


def _ensure_stress_test_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    evaluation_vector: PolicyEvaluationVector,
    supplemental_reports: list[StressTestReport] | None = None,
    phase_d4_suite_ids: list[str] | None = None,
) -> ArtifactRef | None:
    existing_ref = state.artifacts_index.get(ARTIFACT_STRESS_TEST_REPORT_REF)
    replacement_suite_ids = [str(item) for item in (phase_d4_suite_ids or []) if str(item).strip()]
    if existing_ref is not None and not supplemental_reports and not replacement_suite_ids:
        return existing_ref

    report = _load_stress_test_report(ctx, existing_ref)
    if report is None:
        report = StressTestReport(
            report_id=f"stress_{state.run_id}",
            total_scenarios_evaluated=1,
            vulnerabilities=build_vulnerabilities(
                evaluation=evaluation_vector,
                distributional=load_distributional_report_for_state(ctx, state),
                causal_report=load_causal_report(ctx, state),
                governance_report=load_governance_report(ctx, state),
            ),
            robustness_score=0.0,
            metadata={
                "generated_by": "run_policy_blueprint_runtime",
                "phase_d4_suite_ids": [],
                "phase_d4_suite_scenario_counts": {},
                "base_total_scenarios_evaluated": 1,
            },
        )
    report = _merge_stress_test_reports(
        report,
        supplemental_reports or [],
        replacement_suite_ids=replacement_suite_ids,
    )
    report = _recompute_stress_test_report(report)
    return ctx.store.put_json(
        report,
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _merge_stress_test_reports(
    base_report: StressTestReport,
    supplemental_reports: list[StressTestReport],
    *,
    replacement_suite_ids: list[str] | None = None,
) -> StressTestReport:
    replacement_suite_ids_set = {
        str(item).strip() for item in (replacement_suite_ids or []) if str(item).strip()
    }
    if not supplemental_reports and not replacement_suite_ids_set:
        return base_report
    replacement_suite_ids_set.update(
        str(report.metadata.get("challenge_suite_id")).strip()
        for report in supplemental_reports
        if str(report.metadata.get("challenge_suite_id") or "").strip()
    )
    vulnerabilities = [
        item
        for item in base_report.vulnerabilities
        if _phase_d4_suite_id_from_vulnerability(item) not in replacement_suite_ids_set
    ]
    suite_scenario_counts = {
        str(key): int(value)
        for key, value in dict(
            base_report.metadata.get("phase_d4_suite_scenario_counts") or {}
        ).items()
        if str(key).strip()
    }
    for suite_id in replacement_suite_ids_set:
        suite_scenario_counts.pop(suite_id, None)
    base_total_scenarios = int(
        base_report.metadata.get(
            "base_total_scenarios_evaluated",
            max(
                int(base_report.total_scenarios_evaluated) - sum(suite_scenario_counts.values()), 0
            ),
        )
    )
    for supplemental in supplemental_reports:
        vulnerabilities.extend(supplemental.vulnerabilities)
        suite_id = supplemental.metadata.get("challenge_suite_id")
        if suite_id is not None and str(suite_id).strip():
            suite_scenario_counts[str(suite_id)] = int(supplemental.total_scenarios_evaluated)
    total_scenarios = base_total_scenarios + sum(suite_scenario_counts.values())
    return base_report.model_copy(
        update={
            "total_scenarios_evaluated": total_scenarios,
            "vulnerabilities": vulnerabilities,
            "metadata": {
                **dict(base_report.metadata),
                "phase_d4_suite_ids": sorted(suite_scenario_counts),
                "phase_d4_suite_scenario_counts": suite_scenario_counts,
                "base_total_scenarios_evaluated": base_total_scenarios,
            },
        }
    )


def _phase_d4_suite_id_from_vulnerability(vulnerability) -> str | None:
    candidate = str(getattr(vulnerability, "vulnerability_id", "")).strip()
    if ":" not in candidate:
        return None
    suite_id, _, _ = candidate.partition(":")
    if suite_id in {
        STRATEGIC_GAMING_SUITE_ID,
        MULTIPLICITY_DISCLOSURE_SUITE_ID,
        ABSTRACTION_LEAKAGE_SUITE_ID,
    }:
        return suite_id
    return None


def _recompute_stress_test_report(report: StressTestReport) -> StressTestReport:
    return report.model_copy(
        update={
            "critical_count": sum(
                1 for item in report.vulnerabilities if item.severity == "critical"
            ),
            "high_count": sum(1 for item in report.vulnerabilities if item.severity == "high"),
            "medium_count": sum(1 for item in report.vulnerabilities if item.severity == "medium"),
            "robustness_score": max(
                0.0,
                1.0
                - (
                    sum(
                        1
                        for item in report.vulnerabilities
                        if item.severity in {"critical", "high"}
                    )
                    / max(len(report.vulnerabilities), 1)
                ),
            ),
        }
    )


def _serialize_funnel_outcome(outcome: FunnelOutcome) -> dict[str, Any]:
    return {
        "ticket_id": outcome.ticket_id,
        "candidate_hash": outcome.candidate_hash,
        "compute_cost_usd": outcome.compute_cost_usd,
        "compute_cost_origin": outcome.compute_cost_origin,
        "trace": [
            {
                "fidelity_level": step.fidelity_level,
                "stage_name": step.stage_name,
                "objective_value": step.objective_value,
                "is_promising": step.is_promising,
                "duration_seconds": step.duration_seconds,
                "compute_cost_usd": step.compute_cost_usd,
                "compute_cost_origin": step.compute_cost_origin,
                "executed_work_packet_status": step.executed_work_packet_status,
                "executed_work_packet_ref": (
                    None
                    if step.executed_work_packet_ref is None
                    else step.executed_work_packet_ref.model_dump(mode="json")
                ),
                "routing_decision": step.routing_decision,
                "voi_action": step.voi_action,
                "voi_priority": step.voi_priority,
                "failure_count": step.failure_count,
                "blocker_count": step.blocker_count,
            }
            for step in outcome.trace
        ],
        "stage_results": {
            str(level): {
                "stage_name": result.stage_name,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "feedback": result.feedback,
                "failure_cards": [card.model_dump(mode="json") for card in result.failure_cards],
                "fidelity_level": result.fidelity_level,
                "compute_cost_usd": result.compute_cost_usd,
                "compute_cost_origin": result.compute_cost_origin,
                "executed_work_packet_status": result.executed_work_packet_status,
                "executed_work_packet_ref": (
                    None
                    if result.executed_work_packet_ref is None
                    else result.executed_work_packet_ref.model_dump(mode="json")
                ),
                "terminal_action": result.terminal_action,
            }
            for level, result in outcome.stage_results.items()
        },
        "final_action": outcome.final_action,
        "completed": outcome.completed,
        "degradation_mode": outcome.degradation_mode,
        "uncertainty_historical_max": outcome.uncertainty_envelope.model_dump(mode="json"),
        "uncertainty_current": (
            None
            if outcome.current_uncertainty_envelope is None
            else outcome.current_uncertainty_envelope.model_dump(mode="json")
        ),
        "uncertainty_observation_refs": [
            ref.model_dump(mode="json") for ref in outcome.uncertainty_observation_refs
        ],
        "uncertainty_intake_failures": list(outcome.uncertainty_intake_failures),
        "audit_refs": [ref.model_dump(mode="json") for ref in outcome.audit_refs],
        "actionable_side_information_refs": [
            ref.model_dump(mode="json") for ref in outcome.actionable_side_information_refs
        ],
    }


def _extract_level5_gate(outcome: FunnelOutcome) -> dict[str, Any]:
    level5 = outcome.stage_results.get(5)
    if level5 is None:
        return {"passed": False, "reason": "level5_not_executed"}
    return {
        "passed": level5.is_promising
        and level5.terminal_action not in {"reject", "defer_to_human"},
        "terminal_action": level5.terminal_action,
        "failure_count": len(level5.failure_cards),
        "critical_failures": [
            card.failure_type for card in level5.failure_cards if card.is_blocker
        ],
    }


def _load_stress_test_report(
    ctx: ExecutionContext,
    ref: ArtifactRef | None,
) -> StressTestReport | None:
    if ref is None:
        return None
    return StressTestReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))


def _find_non_finite_projection_values(value: Any) -> list[dict[str, str]]:
    """Locate non-finite leaves without changing the source projection."""
    findings: list[dict[str, str]] = []

    def visit(child: Any, location: str, ancestors: frozenset[int]) -> None:
        if type(child) is float:
            if not math.isfinite(child):
                kind = (
                    "nan"
                    if math.isnan(child)
                    else "positive_infinity"
                    if child > 0
                    else "negative_infinity"
                )
                findings.append({"location": location, "kind": kind})
            return

        child_id = id(child)
        if child_id in ancestors:
            return
        next_ancestors = ancestors | {child_id}
        if isinstance(child, BaseModel):
            members = child.model_dump(mode="python", by_alias=True, exclude_none=False)
            visit(members, location, ancestors)
        elif is_dataclass(child) and not isinstance(child, type):
            for field in fields(child):
                visit(getattr(child, field.name), f"{location}.{field.name}", next_ancestors)
        elif isinstance(child, Mapping):
            for key, member in child.items():
                key_location = (
                    f"{location}.{key}"
                    if isinstance(key, str) and key.isidentifier()
                    else f"{location}[{key!r}]"
                )
                visit(member, key_location, next_ancestors)
        elif isinstance(child, (list, tuple)):
            for index, member in enumerate(child):
                visit(member, f"{location}[{index}]", next_ancestors)

    visit(value, "$", frozenset())
    return findings


def _funnel_projection_failure_basis(outcome: FunnelOutcome) -> dict[str, Any]:
    """Project typed stage failure evidence into a finite diagnostic payload."""
    stage_evidence: list[dict[str, Any]] = []
    for level, result in sorted(outcome.stage_results.items()):
        feedback = result.feedback if isinstance(result.feedback, Mapping) else {}
        issues = feedback.get("issues")
        issue_messages = [
            issue["message"]
            for issue in (issues if isinstance(issues, (list, tuple)) else ())
            if isinstance(issue, Mapping) and isinstance(issue.get("message"), str)
        ]
        verdict = feedback.get("verdict")
        stage_evidence.append(
            {
                "fidelity_level": level,
                "stage_name": result.stage_name,
                "verdict": verdict if isinstance(verdict, str) else None,
                "failure_types": [card.failure_type for card in result.failure_cards],
                "issue_messages": issue_messages,
            }
        )
    return {
        "evaluation_status": outcome.evaluation_status,
        "final_action": outcome.final_action,
        "failure_types": [card.failure_type for card in outcome.failure_cards],
        "stage_evidence": stage_evidence,
    }


def _runtime_session_artifact_refs(session: _RuntimeSession) -> list[ArtifactRef]:
    """Retain references produced before final outcome projection was attempted."""
    refs: list[ArtifactRef] = []
    candidates: list[Any] = [
        session.candidate_ref,
        session.selection_vector_ref,
        session.selection_ref,
        session.evidence_ref,
        session.ambiguity_certificate_ref,
        session.platform_meta_ref,
        session.stress_report_ref,
        session.replay_bundle_ref,
        session.replay_verification_ref,
        session.governance_ref,
        session.hidden_holdout_ref,
        session.calibration_ref,
        *session.runtime_artifacts_index.values(),
    ]
    strategic_output = session.strategic_output
    if strategic_output is not None:
        candidates.extend(
            (
                strategic_output.strategic_scm_ref,
                strategic_output.strategic_response_bundle_ref,
            )
        )

    outcome = session.outcome
    if outcome is not None:
        candidates.extend((*outcome.audit_refs, *outcome.actionable_side_information_refs))
        for result in outcome.stage_results.values():
            candidates.extend(
                (
                    result.executed_work_packet_ref,
                    result.uncertainty_observation_ref,
                    result.actionable_side_information_ref,
                    *result.audit_refs,
                )
            )
        for step in outcome.trace:
            candidates.append(step.executed_work_packet_ref)

    seen: set[tuple[str, str | None, str, str]] = set()
    for candidate in candidates:
        if not isinstance(candidate, ArtifactRef):
            continue
        identity = (
            str(candidate.artifact_id),
            candidate.manifest_profile_sha256,
            candidate.kind,
            candidate.media_type,
        )
        if identity not in seen:
            seen.add(identity)
            refs.append(candidate)
    return refs


def _funnel_projection_refusal(
    session: _RuntimeSession,
    projection: Any,
    exc: Exception,
) -> NodeOutcome:
    """Return a typed lossless-refusal result without branching or attaching state."""
    findings = _find_non_finite_projection_values(projection)
    if findings:
        first_finding = findings[0]
        failure_basis = "canonical_json_rejected_non_finite_funnel_leaf"
        location = first_finding["location"]
        value_kind = first_finding["kind"]
        message = (
            "Funnel outcome could not be represented as finite state JSON at "
            f"{location} ({value_kind}); the original state was retained."
        )
    else:
        failure_basis = "canonical_json_rejected_funnel_projection"
        location = "$"
        value_kind = "serializer_or_json_value_not_supported"
        message = (
            "Funnel outcome could not be represented as finite state JSON; "
            "the original state was retained."
        )
    error = NodeError(
        code=node_errors.ERROR_INVALID_STATE,
        message=message,
        details={
            "projection": "funnel_outcome",
            "failure_basis": failure_basis,
            "location": location,
            "value_kind": value_kind,
            "non_finite_values": findings,
            "canonical_validation_error": str(exc),
            "funnel_failure_basis": _funnel_projection_failure_basis(session.outcome),
        },
    )
    return NodeOutcome(
        status="fail",
        state=session.state,
        artifacts=_runtime_session_artifact_refs(session),
        error=error,
    )


def finalize_runtime_session(session: _RuntimeSession) -> NodeOutcome:
    """Persist final evidence, branch state, and emit the node's existing events."""
    owner = session.owner
    ctx = session.ctx
    state = session.state
    outcome = session.outcome
    evidence_bundle = session.evidence_bundle
    predictive_voi = session.predictive_voi
    transfer_context = session.transfer_context
    assert evidence_bundle is not None
    assert session.selection_vector is not None
    assert session.selection_ref is not None
    assert session.evidence_ref is not None

    serialized_funnel_outcome: dict[str, Any] | None = None
    try:
        serialized_funnel_outcome = owner._serialize_funnel_outcome(outcome)
        if not isinstance(serialized_funnel_outcome, dict):
            raise CanonViolation("funnel outcome projection must be a JSON object")
        to_canonical_bytes(
            serialized_funnel_outcome,
            CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        )
    except (CanonViolation, TypeError, ValueError) as exc:
        return _funnel_projection_refusal(session, serialized_funnel_outcome, exc)

    final_evaluation_vector, final_evaluation_ref = owner._resolve_runtime_policy_evaluation(
        ctx,
        candidate_ref=session.candidate_ref,
        outcome=outcome,
        fallback=session.selection_vector,
    )
    stage4_feedback = dict(
        (outcome.stage_results.get(4).feedback or {})
        if outcome.stage_results.get(4) is not None
        else {}
    )
    evidence_bundle = evidence_bundle.model_copy(
        update={
            "evaluation_ref": final_evaluation_ref,
            "metadata": {
                **evidence_bundle.metadata,
                "voi_model_status": [
                    status.model_dump(mode="json") for status in predictive_voi.model_status()
                ],
                "voi_scope": {
                    "task_family": str(transfer_context.get("task_family") or "policy"),
                    "domain": str(transfer_context.get("domain") or ""),
                    "tenant_scope": str(transfer_context.get("tenant_hash") or ""),
                },
                "promotion_grade_fidelity": (
                    "full" if outcome.stage_results.get(4) is not None else "selection_only"
                ),
                "promotion_grade_backend_kind": str(
                    stage4_feedback.get("policy_runtime_backend_kind")
                    or session.selection_artifact.provenance.backend_kind
                ),
                "promotion_grade_promotable_source": bool(
                    stage4_feedback.get(
                        "policy_runtime_promotable_source",
                        session.selection_artifact.provenance.promotable_source,
                    )
                ),
                "promotion_grade_degradation_mode": (
                    str(stage4_feedback.get("policy_runtime_degradation_mode"))
                    if stage4_feedback.get("policy_runtime_degradation_mode") is not None
                    else session.selection_artifact.provenance.degradation_mode
                ),
            },
        }
    )
    evidence_ref = owner.persist_promotion_evidence_bundle(
        ctx.store,
        evidence_bundle,
        inputs=[
            InputRef(artifact_id=session.candidate_ref.artifact_id, role="candidate"),
            InputRef(artifact_id=session.selection_ref.artifact_id, role="selection_evaluation"),
            *(
                [InputRef(artifact_id=final_evaluation_ref.artifact_id, role="policy_evaluation")]
                if final_evaluation_ref is not None
                else []
            ),
        ],
    )
    voi_input_refs = [
        ref
        for ref in (session.candidate_ref, final_evaluation_ref, evidence_ref)
        if ref is not None
    ]
    voi_report = predictive_voi.report_for_decisions(
        run_id=state.run_id,
        decisions=(
            [outcome.last_scheduling_decision]
            if outcome.last_scheduling_decision is not None
            else []
        ),
        calibration_status=str(state.params.get("voi_calibration_status") or "shadow"),
        input_refs_by_candidate_id=(
            {outcome.candidate_hash: voi_input_refs}
            if outcome.last_scheduling_decision is not None
            else {}
        ),
        metadata={
            "source": "run_policy_blueprint_runtime",
            "final_action": outcome.final_action,
            "completed": outcome.completed,
            "trace_step_count": len(outcome.trace),
        },
    )
    voi_report_ref = owner.persist_voi_run_report(ctx.store, voi_report)

    new_state = owner.branch_state(
        state,
        write_paths=(
            "artifacts_index",
            "params.policy_candidate_ref",
            "params.policy_evaluation",
            "params.policy_evaluation_ref",
            "params.promotion_evidence_bundle_ref",
            "params.funnel_outcome",
            "params._funnel_outcome",
            "params.policy_level5_gate",
            "params.policy_runtime_source_statuses",
            "params.audit_refs",
            "params.actionable_side_information_refs",
            "params.voi_run_report_ref",
            "params.strategic_response",
            "params.strategic_response_source",
        ),
    ).state
    new_state.artifacts_index.update(session.runtime_artifacts_index)
    new_state.params["policy_candidate_ref"] = session.candidate_ref.model_dump(mode="json")
    new_state.params["policy_evaluation"] = final_evaluation_vector.model_dump(mode="json")
    if final_evaluation_ref is not None:
        new_state.params["policy_evaluation_ref"] = final_evaluation_ref.model_dump(mode="json")
    new_state.params["promotion_evidence_bundle_ref"] = evidence_ref.model_dump(mode="json")
    new_state.params["funnel_outcome"] = serialized_funnel_outcome
    new_state.params["_funnel_outcome"] = serialized_funnel_outcome
    new_state.params["policy_level5_gate"] = owner._extract_level5_gate(outcome)
    new_state.params["policy_runtime_source_statuses"] = dict(session.runtime_source_statuses)
    new_state.params["audit_refs"] = [ref.model_dump(mode="json") for ref in outcome.audit_refs]
    new_state.params["actionable_side_information_refs"] = [
        ref.model_dump(mode="json") for ref in outcome.actionable_side_information_refs
    ]
    new_state.params["voi_run_report_ref"] = voi_report_ref.model_dump(mode="json")
    if session.strategic_output.strategic_response_summary is not None:
        new_state.params["strategic_response"] = dict(
            session.strategic_output.strategic_response_summary
        )
        new_state.params.setdefault("strategic_response_source", "policy_runtime")
    new_state.artifacts_index[owner.ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF] = evidence_ref
    new_state.artifacts_index[owner.ARTIFACT_VOI_RUN_REPORT_REF] = voi_report_ref
    if session.platform_meta_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_PLATFORM_META_EVALUATION_REPORT_REF] = (
            session.platform_meta_ref
        )
    if session.stress_report_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_STRESS_TEST_REPORT_REF] = session.stress_report_ref
    if session.ambiguity_certificate_ref is not None:
        new_state.artifacts_index[owner.ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = (
            session.ambiguity_certificate_ref
        )

    promotion_feedback = dict(outcome.final_result.feedback or {}) if outcome.final_result else {}
    _project_promotion_feedback(new_state, promotion_feedback)
    session.evidence_bundle = evidence_bundle
    session.evidence_ref = evidence_ref
    session.final_evaluation_vector = final_evaluation_vector
    session.final_evaluation_ref = final_evaluation_ref
    session.voi_report_ref = voi_report_ref
    session.new_state = new_state
    return _build_runtime_outcome(session)


def _project_promotion_feedback(new_state: Any, promotion_feedback: dict[str, Any]) -> None:
    promotion_payload = promotion_feedback.get("promotion_result")
    if hasattr(promotion_payload, "model_dump"):
        new_state.params["policy_promotion_result"] = promotion_payload.model_dump(mode="json")
        new_state.params["judge_verdict"] = promotion_payload.judge_verdict.model_dump(mode="json")
        new_state.params["decision_readiness_contract"] = (
            promotion_payload.readiness_contract.model_dump(mode="json")
        )
        new_state.params["promotion_decision"] = promotion_payload.promotion_decision.model_dump(
            mode="json"
        )
        if promotion_payload.readiness_ref is not None:
            new_state.artifacts_index[ARTIFACT_DECISION_READINESS_CONTRACT_REF] = (
                promotion_payload.readiness_ref
            )
    elif isinstance(promotion_payload, Mapping):
        new_state.params["policy_promotion_result"] = dict(promotion_payload)
        if isinstance(promotion_payload.get("judge_verdict"), Mapping):
            new_state.params["judge_verdict"] = dict(promotion_payload["judge_verdict"])
        if isinstance(promotion_payload.get("readiness_contract"), Mapping):
            new_state.params["decision_readiness_contract"] = dict(
                promotion_payload["readiness_contract"]
            )
        if isinstance(promotion_payload.get("promotion_decision"), Mapping):
            new_state.params["promotion_decision"] = dict(promotion_payload["promotion_decision"])
    elif isinstance(promotion_feedback, dict):
        if "judge_verdict" in promotion_feedback:
            new_state.params["judge_verdict"] = promotion_feedback["judge_verdict"]
        if "decision_readiness_contract" in promotion_feedback:
            new_state.params["decision_readiness_contract"] = promotion_feedback[
                "decision_readiness_contract"
            ]
        if "promotion_reason" in promotion_feedback:
            new_state.params["promotion_decision"] = {
                "promoted": False,
                "reason": promotion_feedback["promotion_reason"],
            }


def _build_runtime_outcome(session: _RuntimeSession) -> NodeOutcome:
    owner = session.owner
    outcome = session.outcome
    artifacts = [session.selection_ref, session.evidence_ref]
    artifacts.extend(
        ref
        for ref in (
            session.ambiguity_certificate_ref,
            session.strategic_output.strategic_scm_ref,
            session.strategic_output.strategic_response_bundle_ref,
            session.platform_meta_ref,
            session.stress_report_ref,
        )
        if ref is not None
    )
    artifacts.append(session.voi_report_ref)
    events = [
        NodeEvent(
            level="info",
            message="Blueprint-native policy runtime executed through L0-L6.",
            attrs={
                "final_action": outcome.final_action,
                "completed": outcome.completed,
                "has_hidden_holdout": session.hidden_holdout_ref is not None,
            },
        )
    ]
    if session.cross_graph_profile is None and session.runtime_source_statuses:
        events.append(
            NodeEvent(
                level="info",
                message=(
                    "Policy runtime inferred evidence source availability from config "
                    "because no cross-graph profile artifact was available."
                ),
                attrs={"evidence_source_statuses": dict(session.runtime_source_statuses)},
            )
        )
    if session.phase_d4_warnings:
        events.append(
            NodeEvent(
                level="warn",
                message="Phase D.4 challenge suites emitted warnings.",
                attrs={"warnings": list(session.phase_d4_warnings)},
            )
        )
    if session.strategic_output.warnings:
        events.append(
            NodeEvent(
                level="warn",
                message="Strategic runtime artifact flow emitted warnings.",
                attrs={"warnings": list(session.strategic_output.warnings)},
            )
        )
    return NodeOutcome(status="ok", state=session.new_state, artifacts=artifacts, events=events)
