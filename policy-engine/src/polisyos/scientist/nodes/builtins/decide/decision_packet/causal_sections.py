"""Decision-packet causal projections."""

from __future__ import annotations

from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.evidence_bundle import load_causal_evidence_bundle
from polisyos.ir.analytics.kernel_causal import load_kernel_estimator_spec
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.registry.refs import (
    CausalModelEnsembleRef,
    EvidenceBundleRef,
    KernelEstimatorSpecRef,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _record_decision_packet_section_degraded,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

logger = get_logger(__name__)


def _build_causal_section(
    ctx: ExecutionContext,
    state: ExperimentState,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    envelope_ref = artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    ensemble_ref = artifacts_index.get(ARTIFACT_CAUSAL_ENSEMBLE_REF)
    evidence_ref = artifacts_index.get(ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF)
    validity_ref = artifacts_index.get(ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF)
    bounds_ref = artifacts_index.get(ARTIFACT_BOUNDS_BUNDLE_REF)
    readiness_ref = artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
    if (
        report_ref is None
        and envelope_ref is None
        and ensemble_ref is None
        and evidence_ref is None
        and validity_ref is None
        and bounds_ref is None
        and readiness_ref is None
    ):
        return None

    payload: dict[str, object] = {
        "report_ref": str(report_ref.artifact_id) if report_ref is not None else None,
        "envelope_ref": str(envelope_ref.artifact_id) if envelope_ref is not None else None,
        "ensemble_ref": str(ensemble_ref.artifact_id) if ensemble_ref is not None else None,
        "causal_method_evidence_ref": (
            str(evidence_ref.artifact_id) if evidence_ref is not None else None
        ),
        "causal_validity_ref": str(validity_ref.artifact_id) if validity_ref is not None else None,
        "bounds_ref": str(bounds_ref.artifact_id) if bounds_ref is not None else None,
        "decision_readiness_contract_ref": (
            str(readiness_ref.artifact_id) if readiness_ref is not None else None
        ),
        "proof_bundle_ref": None,
        "kernel_estimator_spec_ref": None,
        "kernel_summary": None,
        "ensemble_member_count": None,
        "ensemble_methods": [],
        "ensemble_consensus_graph_ref": None,
    }

    _populate_causal_ensemble(ctx, ensemble_ref, payload, packet_payload)

    _populate_causal_report(ctx, state, report_ref, payload, packet_payload)

    _populate_causal_evidence(ctx, evidence_ref, payload, packet_payload)

    _populate_causal_bounds(ctx, bounds_ref, payload, packet_payload)

    _populate_decision_readiness(ctx, readiness_ref, payload, packet_payload)

    return payload


def _populate_causal_ensemble(
    ctx: ExecutionContext,
    ensemble_ref: ArtifactRef | None,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if ensemble_ref is not None:
        try:
            ensemble = load_causal_model_ensemble(
                _ensure_ir_artifact_store(ctx.store),
                CausalModelEnsembleRef(artifact_id=ensemble_ref.artifact_id),
            )
            payload["ensemble_member_count"] = len(ensemble.members)
            payload["ensemble_methods"] = sorted(
                {member.discovery_method for member in ensemble.members}
            )
            payload["ensemble_consensus_graph_ref"] = ensemble.consensus_graph_ref
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            logger.debug(
                "Failed to parse causal model ensemble from ref %s",
                ensemble_ref,
                exc_info=True,
            )
            payload["ensemble_parse_warning"] = "causal_ensemble_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_causal_ensemble",
                reason="causal_ensemble_load_failed",
                exc=exc,
                ref=ensemble_ref,
                artifact_key=ARTIFACT_CAUSAL_ENSEMBLE_REF,
            )


def _populate_causal_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    report_ref: ArtifactRef | None,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if report_ref is not None:
        try:
            report_obj = from_canonical_bytes(ctx.store.get_bytes(report_ref))
            report = CausalEffectReport.model_validate(report_obj)
            refutation_results = [
                item.model_dump(mode="json") for item in report.refutation_results
            ]
            refutation_tests_total = len(report.refutation_results)
            refutation_tests_passed = sum(1 for item in report.refutation_results if item.passed)
            payload.update(
                {
                    "method": report.method.value,
                    "status": report.status.value,
                    "status_reason": report.status_reason,
                    "estimand": report.estimand,
                    "point_estimate": report.point_estimate,
                    "confidence_interval": report.confidence_interval,
                    "p_value": report.p_value,
                    "placebo_p_value": report.placebo_p_value,
                    "inference_method": report.inference_method,
                    "diagnostics": [diag.model_dump(mode="json") for diag in report.diagnostics],
                    "refutation_results": refutation_results,
                    "refutation_tests_total": refutation_tests_total,
                    "refutation_tests_passed": refutation_tests_passed,
                    "refutation_robust": (
                        refutation_tests_total > 0
                        and refutation_tests_passed == refutation_tests_total
                    ),
                    "transportability_summary": _build_transportability_summary(report, state),
                }
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["parse_warning"] = "causal_report_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_causal_report",
                reason="causal_report_load_failed",
                exc=exc,
                ref=report_ref,
                artifact_key=ARTIFACT_CAUSAL_REPORT_REF,
            )


def _populate_causal_evidence(
    ctx: ExecutionContext,
    evidence_ref: ArtifactRef | None,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if evidence_ref is not None:
        try:
            evidence_bundle = load_causal_evidence_bundle(
                _ensure_ir_artifact_store(ctx.store),
                EvidenceBundleRef.model_validate(evidence_ref.model_dump()),
            )
            payload["proof_bundle_ref"] = (
                str(evidence_bundle.proof_bundle_ref.artifact_id)
                if evidence_bundle.proof_bundle_ref is not None
                else None
            )
            payload["kernel_estimator_spec_ref"] = (
                str(evidence_bundle.kernel_estimator_spec_ref.artifact_id)
                if evidence_bundle.kernel_estimator_spec_ref is not None
                else None
            )
            if evidence_bundle.kernel_estimator_spec_ref is not None:
                kernel_spec = load_kernel_estimator_spec(
                    _ensure_ir_artifact_store(ctx.store),
                    KernelEstimatorSpecRef.model_validate(
                        evidence_bundle.kernel_estimator_spec_ref.model_dump(mode="json")
                    ),
                )
                payload["kernel_summary"] = {
                    "template": kernel_spec.template.value,
                    "target_representation": kernel_spec.target_representation.value,
                    "lowering_disposition": kernel_spec.lowering_disposition.value,
                    "consistency_claim": kernel_spec.consistency_claim.value,
                    "required_side_conditions": list(kernel_spec.required_side_conditions),
                    "blocking_reasons": list(kernel_spec.blocking_reasons),
                    "diagnostics_plan": list(kernel_spec.diagnostics_plan),
                    "output_kernel": kernel_spec.output_kernel.name,
                    "operator_ready": kernel_spec.target_representation.value == "effect_operator",
                    "non_promotable": kernel_spec.lowering_disposition.value != "ready",
                }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_causal_method_evidence_bundle",
                reason="causal_method_evidence_load_failed",
                exc=exc,
                ref=evidence_ref,
                artifact_key=ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
            )


def _populate_causal_bounds(
    ctx: ExecutionContext,
    bounds_ref: ArtifactRef | None,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if bounds_ref is not None:
        try:
            bounds_bundle = load_bounds_bundle(_ensure_ir_artifact_store(ctx.store), bounds_ref)
            payload["bounds_interval"] = (
                None
                if bounds_bundle.lower_bound is None or bounds_bundle.upper_bound is None
                else [bounds_bundle.lower_bound, bounds_bundle.upper_bound]
            )
            payload["bounds_warning_codes"] = list(bounds_bundle.warnings)
            payload["bounds_sharpness_status"] = bounds_bundle.sharpness_status
            dp_summary = _normalize_dp_summary(bounds_bundle.metadata)
            if dp_summary is not None:
                _merge_dp_summary_into_causal_payload(payload, dp_summary)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["bounds_parse_warning"] = "bounds_bundle_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_bounds_bundle",
                reason="bounds_bundle_load_failed",
                exc=exc,
                ref=bounds_ref,
                artifact_key=ARTIFACT_BOUNDS_BUNDLE_REF,
            )


def _populate_decision_readiness(
    ctx: ExecutionContext,
    readiness_ref: ArtifactRef | None,
    payload: dict[str, object],
    packet_payload: dict[str, object] | None,
) -> None:
    if readiness_ref is not None:
        try:
            from polisyos.scientist.methods.search.readiness import load_decision_readiness_contract

            readiness = load_decision_readiness_contract(ctx.store, readiness_ref)
            payload["decision_readiness_level"] = readiness.readiness_level.value
            payload["decision_readiness_cap"] = readiness.metadata.get("readiness_cap")
            if readiness.metadata.get("data_readiness_decision") is not None:
                payload["data_readiness_decision"] = readiness.metadata.get(
                    "data_readiness_decision"
                )
            dp_summary = _normalize_dp_summary(readiness.metadata)
            if dp_summary is not None:
                _merge_dp_summary_into_causal_payload(payload, dp_summary)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["decision_readiness_parse_warning"] = "decision_readiness_contract_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_decision_readiness_contract",
                reason="decision_readiness_contract_load_failed",
                exc=exc,
                ref=readiness_ref,
                artifact_key=ARTIFACT_DECISION_READINESS_CONTRACT_REF,
            )


def _normalize_dp_summary(payload: Any) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    candidate = payload.get("dp_robustness")
    if isinstance(candidate, dict):
        payload = candidate
    effective_status = payload.get("effective_status", payload.get("dp_effective_status"))
    if effective_status is None:
        return None
    summary: dict[str, object] = {"effective_status": str(effective_status)}
    reason = payload.get("reason")
    if reason is not None:
        summary["reason"] = reason
    block_reason = payload.get("block_reason", payload.get("dp_block_reason"))
    if block_reason is not None:
        summary["block_reason"] = block_reason
    distortion_radius = payload.get("distortion_radius", payload.get("dp_distortion_radius"))
    if distortion_radius is not None:
        summary["distortion_radius"] = distortion_radius
    mechanism_family = payload.get("mechanism_family", payload.get("dp_mechanism_family"))
    if mechanism_family is not None:
        summary["mechanism_family"] = mechanism_family
    effect_interval = payload.get("effect_interval", payload.get("dp_effect_interval"))
    if isinstance(effect_interval, (list, tuple)) and len(effect_interval) == 2:
        summary["effect_interval"] = [effect_interval[0], effect_interval[1]]
    return summary


def _merge_dp_summary_into_causal_payload(
    payload: dict[str, object],
    summary: dict[str, object],
) -> None:
    payload["dp_effective_status"] = summary["effective_status"]
    if summary.get("reason") is not None:
        payload["dp_reason"] = summary["reason"]
    if summary.get("block_reason") is not None:
        payload["dp_block_reason"] = summary["block_reason"]
    if summary.get("distortion_radius") is not None:
        payload["dp_distortion_radius"] = summary["distortion_radius"]
    if summary.get("mechanism_family") is not None:
        payload["dp_mechanism_family"] = summary["mechanism_family"]
    if summary.get("effect_interval") is not None:
        payload["dp_effect_interval"] = summary["effect_interval"]


def _build_transportability_summary(
    report: CausalEffectReport,
    state: ExperimentState,
) -> dict[str, object] | None:
    transport = report.transport_result
    if transport is None:
        return None
    gap_vars = [gap.required_variable for gap in transport.data_gaps]
    return {
        "status": transport.status.value,
        "transport_mode": transport.transport_mode.value,
        "final_confidence": transport.final_confidence,
        "feasible": transport.feasible,
        "algorithm_version": transport.algorithm_version,
        "identification_engine": transport.identification_engine,
        "capability_hash": state.params.get("transportability_capability_hash"),
        "degradation_policy": state.params.get("transportability_degradation_policy"),
        "unsupported_reason": transport.unsupported_reason,
        "identification_trace": list(transport.identification_trace),
        "pag_identification_policy": (
            transport.pag_identification_policy.value
            if transport.pag_identification_policy is not None
            else None
        ),
        "id_confidence_under_pag": transport.id_confidence_under_pag,
        "pag_dag_sample_size": transport.pag_dag_sample_size,
        "pag_transportable_count": transport.pag_transportable_count,
        "resolution_rounds": transport.resolution_rounds,
        "data_gaps_count": len(transport.data_gaps),
        "data_gap_variables": gap_vars,
        "unsupported_cases_count": len(transport.unsupported_cases),
        "unsupported_cases": list(transport.unsupported_cases),
        "hard_legal_constraints": list(transport.hard_legal_constraints),
        "requires_expert_review": transport.requires_expert_review,
        "expert_review_reasons": list(transport.expert_review_reasons),
        "warnings": list(transport.warnings),
    }
