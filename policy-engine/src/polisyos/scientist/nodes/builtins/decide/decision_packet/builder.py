"""Public decide build decision packet module API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import polisyos.scientist.nodes.builtins.errors as node_errors
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.contracts.scientist import (
    DecisionPacketRef,
    MetricValidationReportRef,
    SourceVerificationReportRef,
    ValidationReportRef,
    VerifiedPolicyReportRef,
)
from polisyos.ir.analytics.metric_validation_report import (
    load_metric_validation_report,
)
from polisyos.scientist.evidence.claims.validators import (
    is_fail_on_naked_claims_enabled,
    validate_naked_decision_claims,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.research_dag.projections import (
    is_research_dag_required_for_publication,
)
from polisyos.scientist.methods.research_dag.replay import legacy_research_dag_status
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    _ClaimLedgerAttachment,  # noqa: F401 - re-exported through legacy decision packet API
    _DecisionPacketBuildRequest,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    _build_replay_section,
    _compute_replay_readiness,
    _determine_strategy_hint,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIM_LEDGER_V2_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF,
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORM_IMPACT_REPORT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_REISSUE_PACKET_REF,
    ARTIFACT_RESEARCH_DAG_REF,
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    ARTIFACT_VOI_RUN_REPORT_REF,
    ARTIFACT_WITHDRAWAL_RECORD_REF,
    REPORT_GOVERNANCE_REPORT_REF,
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
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    enforce_phase5_publication,
    run_phase5_artifact_preflight,
)
from polisyos.scientist.validation.policy_verified import (
    load_source_verification_report,
    load_verified_policy_report,
)

logger = get_logger(__name__)

from polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment import (
    _attach_claim_ledger_to_packet,
    _attach_human_review_projection,
    _build_abm_alignment_section,
    _build_abstraction_section,
    _build_aux_artifact_section,
    _build_backtest_section,
    _build_calibration_validation_section,
    _build_causal_section,
    _build_continuous_governance_section,
    _build_data_basis,
    _build_diagnostics_summary,
    _build_distributional_section,
    _build_econometrics_section,
    _build_feedback_loop,
    _build_hte_section,
    _build_knowledge_basis,
    _build_metric_significance_projection,
    _build_metric_significance_summary,
    _build_metric_validation_comparison_rows,
    _build_normative_basis,
    _build_phase3_section,
    _build_policy_summary,
    _build_runtime_contracts_section,
    _build_sensitivity_section,
    _build_strategic_section,
    _build_targeting_section,
    _build_tradeoff_certificate_section,
    _build_transportability_basis,
    _build_uncertainty_bounds,
    _build_uncertainty_section,
    _build_voi_section,
    _build_watched_triggers,
    _build_web_evidence_section,
    _build_welfare_section,
    _load_normative_frame_payload,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.serialization import (
    _build_artifacts_section,
    _build_document_outline,
    _build_inputs_section,
    _build_manifest_inputs,
    _sensitivity_analysis_bundle_ref_from_packet,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _build_analysis_limits,
    _build_decision_validity_baseline,
    _build_decision_validity_envelope,
    _decision_packet_degraded,
    _missing_serious_decision_contracts,
    _phase5_validation_summary,
    _record_decision_packet_degraded,
    _should_run_phase5_publication_preflight,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.5.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Decision Packet",
    description="Create the DecisionPacket artifact from available reports and metrics.",
    tags=["builtin", "decide"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.random_seed",
        "params.determinism_tier",
        "execution_profile",
        "capability_manifest_ref",
        "inputs",
        "reports_index",
        "artifacts_index",
        "artifacts_index.normative_arbitration_result_ref",
        "artifacts_index.policy_output_bundle_ref",
        "artifacts_index.claims_ref",
        "artifacts_index.claim_ledger_v2_ref",
        "artifacts_index.research_dag_ref",
        "artifacts_index.voi_run_report_ref",
        "artifacts_index.continuous_governance_report_ref",
        "artifacts_index.reissue_packet_ref",
        "artifacts_index.withdrawal_record_ref",
        "artifacts_index.human_review_packet_ref",
        "artifacts_index.human_review_decision_ref",
        "artifacts_index.web_evidence_bundle_ref",
        "artifacts_index.source_verification_report_ref",
        "artifacts_index.verified_policy_report_ref",
        "artifacts_index.bounds_bundle_ref",
        "artifacts_index.decision_readiness_contract_ref",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}",
        f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
        f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}",
        f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
        f"artifacts_index.{ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF}",
    ],
    produces=[
        ARTIFACT_DECISION_PACKET_REF,
        ARTIFACT_CLAIMS_REF,
        ARTIFACT_CLAIM_LEDGER_V2_REF,
        ARTIFACT_VALIDATION_REPORT_REF,
        ARTIFACT_JUDGE_VERDICT_REF,
    ],
)


@dataclass(frozen=True)
class BuildDecisionPacketNode:
    """Build a DecisionPacket from the engine state."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        request = _build_decision_packet_request(ctx, state)
        replay_section = _build_replay_section(
            inputs_section=request.inputs_section,
            artifacts_section=request.artifacts_section,
            readiness=request.readiness,
            strategy_hint=request.strategy_hint,
            seed=request.seed,
            determinism_tier=state.params.get("determinism_tier"),
        )

        packet_payload: dict[str, object] = {
            "schema_version": "3.4",
            "generated_at": datetime.now(UTC).isoformat(),
            "run_id": state.run_id,
            "seed": request.seed,
            "policy_summary": request.policy_summary,
            "intervention_count": request.intervention_count,
            "run_record": {
                "schema_version": "3.2",
                "run_id": state.run_id,
                "seed": request.seed,
                "engine": "scientist.engine",
            },
            "simulation_results": None,
            "metric_validation_report_ref": None,
            "metric_significance": None,
            "metric_significance_summary": None,
            "metric_validation_family_adjustment": None,
            "metric_validation_comparisons": [],
            "governance": None,
            "legal_verification": None,
            "source_coverage": None,
            "policy_answer": None,
            "verified_findings": [],
            "hypotheses": [],
            "intervention_legal_basis_map": {},
            "uncertainty": None,
            "uncertainty_bounds": None,
            "causal": None,
            "abm_alignment": None,
            "abstraction_certificate": None,
            "strategic": None,
            "hte": None,
            "targeting": None,
            "backtest": None,
            "calibration_validation": None,
            "distributional": None,
            "welfare": None,
            "phase3": None,
            "econometrics": None,
            "norm_impact": None,
            "sensitivity": None,
            "causal_validity": None,
            "stress_test": None,
            "tradeoff_certificate": None,
            "runtime_contracts": _build_runtime_contracts_section(state),
            "inputs": request.inputs_section,
            "artifacts": request.artifacts_section,
            "replay": replay_section,
            "research_dag_ref": request.artifacts_section.get(ARTIFACT_RESEARCH_DAG_REF),
            "research_dag_status": legacy_research_dag_status(
                request.artifacts_section.get(ARTIFACT_RESEARCH_DAG_REF)
            ),
            "voi_report_ref": request.artifacts_section.get(ARTIFACT_VOI_RUN_REPORT_REF),
            "voi_report_status": (
                "available"
                if request.artifacts_section.get(ARTIFACT_VOI_RUN_REPORT_REF) is not None
                else "legacy_missing"
            ),
            "voi": None,
            "continuous_governance_report_ref": request.artifacts_section.get(
                ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF
            ),
            "reissue_packet_ref": request.artifacts_section.get(ARTIFACT_REISSUE_PACKET_REF),
            "withdrawal_record_ref": request.artifacts_section.get(ARTIFACT_WITHDRAWAL_RECORD_REF),
            "continuous_governance": None,
            "human_review": None,
            "human_review_validation": None,
            "web_evidence": None,
            "degraded_paths": [],
            "document_outline": [],
            "notes": [],
        }
        packet_payload["web_evidence"] = _build_web_evidence_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["voi"] = _build_voi_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["continuous_governance"] = _build_continuous_governance_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["uncertainty"] = _build_uncertainty_section(
            ctx,
            state.inputs,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["causal"] = _build_causal_section(
            ctx,
            state,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["abm_alignment"] = _build_abm_alignment_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["abstraction_certificate"] = _build_abstraction_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["strategic"] = _build_strategic_section(
            ctx,
            state,
            packet_payload=packet_payload,
        )
        packet_payload["hte"] = _build_hte_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["targeting"] = _build_targeting_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["backtest"] = _build_backtest_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["calibration_validation"] = _build_calibration_validation_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["distributional"] = _build_distributional_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["welfare"] = _build_welfare_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["phase3"] = _build_phase3_section(
            ctx,
            state,
            packet_payload=packet_payload,
        )
        packet_payload["econometrics"] = _build_econometrics_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["norm_impact"] = _build_aux_artifact_section(
            ctx,
            state.artifacts_index,
            ARTIFACT_NORM_IMPACT_REPORT_REF,
            packet_payload=packet_payload,
        )
        packet_payload["sensitivity"] = _build_sensitivity_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["causal_validity"] = _build_aux_artifact_section(
            ctx,
            state.artifacts_index,
            ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
            packet_payload=packet_payload,
        )
        packet_payload["stress_test"] = _build_aux_artifact_section(
            ctx,
            state.artifacts_index,
            ARTIFACT_STRESS_TEST_REPORT_REF,
            packet_payload=packet_payload,
        )
        packet_payload["tradeoff_certificate"] = _build_tradeoff_certificate_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        if isinstance(packet_payload["backtest"], dict):
            backtest_section = packet_payload["backtest"]
            if bool(backtest_section.get("trust_eligible", True)):
                packet_payload["trust_profile"] = {
                    "backtest_trust_score": backtest_section.get("trust_score"),
                    "backtest_trust_grade": backtest_section.get("trust_grade"),
                }
            else:
                packet_payload["trust_profile"] = {
                    "backtest_trust_score": None,
                    "backtest_trust_grade": None,
                }

        metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
        if metrics_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
                metrics = Metrics.model_validate(payload)
                packet_payload["simulation_results"] = dict(metrics.values)
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                packet_payload["simulation_results"] = None
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_metrics_artifact",
                        reason="metrics_load_failed",
                        exc=exc,
                        ref=metrics_ref,
                        artifact_key=ARTIFACT_METRICS_REF,
                    ),
                )

        metric_validation_ref = state.artifacts_index.get(ARTIFACT_METRIC_VALIDATION_REPORT_REF)
        if metric_validation_ref is not None:
            try:
                report = load_metric_validation_report(
                    ctx.store,
                    MetricValidationReportRef.model_validate(metric_validation_ref.model_dump()),
                )
                packet_payload["metric_validation_report_ref"] = str(
                    metric_validation_ref.artifact_id
                )
                packet_payload["metric_significance"] = _build_metric_significance_projection(
                    report
                )
                packet_payload["metric_significance_summary"] = _build_metric_significance_summary(
                    report
                )
                packet_payload["metric_validation_family_adjustment"] = (
                    report.family_adjustment.model_dump(mode="json")
                )
                packet_payload["metric_validation_comparisons"] = (
                    _build_metric_validation_comparison_rows(report)
                )
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_metric_validation_report",
                        reason="metric_validation_report_load_failed",
                        exc=exc,
                        ref=metric_validation_ref,
                        artifact_key=ARTIFACT_METRIC_VALIDATION_REPORT_REF,
                    ),
                )

        governance_report: GovernanceReport | None = None
        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(governance_ref.artifact_id))
                report = GovernanceReport.model_validate(payload)
                governance_report = report
                packet_payload["governance"] = {
                    "verdict": report.verdict,
                    "issues": report.issues,
                    "links": report.links.model_dump(mode="json"),
                    "notes": report.notes,
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_governance_report",
                        reason="governance_report_load_failed",
                        exc=exc,
                        ref=governance_ref,
                        artifact_key=REPORT_GOVERNANCE_REPORT_REF,
                    ),
                )
                packet_payload["governance"] = None

        source_verification_ref = state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF)
        if source_verification_ref is not None:
            try:
                report = load_source_verification_report(
                    ctx.store,
                    SourceVerificationReportRef.model_validate(
                        source_verification_ref.model_dump()
                    ),
                )
                packet_payload["legal_verification"] = {
                    "verified_claim_count": len(report.verified_claims),
                    "citation_coverage_pct": report.verified_claim_citation_coverage_pct,
                    "needs_expert_review": report.needs_expert_review,
                    "verification_cycles_completed": report.verification_cycles_completed,
                }
                packet_payload["source_coverage"] = {
                    "unresolved_critical_gaps": [
                        gap.model_dump(mode="json") for gap in report.unresolved_critical_gaps
                    ],
                    "verifier_calls_total": report.verifier_calls_total,
                    "adjudicator_calls_total": report.adjudicator_calls_total,
                    "verifier_disagreement_rate": report.verifier_disagreement_rate,
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_source_verification_report",
                        reason="source_verification_report_load_failed",
                        exc=exc,
                        ref=source_verification_ref,
                        artifact_key=ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
                    ),
                )

        verified_policy_ref = state.artifacts_index.get(ARTIFACT_VERIFIED_POLICY_REPORT_REF)
        if verified_policy_ref is not None:
            try:
                verified_report = load_verified_policy_report(
                    ctx.store,
                    VerifiedPolicyReportRef.model_validate(verified_policy_ref.model_dump()),
                )
                packet_payload["policy_answer"] = {
                    "executive_summary": verified_report.executive_summary,
                    "missing_evidence": list(verified_report.missing_evidence),
                    "needs_expert_review": verified_report.needs_expert_review,
                }
                packet_payload["verified_findings"] = list(verified_report.verified_findings)
                packet_payload["hypotheses"] = list(verified_report.hypotheses)
                packet_payload["intervention_legal_basis_map"] = dict(
                    verified_report.intervention_legal_basis_map
                )
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_verified_policy_report",
                        reason="verified_policy_report_load_failed",
                        exc=exc,
                        ref=verified_policy_ref,
                        artifact_key=ARTIFACT_VERIFIED_POLICY_REPORT_REF,
                    ),
                )

        policy_bundle_ref = state.artifacts_index.get(ARTIFACT_POLICY_OUTPUT_BUNDLE_REF)
        if policy_bundle_ref is not None:
            try:
                from polisyos.scientist.policy_design.output import load_policy_artifact_bundle

                policy_bundle = load_policy_artifact_bundle(ctx.store, policy_bundle_ref)
                packet_payload["policy_output_bundle"] = {
                    "bundle_ref": policy_bundle_ref.artifact_id,
                    "policy_brief_ref": policy_bundle.policy_brief_ref.artifact_id,
                    "champion_policy_dossier_ref": (
                        policy_bundle.champion_policy_dossier_ref.artifact_id
                    ),
                    "decision_readiness_contract_ref": (
                        policy_bundle.decision_readiness_contract_ref.artifact_id
                        if policy_bundle.decision_readiness_contract_ref is not None
                        else None
                    ),
                    "phase3_gate": policy_bundle.phase3_gate.model_dump(mode="json"),
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_policy_output_bundle",
                        reason="policy_output_bundle_load_failed",
                        exc=exc,
                        ref=policy_bundle_ref,
                        artifact_key=ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
                    ),
                )

        uncertainty_bounds = _build_uncertainty_bounds(
            ctx,
            (
                packet_payload["uncertainty"]
                if isinstance(packet_payload["uncertainty"], dict)
                else {}
            ),
            packet_payload=packet_payload,
        )
        packet_payload["uncertainty_bounds"] = uncertainty_bounds
        packet_payload["diagnostics_summary"] = _build_diagnostics_summary(
            ctx=ctx,
            packet_payload=packet_payload,
            state=state,
        )
        packet_payload["analysis_limits"] = _build_analysis_limits(packet_payload)
        packet_payload["document_outline"] = _build_document_outline(packet_payload)
        validity_envelope = _build_decision_validity_envelope(
            ctx=ctx,
            state=state,
            packet_payload=packet_payload,
            build_normative_basis=_build_normative_basis,
            build_data_basis=_build_data_basis,
            build_knowledge_basis=_build_knowledge_basis,
            build_transportability_basis=_build_transportability_basis,
            build_watched_triggers=_build_watched_triggers,
            load_normative_frame_payload=_load_normative_frame_payload,
        )
        validity_baseline = _build_decision_validity_baseline(
            packet_payload=packet_payload,
            envelope=validity_envelope,
        )
        packet_payload["decision_validity_envelope"] = validity_envelope.model_dump(mode="json")
        packet_payload["decision_validity_baseline"] = validity_baseline.model_dump(mode="json")
        feedback_loop, monitoring_contract_ref = _build_feedback_loop(
            ctx=ctx,
            state=state,
            packet_payload=packet_payload,
            decision_lineage_key=validity_envelope.decision_lineage_key,
        )
        packet_payload["feedback_loop"] = feedback_loop
        missing_serious_contracts = _missing_serious_decision_contracts(
            state=state,
            monitoring_contract_ref=monitoring_contract_ref,
        )
        if missing_serious_contracts:
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        message=(
                            "Serious execution profiles require a complete decision contract; "
                            f"missing: {', '.join(missing_serious_contracts)}."
                        ),
                    )
                ],
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Incomplete serious decision contract",
                    details={
                        "execution_profile": state.execution_profile,
                        "missing_contracts": missing_serious_contracts,
                    },
                ),
            )

        claim_attachment = _attach_claim_ledger_to_packet(ctx, state, packet_payload)
        claims_ref = claim_attachment.claims_ref
        claim_ledger_v2_ref = claim_attachment.claim_ledger_v2_ref
        human_review_validation = _attach_human_review_projection(
            ctx,
            state,
            packet_payload,
            governance_report=governance_report,
        )
        claim_gate = validate_naked_decision_claims(
            packet_payload,
            claims_ref=claims_ref,
            workflow_id=str(state.params.get("workflow_id") or ""),
            fail_on_naked_claims=is_fail_on_naked_claims_enabled(state.params),
        )
        packet_payload["claim_ledger_validation"] = claim_gate.model_dump(mode="json")
        if not claim_gate.passed:
            new_state = branch_state(state, write_paths=claim_attachment.write_paths).state
            claim_attachment.apply_to_state(new_state)
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=claim_attachment.artifacts,
                events=[
                    NodeEvent(
                        level="error",
                        message="Claim spine validation blocked decision packet publication.",
                    )
                ],
                error=NodeError(
                    code="claim_spine_validation_failed",
                    message="Decision packet contains decision-bearing claims without claims_ref",
                    details=claim_gate.model_dump(mode="json"),
                ),
            )
        if not human_review_validation.passed:
            new_state = branch_state(state, write_paths=claim_attachment.write_paths).state
            claim_attachment.apply_to_state(new_state)
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=claim_attachment.artifacts,
                events=[
                    NodeEvent(
                        level="error",
                        message="Human review validation blocked decision packet publication.",
                    )
                ],
                error=NodeError(
                    code="human_review_validation_failed",
                    message="Decision packet human-review readiness requires review refs",
                    details=human_review_validation.model_dump(mode="json"),
                ),
            )
        if (
            is_research_dag_required_for_publication(state.params)
            and request.artifacts_section.get(ARTIFACT_RESEARCH_DAG_REF) is None
        ):
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        message="Research DAG sidecar is required for publication.",
                    )
                ],
                error=NodeError(
                    code="research_dag_missing_for_publication",
                    message="Decision packet publication requires research_dag_ref",
                    details={"research_dag_status": "legacy_missing"},
                ),
            )

        validation_ref: ValidationReportRef | None = None
        judge_verdict_ref: ArtifactRef | None = None
        if _should_run_phase5_publication_preflight(state):
            publication = run_phase5_artifact_preflight(
                ctx,
                state,
                Phase5ArtifactPreflightInput(
                    artifact_payload=packet_payload,
                    artifact_kind="scientist.decision_packet",
                    generated_for="scientist.decision_packet",
                    analyst_facing=True,
                    base_readiness="ready",
                ),
            )
            validation_report = publication.validation_report
            validation_ref = ValidationReportRef.model_validate(dict(publication.validation_ref))
            judge_verdict_ref = publication.judge_verdict_ref
            try:
                enforce_phase5_publication(publication)
            except Phase5ValidationBlocked:
                write_paths = [
                    f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                    f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
                ]
                if claim_ledger_v2_ref is not None:
                    write_paths.append(f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}")
                if judge_verdict_ref is not None:
                    write_paths.append(f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}")
                new_state = branch_state(
                    state,
                    write_paths=tuple(write_paths),
                ).state
                new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
                claim_attachment.apply_to_state(new_state)
                if judge_verdict_ref is not None:
                    new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = judge_verdict_ref
                return NodeOutcome(
                    status="fail",
                    state=new_state,
                    events=[
                        NodeEvent(
                            level="error",
                            message="Phase 5 validation blocked decision packet publication.",
                        )
                    ],
                    artifacts=[
                        artifact
                        for artifact in (
                            validation_ref,
                            judge_verdict_ref,
                            *claim_attachment.artifacts,
                        )
                        if artifact is not None
                    ],
                    error=NodeError(
                        code="phase5_validation_failed",
                        message="Phase 5 validation blocked analyst-facing publication",
                        details={
                            "validation_report_ref": str(validation_ref.artifact_id),
                            "verdict": validation_report.verdict,
                            "readiness": validation_report.readiness,
                            "gate_failures": list(validation_report.gate_failures),
                        },
                    ),
                )

            packet_payload["validation_report_ref"] = validation_ref.model_dump(mode="json")
            if judge_verdict_ref is not None:
                packet_payload["judge_verdict_ref"] = judge_verdict_ref.model_dump(mode="json")
            packet_payload["validation"] = _phase5_validation_summary(validation_report)
        inputs = _build_manifest_inputs(packet_payload)

        packet_ref_payload = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version="3.4",
                ),
                inputs=inputs or None,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        packet_ref = DecisionPacketRef(artifact_id=packet_ref_payload.artifact_id)
        sensitivity_bundle_ref = _sensitivity_analysis_bundle_ref_from_packet(packet_payload)
        DecisionValidityService(ctx.store).register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=validity_envelope,
            baseline=validity_baseline,
            monitoring_contract_ref=monitoring_contract_ref,
        )

        new_state = branch_state(
            state,
            write_paths=(
                f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}",
                f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
                f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}",
                f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                f"artifacts_index.{ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF}",
            ),
        ).state
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref
        claim_attachment.apply_to_state(new_state)
        if validation_ref is not None:
            new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
        if judge_verdict_ref is not None:
            new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = judge_verdict_ref
        if sensitivity_bundle_ref is not None:
            new_state.artifacts_index[ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF] = (
                sensitivity_bundle_ref
            )

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                artifact
                for artifact in (
                    packet_ref,
                    claims_ref,
                    claim_ledger_v2_ref,
                    validation_ref,
                    judge_verdict_ref,
                )
                if artifact is not None
            ],
        )


def _build_decision_packet_request(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> _DecisionPacketBuildRequest:
    seed = int(state.params.get("random_seed", 0) or 0)
    inputs_section = _build_inputs_section(state.inputs, state.artifacts_index)
    artifacts_section = _build_artifacts_section(
        state.artifacts_index,
        state.reports_index,
    )
    readiness = _compute_replay_readiness(inputs_section)
    strategy_hint = _determine_strategy_hint(inputs_section, artifacts_section)
    policy_summary, intervention_count = _build_policy_summary(ctx, state.inputs)
    return _DecisionPacketBuildRequest(
        seed=seed,
        inputs_section=inputs_section,
        artifacts_section=artifacts_section,
        readiness=readiness,
        strategy_hint=strategy_hint,
        policy_summary=policy_summary,
        intervention_count=intervention_count,
    )
