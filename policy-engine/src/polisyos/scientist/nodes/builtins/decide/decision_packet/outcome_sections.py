"""Decision-packet outcome projections."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import (
    DistributionalReportRef,
    SimulationResult,
    UncertaintyEnvelopeRef,
)
from polisyos.core.contracts.scientist import DecisionMonitoringContractRef
from polisyos.ir.analytics.abm_bridge import load_abm_alignment_report
from polisyos.ir.analytics.abstraction import load_abstraction_certificate
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.distributional import (
    load_distributional_effect_bundle,
    load_distributional_report,
    load_ordinal_poverty_report,
)
from polisyos.ir.analytics.hte import load_hte_result, load_policy_recommendation
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.analytics.welfare import load_channel_decomposition_artifact, load_welfare_bundle
from polisyos.ir.registry.refs import (
    ABMAlignmentReportRef,
    AbstractionCertificateRef,
    DistributionalEffectBundleRef,
    WelfareBundleRef,
)
from polisyos.scientist.feedback.core import (
    DecisionFeedbackService,
    build_monitoring_contract_from_packet,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.basis_sections import (
    _load_normative_arbitration,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _record_decision_packet_section_degraded,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import resolve_phase3_gate


def _build_abm_alignment_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_ABM_ALIGNMENT_REPORT_REF)
    if report_ref is None:
        return None

    payload: dict[str, object] = {"report_ref": str(report_ref.artifact_id)}
    try:
        report = load_abm_alignment_report(
            _ensure_ir_artifact_store(ctx.store),
            ABMAlignmentReportRef(artifact_id=report_ref.artifact_id),
        )
        status_counts: dict[str, int] = {}
        for result in report.alignment_results.values():
            key = result.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        payload.update(
            {
                "overall_consistent": report.overall_consistent,
                "n_mappings": len(report.mappings),
                "n_results": len(report.alignment_results),
                "status_counts": status_counts,
                "phase_transitions": [
                    item.model_dump(mode="json") for item in report.phase_transitions
                ],
                "warnings": list(report.warnings),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "abm_alignment_report_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_abm_alignment_report",
            reason="abm_alignment_report_load_failed",
            exc=exc,
            ref=report_ref,
            artifact_key=ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
        )

    return payload


def _build_abstraction_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    certificate_ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if certificate_ref is None:
        return None

    payload: dict[str, object] = {
        "certificate_ref": str(certificate_ref.artifact_id),
        "abstraction_map_ref": None,
    }
    map_ref = artifacts_index.get(ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF)
    if map_ref is not None:
        payload["abstraction_map_ref"] = str(map_ref.artifact_id)
    try:
        certificate = load_abstraction_certificate(
            _ensure_ir_artifact_store(ctx.store),
            AbstractionCertificateRef(artifact_id=certificate_ref.artifact_id),
        )
        payload.update(
            {
                "preservation_type": certificate.preservation_type.value,
                "preserved_queries": list(certificate.preserved_queries),
                "error_bound": certificate.error_bound,
                "validation_notes": list(certificate.validation_notes),
                "metadata": dict(certificate.metadata),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "abstraction_certificate_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_abstraction_certificate",
            reason="abstraction_certificate_load_failed",
            exc=exc,
            ref=certificate_ref,
            artifact_key=ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
        )
    return payload


def _build_hte_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    hte_ref = artifacts_index.get(ARTIFACT_HTE_RESULT_REF)
    if hte_ref is None:
        return None
    from polisyos.core.contracts import HTEResultRef

    payload: dict[str, object] = {"result_ref": str(hte_ref.artifact_id)}
    try:
        result = load_hte_result(
            _ensure_ir_artifact_store(ctx.store),
            HTEResultRef(artifact_id=hte_ref.artifact_id),
        )
        payload.update(
            {
                "method": result.method.value,
                "ate": result.ate,
                "ate_ci_lower": result.ate_ci_lower,
                "ate_ci_upper": result.ate_ci_upper,
                "n_samples": result.n_samples,
                "n_features": result.n_features,
                "n_subgroups": len(result.subgroup_effects),
                "top_features": [
                    item.model_dump(mode="json")
                    for item in sorted(result.feature_importances, key=lambda x: x.importance_rank)[
                        :5
                    ]
                ],
                "warnings": result.metadata.get("warnings", []),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "hte_result_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_hte_result",
            reason="hte_result_load_failed",
            exc=exc,
            ref=hte_ref,
            artifact_key=ARTIFACT_HTE_RESULT_REF,
        )
    return payload


def _build_targeting_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    recommendation_ref = artifacts_index.get(ARTIFACT_POLICY_RECOMMENDATION_REF)
    if recommendation_ref is None:
        return None
    from polisyos.core.contracts import PolicyRecommendationRef

    payload: dict[str, object] = {"recommendation_ref": str(recommendation_ref.artifact_id)}
    try:
        recommendation = load_policy_recommendation(
            _ensure_ir_artifact_store(ctx.store),
            PolicyRecommendationRef(artifact_id=recommendation_ref.artifact_id),
        )
        payload.update(
            {
                "budget_constraint": recommendation.budget_constraint,
                "optimization_objective": recommendation.optimization_objective,
                "n_targeted_units": recommendation.n_targeted_units,
                "n_total_units": recommendation.n_total_units,
                "total_expected_effect": recommendation.total_expected_effect,
                "total_cost": recommendation.total_cost,
                "targeting_efficiency": recommendation.targeting_efficiency,
                "rules": [
                    rule.model_dump(mode="json")
                    for rule in sorted(recommendation.targeting_rules, key=lambda r: r.priority)
                ],
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "policy_recommendation_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_policy_recommendation",
            reason="policy_recommendation_load_failed",
            exc=exc,
            ref=recommendation_ref,
            artifact_key=ARTIFACT_POLICY_RECOMMENDATION_REF,
        )
    return payload


def _build_backtest_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    backtest_ref = artifacts_index.get(ARTIFACT_BACKTEST_REPORT_REF)
    if backtest_ref is None:
        return None
    from polisyos.core.contracts import BacktestReportRef

    payload: dict[str, object] = {"report_ref": str(backtest_ref.artifact_id)}
    try:
        report = load_backtest_report(
            _ensure_ir_artifact_store(ctx.store),
            BacktestReportRef(artifact_id=backtest_ref.artifact_id),
        )
        payload.update(
            {
                "report_id": report.report_id,
                "n_scenarios": report.n_scenarios,
                "n_metrics_evaluated": report.n_metrics_evaluated,
                "overall_rmse": report.overall_rmse,
                "overall_mae": report.overall_mae,
                "overall_mape": report.overall_mape,
                "overall_coverage_probability": report.overall_coverage_probability,
                "overall_bias_direction": report.overall_bias_direction.value,
                "detected_biases": [
                    bias.model_dump(mode="json") for bias in report.detected_biases
                ],
                "prediction_mode_requested": report.prediction_mode_requested,
                "prediction_mode_effective": report.prediction_mode_effective,
                "degraded": report.degraded,
                "degraded_reasons": list(report.degraded_reasons),
                "trust_eligible": report.trust_eligible,
                "trust_score": report.trust_score,
                "trust_grade": report.trust_grade,
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "backtest_report_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_backtest_report",
            reason="backtest_report_load_failed",
            exc=exc,
            ref=backtest_ref,
            artifact_key=ARTIFACT_BACKTEST_REPORT_REF,
        )
    return payload


def _build_calibration_validation_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    bundle_ref = artifacts_index.get(ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF)
    if bundle_ref is None:
        return None
    payload: dict[str, object] = {"ref": str(bundle_ref.artifact_id)}
    try:
        from polisyos.scientist.governance.calibration_validation import (
            load_calibration_validation_bundle,
        )

        bundle = load_calibration_validation_bundle(ctx.store, bundle_ref)
        payload.update(
            {
                "status": bundle.status,
                "governance_verdict": bundle.governance_verdict,
                "summary": bundle.readout_summary(),
                "governance_accountability_ref": (
                    None
                    if bundle.governance_accountability_ref is None
                    else str(bundle.governance_accountability_ref.artifact_id)
                ),
                "governance_accountability_summary": dict(bundle.governance_accountability_summary),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "calibration_validation_bundle_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_calibration_validation_bundle",
            reason="calibration_validation_bundle_load_failed",
            exc=exc,
            ref=bundle_ref,
            artifact_key=ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
        )
    return payload


def _build_feedback_loop(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
    decision_lineage_key: str,
) -> tuple[dict[str, object], str | None]:
    generated_at = packet_payload.get("generated_at")
    anchor_at = str(state.params.get("deployment_at") or generated_at or "")
    monitoring_contract_ref: str | None = None
    feedback_service = DecisionFeedbackService(ctx.store)
    contract = build_monitoring_contract_from_packet(
        run_id=state.run_id,
        decision_lineage_key=decision_lineage_key,
        anchor_at=_parse_anchor_at(anchor_at),
        packet_payload=packet_payload,
        override=(
            state.params.get("monitoring_contract_override")
            if isinstance(state.params.get("monitoring_contract_override"), dict)
            else None
        ),
    )
    if contract is not None:
        input_refs: list[InputRef] = []
        for ref in (
            state.inputs.get(INPUT_DATA_SNAPSHOT_REF),
            state.artifacts_index.get(ARTIFACT_BACKTEST_REPORT_REF),
            state.artifacts_index.get(ARTIFACT_METRICS_REF),
        ):
            if ref is not None:
                input_refs.append(InputRef(artifact_id=ref.artifact_id, role="feedback_source"))
        monitoring_contract_ref = feedback_service.persist_monitoring_contract(
            contract,
            inputs=input_refs or None,
        )

    backtest_section = (
        packet_payload.get("backtest") if isinstance(packet_payload.get("backtest"), dict) else {}
    )
    contract_ref_payload = (
        DecisionMonitoringContractRef(artifact_id=monitoring_contract_ref).model_dump(mode="json")
        if monitoring_contract_ref is not None
        else None
    )
    return (
        {
            "anchor_at": anchor_at,
            "monitoring_contract_ref": contract_ref_payload,
            "latest_monitoring_report_ref": None,
            "latest_compare_report_ref": None,
            "latest_reissue_plan_ref": None,
            "backtest_mode_effective": backtest_section.get("prediction_mode_effective"),
            "backtest_trust_eligible": backtest_section.get("trust_eligible"),
        },
        monitoring_contract_ref,
    )


def _parse_anchor_at(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_distributional_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    bundle_ref = artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF)
    report_ref = artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    if report_ref is None and bundle_ref is None:
        return None

    payload: dict[str, object] = {
        "report_ref": str(report_ref.artifact_id) if report_ref is not None else None,
        "effect_bundle_ref": str(bundle_ref.artifact_id) if bundle_ref is not None else None,
    }
    if report_ref is not None:
        try:
            report = load_distributional_report(
                _ensure_ir_artifact_store(ctx.store),
                DistributionalReportRef(artifact_id=report_ref.artifact_id),
            )
            payload.update(
                {
                    "overall_gini_before": report.overall_gini_before,
                    "overall_gini_after": report.overall_gini_after,
                    "overall_gini_delta": report.overall_gini_delta,
                    "palma_ratio_before": report.palma_ratio_before,
                    "palma_ratio_after": report.palma_ratio_after,
                    "palma_ratio_delta": report.palma_ratio_delta,
                    "winners_count": len(report.winners_losers.winners),
                    "losers_count": len(report.winners_losers.losers),
                    "neutral_count": len(report.winners_losers.neutral),
                    "winners_share": report.winners_losers.total_winners_share,
                    "losers_share": report.winners_losers.total_losers_share,
                    "ordinal_poverty_summary": dict(report.ordinal_poverty_summary),
                    "breakdowns": [
                        {
                            "dimension": breakdown.dimension.value,
                            "dimension_label": breakdown.dimension_label,
                            "primary_metric": breakdown.primary_metric,
                            "primary_metric_unit": breakdown.primary_metric_unit.value,
                            "gini_before": breakdown.gini_before,
                            "gini_after": breakdown.gini_after,
                            "gini_delta": breakdown.gini_delta,
                            "cohorts": [
                                {
                                    "cohort_id": cohort.cohort_id,
                                    "cohort_label": cohort.cohort_label,
                                    "population_share": cohort.population_share,
                                    "delta": cohort.metric_deltas.get(breakdown.primary_metric),
                                    "impact_direction": cohort.impact_direction.value,
                                    "is_vulnerable": cohort.is_vulnerable,
                                }
                                for cohort in breakdown.cohorts
                            ],
                        }
                        for breakdown in report.breakdowns
                    ],
                }
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["parse_warning"] = "distributional_report_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_distributional_report",
                reason="distributional_report_load_failed",
                exc=exc,
                ref=report_ref,
                artifact_key=ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
            )

    if bundle_ref is not None:
        try:
            bundle = load_distributional_effect_bundle(
                _ensure_ir_artifact_store(ctx.store),
                DistributionalEffectBundleRef.model_validate(bundle_ref.model_dump()),
            )
            proof_kernel = bundle.metadata.get("proof_kernel")
            payload.update(
                {
                    "distributional_query_kind": bundle.distributional_query_kind,
                    "justification": bundle.justification.value,
                    "marginal_law_justification": (
                        bundle.marginal_law_justification.value
                        if bundle.marginal_law_justification is not None
                        else None
                    ),
                    "coupling_justification": (
                        bundle.coupling_justification.value
                        if bundle.coupling_justification is not None
                        else None
                    ),
                    "distributional_bounds_count": len(bundle.distributional_bounds_refs),
                    "causal_assumption_count": len(bundle.causal_assumption_refs),
                    "readiness_cap": bundle.readiness_cap,
                    "marginal_law_proof_ref": (
                        str(bundle.marginal_law_proof_ref.artifact_id)
                        if bundle.marginal_law_proof_ref is not None
                        else None
                    ),
                    "distributional_proof_ref": (
                        str(bundle.distributional_proof_ref.artifact_id)
                        if bundle.distributional_proof_ref is not None
                        else None
                    ),
                    "coupling_proof_ref": (
                        str(bundle.coupling_proof_ref.artifact_id)
                        if bundle.coupling_proof_ref is not None
                        else None
                    ),
                    "proof_kernel_status": (
                        str(proof_kernel.get("status"))
                        if isinstance(proof_kernel, dict) and proof_kernel.get("status") is not None
                        else None
                    ),
                    "proof_kernel_theorem_family": (
                        str(proof_kernel.get("theorem_family"))
                        if isinstance(proof_kernel, dict)
                        and proof_kernel.get("theorem_family") is not None
                        else None
                    ),
                    "ordinal_poverty_ref": (
                        str(bundle.ordinal_poverty_ref.artifact_id)
                        if bundle.ordinal_poverty_ref is not None
                        else None
                    ),
                }
            )
            if bundle.ordinal_poverty_ref is not None:
                try:
                    ordinal_report = load_ordinal_poverty_report(
                        _ensure_ir_artifact_store(ctx.store), bundle.ordinal_poverty_ref
                    )
                    payload.update(
                        {
                            "ordinal_poverty_methodology": ordinal_report.methodology,
                            "ordinal_poverty_deltas": dict(ordinal_report.deltas),
                        }
                    )
                except _DECISION_PACKET_LOAD_ERRORS as exc:
                    payload["ordinal_poverty_parse_warning"] = "ordinal_poverty_report_load_failed"
                    _record_decision_packet_section_degraded(
                        packet_payload,
                        operation="load_ordinal_poverty_report",
                        reason="ordinal_poverty_report_load_failed",
                        exc=exc,
                        ref=bundle.ordinal_poverty_ref,
                        artifact_key=ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
                    )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_distributional_effect_bundle",
                reason="distributional_effect_bundle_load_failed",
                exc=exc,
                ref=bundle_ref,
                artifact_key=ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
            )

    return payload


def _build_welfare_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    bundle_ref = artifacts_index.get(ARTIFACT_WELFARE_BUNDLE_REF)
    if bundle_ref is None:
        sim_result_ref = artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if sim_result_ref is not None:
            try:
                sim_result = SimulationResult.model_validate(
                    from_canonical_bytes(ctx.store.get_bytes(sim_result_ref))
                )
                if sim_result.welfare_bundle_ref is not None:
                    bundle_ref = sim_result.welfare_bundle_ref
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_section_degraded(
                    packet_payload,
                    operation="load_simulation_result_for_welfare",
                    reason="simulation_result_welfare_lookup_failed",
                    exc=exc,
                    ref=sim_result_ref,
                    artifact_key=ARTIFACT_SIMULATION_RESULT_REF,
                )
    if bundle_ref is None:
        return None

    payload: dict[str, object] = {
        "bundle_ref": str(bundle_ref.artifact_id),
    }
    try:
        welfare = load_welfare_bundle(
            _ensure_ir_artifact_store(ctx.store),
            WelfareBundleRef.model_validate(bundle_ref.model_dump()),
        )
        payload.update(
            {
                "welfare_measure": welfare.welfare_measure,
                "model_class": welfare.model_class,
                "ge_multiplier_semantics": welfare.ge_multiplier_semantics,
                "point_estimate": welfare.point_estimate,
                "credible_interval": (
                    None
                    if welfare.credible_interval is None
                    else [welfare.credible_interval[0], welfare.credible_interval[1]]
                ),
                "credible_width": (
                    None
                    if welfare.credible_interval is None
                    else welfare.credible_interval[1] - welfare.credible_interval[0]
                ),
                "robust_interval": (
                    None
                    if welfare.robust_interval is None
                    else [welfare.robust_interval[0], welfare.robust_interval[1]]
                ),
                "robust_width": (
                    None
                    if welfare.robust_interval is None
                    else welfare.robust_interval[1] - welfare.robust_interval[0]
                ),
                "interval_semantics": welfare.interval_semantics.value,
                "channel_decomposition_ref": (
                    str(welfare.channel_decomposition_ref.artifact_id)
                    if welfare.channel_decomposition_ref is not None
                    else None
                ),
                "channel_decomposition": dict(welfare.channel_decomposition),
                "subgroup_welfare": dict(welfare.subgroup_welfare),
                "equilibrium_multiplicity": welfare.equilibrium_multiplicity.model_dump(
                    mode="json"
                ),
                "method_used": welfare.method_used.value,
                "status": welfare.status.value,
                "warnings": list(welfare.warnings),
                "warning_count": len(welfare.warnings),
                "pe_uncertainty_count": len(welfare.pe_uncertainty_refs),
                "ge_uncertainty_ref": (
                    str(welfare.ge_uncertainty_ref.artifact_id)
                    if welfare.ge_uncertainty_ref is not None
                    else None
                ),
                "dependence_structure_ref": (
                    str(welfare.dependence_structure_ref.artifact_id)
                    if welfare.dependence_structure_ref is not None
                    else None
                ),
                "ge_model_ref": (
                    str(welfare.ge_model_ref.artifact_id)
                    if welfare.ge_model_ref is not None
                    else None
                ),
                "method_config_ref": (
                    str(welfare.method_config_ref.artifact_id)
                    if welfare.method_config_ref is not None
                    else None
                ),
                "sample_bundle_ref": (
                    str(welfare.sample_bundle_ref.artifact_id)
                    if welfare.sample_bundle_ref is not None
                    else None
                ),
                "sensitivity_diagnostics_ref": (
                    str(welfare.sensitivity_diagnostics_ref.artifact_id)
                    if welfare.sensitivity_diagnostics_ref is not None
                    else None
                ),
                "diagnostics": dict(welfare.diagnostics),
            }
        )
        if welfare.channel_decomposition_ref is not None:
            try:
                channel = load_channel_decomposition_artifact(
                    _ensure_ir_artifact_store(ctx.store),
                    welfare.channel_decomposition_ref,
                )
                payload["channel_decomposition_artifact"] = {
                    "target_kind": channel.target_kind.value,
                    "policy_class": channel.policy_class.value,
                    "basis_labels": list(channel.basis_labels),
                    "step_vector": list(channel.step_vector),
                    "mechanical_vector": (
                        None
                        if channel.mechanical_vector is None
                        else list(channel.mechanical_vector)
                    ),
                    "behavioral_vector": (
                        None
                        if channel.behavioral_vector is None
                        else list(channel.behavioral_vector)
                    ),
                    "fiscal_feedback_vector": (
                        None
                        if channel.fiscal_feedback_vector is None
                        else list(channel.fiscal_feedback_vector)
                    ),
                    "total_vector": (
                        None if channel.total_vector is None else list(channel.total_vector)
                    ),
                    "identification_status": channel.identification_status.value,
                    "blocking_reasons": list(channel.blocking_reasons),
                    "first_stage_stats": dict(channel.first_stage_stats),
                    "overid_stats": dict(channel.overid_stats),
                    "overlap_stats": dict(channel.overlap_stats),
                    "local_remainder_bound": channel.local_remainder_bound,
                    "diagnostic_summary": dict(channel.diagnostic_summary),
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                payload["channel_decomposition_parse_warning"] = "channel_decomposition_load_failed"
                _record_decision_packet_section_degraded(
                    packet_payload,
                    operation="load_channel_decomposition_artifact",
                    reason="channel_decomposition_load_failed",
                    exc=exc,
                    ref=welfare.channel_decomposition_ref,
                    artifact_key=ARTIFACT_WELFARE_BUNDLE_REF,
                )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "welfare_bundle_load_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_welfare_bundle",
            reason="welfare_bundle_load_failed",
            exc=exc,
            ref=bundle_ref,
            artifact_key=ARTIFACT_WELFARE_BUNDLE_REF,
        )
    return payload


def _build_phase3_section(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    gate = resolve_phase3_gate(ctx, state)
    payload: dict[str, object] = gate.model_dump(mode="json")
    payload["blocking_reason_count"] = len(gate.blocking_reasons)
    payload["refusal_status"] = "clear" if gate.gate_passed else "blocked"
    if packet_payload is not None:
        packet_payload["phase3_gate_passed"] = gate.gate_passed
    return payload


def _build_tradeoff_certificate_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    result = _load_normative_arbitration(ctx, artifacts_index, packet_payload=packet_payload)
    if result is None:
        return None
    return {
        "selected_policy": result.tradeoff_certificate.selected_policy.value,
        "selected_option": result.tradeoff_certificate.selected_option.value,
        "winners": list(result.tradeoff_certificate.winners),
        "losers": list(result.tradeoff_certificate.losers),
        "residual_dissent": [
            item.model_dump(mode="json") for item in result.tradeoff_certificate.residual_dissent
        ],
        "rights_violations": list(result.tradeoff_certificate.rights_violations),
        "hard_constraint_violations": list(result.tradeoff_certificate.hard_constraint_violations),
        "notes": list(result.tradeoff_certificate.notes),
    }


def _build_econometrics_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    result_ref = artifacts_index.get(ARTIFACT_ECONOMETRIC_RESULT_REF)
    evidence_ref = artifacts_index.get(ARTIFACT_ECONOMETRIC_EVIDENCE_REF)
    envelope_ref = artifacts_index.get(ARTIFACT_ECONOMETRIC_ENVELOPE_REF)
    if result_ref is None and evidence_ref is None and envelope_ref is None:
        return None

    payload: dict[str, object] = {
        "result_ref": str(result_ref.artifact_id) if result_ref is not None else None,
        "evidence_ref": str(evidence_ref.artifact_id) if evidence_ref is not None else None,
        "envelope_ref": str(envelope_ref.artifact_id) if envelope_ref is not None else None,
    }

    if result_ref is not None:
        try:
            result_obj = from_canonical_bytes(ctx.store.get_bytes(result_ref))
            if isinstance(result_obj, dict):
                payload["result"] = result_obj.get("result", result_obj)
                if "envelope" in result_obj:
                    payload["envelope"] = result_obj["envelope"]
            else:
                payload["result_type"] = type(result_obj).__name__
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["result_parse_warning"] = "econometric_result_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_econometric_result",
                reason="econometric_result_load_failed",
                exc=exc,
                ref=result_ref,
                artifact_key=ARTIFACT_ECONOMETRIC_RESULT_REF,
            )

    if envelope_ref is not None:
        try:
            envelope = load_uncertainty_envelope(
                _ensure_ir_artifact_store(ctx.store),
                UncertaintyEnvelopeRef(artifact_id=envelope_ref.artifact_id),
            )
            payload["envelope_summary"] = {
                "point_estimate": envelope.point_estimate,
                "confidence_interval": [
                    envelope.confidence_interval[0],
                    envelope.confidence_interval[1],
                ],
                "confidence_level": envelope.confidence_level,
            }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["envelope_parse_warning"] = "econometric_envelope_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_econometric_envelope",
                reason="econometric_envelope_load_failed",
                exc=exc,
                ref=envelope_ref,
                artifact_key=ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
            )

    return payload
