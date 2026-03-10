from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.distributional import DistributionalReportRef
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics, SimulationResult
from polisyos.core.contracts.scientist import DecisionPacketRef
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.ir.analytics.abm_bridge import load_abm_alignment_report
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.distributional import load_distributional_report
from polisyos.ir.analytics.hte import load_hte_result, load_policy_recommendation
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.refs import ABMAlignmentReportRef, CausalModelEnsembleRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_DECISION_CARD_REF,
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORM_IMPACT_REPORT_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.4.0"),
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
        "inputs",
        "reports_index",
        "artifacts_index",
    ],
    state_writes=[f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}"],
    produces=[ARTIFACT_DECISION_PACKET_REF],
)


class ReplayReadiness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INCOMPLETE = "incomplete"


_REQUIRED_INPUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        INPUT_TRINITY_BUNDLE_REF,
        INPUT_REGISTRY_BUNDLE_REF,
    }
)

_OPTIONAL_INPUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        INPUT_INPUT_BINDINGS_REF,
        INPUT_NORM_PACK_REF,
        INPUT_KNOWLEDGE_BUNDLE_REF,
        INPUT_RESEARCH_INTENT_REF,
        ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    }
)


@dataclass(frozen=True)
class BuildDecisionPacketNode:
    """Build a DecisionPacket from the engine state."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        seed = int(state.params.get("random_seed", 0) or 0)
        inputs_section = _build_inputs_section(state.inputs, state.artifacts_index)
        artifacts_section = _build_artifacts_section(state.artifacts_index, state.reports_index)
        readiness = _compute_replay_readiness(inputs_section)
        strategy_hint = _determine_strategy_hint(inputs_section, artifacts_section)
        policy_summary, intervention_count = _build_policy_summary(ctx, state.inputs)
        backtest_section = _build_backtest_section(ctx, state.artifacts_index)
        replay_section = _build_replay_section(
            inputs_section=inputs_section,
            artifacts_section=artifacts_section,
            readiness=readiness,
            strategy_hint=strategy_hint,
            seed=seed,
            determinism_tier=state.params.get("determinism_tier"),
        )

        packet_payload: dict[str, object] = {
            "schema_version": "3.2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": state.run_id,
            "seed": seed,
            "policy_summary": policy_summary,
            "intervention_count": intervention_count,
            "run_record": {
                "schema_version": "3.2",
                "run_id": state.run_id,
                "seed": seed,
                "engine": "scientist.engine",
            },
            "simulation_results": None,
            "governance": None,
            "uncertainty": _build_uncertainty_section(ctx, state.inputs, state.artifacts_index),
            "uncertainty_bounds": None,
            "causal": _build_causal_section(ctx, state.artifacts_index),
            "abm_alignment": _build_abm_alignment_section(ctx, state.artifacts_index),
            "hte": _build_hte_section(ctx, state.artifacts_index),
            "targeting": _build_targeting_section(ctx, state.artifacts_index),
            "backtest": backtest_section,
            "distributional": _build_distributional_section(ctx, state.artifacts_index),
            "econometrics": _build_econometrics_section(ctx, state.artifacts_index),
            "norm_impact": _build_aux_artifact_section(
                ctx, state.artifacts_index, ARTIFACT_NORM_IMPACT_REPORT_REF
            ),
            "sensitivity": _build_aux_artifact_section(
                ctx, state.artifacts_index, ARTIFACT_SENSITIVITY_RESULT_REF
            ),
            "stress_test": _build_aux_artifact_section(
                ctx, state.artifacts_index, ARTIFACT_STRESS_TEST_REPORT_REF
            ),
            "inputs": inputs_section,
            "artifacts": artifacts_section,
            "replay": replay_section,
            "notes": [],
        }
        if isinstance(backtest_section, dict):
            packet_payload["trust_profile"] = {
                "backtest_trust_score": backtest_section.get("trust_score"),
                "backtest_trust_grade": backtest_section.get("trust_grade"),
            }

        metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
        if metrics_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
                metrics = Metrics.model_validate(payload)
                packet_payload["simulation_results"] = dict(metrics.values)
            except Exception:
                packet_payload["simulation_results"] = None

        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(governance_ref.artifact_id))
                report = GovernanceReport.model_validate(payload)
                packet_payload["governance"] = {
                    "verdict": report.verdict,
                    "issues": report.issues,
                    "links": report.links.model_dump(mode="json"),
                    "notes": report.notes,
                }
            except Exception:
                packet_payload["governance"] = None

        uncertainty_bounds = _build_uncertainty_bounds(
            ctx,
            (
                packet_payload["uncertainty"]
                if isinstance(packet_payload["uncertainty"], dict)
                else {}
            ),
        )
        packet_payload["uncertainty_bounds"] = uncertainty_bounds
        packet_payload["diagnostics_summary"] = _build_diagnostics_summary(
            ctx=ctx,
            packet_payload=packet_payload,
            state=state,
        )
        packet_payload["analysis_limits"] = _build_analysis_limits(packet_payload)

        inputs = _build_manifest_inputs(packet_payload)

        packet_ref_payload = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version="3.2",
                ),
                inputs=inputs or None,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        packet_ref = DecisionPacketRef(artifact_id=packet_ref_payload.artifact_id)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref

        return NodeOutcome(status="ok", state=new_state, artifacts=[packet_ref])


def _build_inputs_section(
    state_inputs: dict[str, ArtifactRef],
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        INPUT_TRINITY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_TRINITY_BUNDLE_REF),
        INPUT_DATA_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_DATA_SNAPSHOT_REF),
        INPUT_STATE_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_STATE_SNAPSHOT_REF),
        INPUT_INPUT_BINDINGS_REF: _ref_from_dict(state_inputs, INPUT_INPUT_BINDINGS_REF),
        INPUT_REGISTRY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_REGISTRY_BUNDLE_REF),
        INPUT_NORM_PACK_REF: _ref_from_dict(state_inputs, INPUT_NORM_PACK_REF),
        INPUT_KNOWLEDGE_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_KNOWLEDGE_BUNDLE_REF),
        INPUT_RESEARCH_INTENT_REF: _ref_from_dict(state_inputs, INPUT_RESEARCH_INTENT_REF),
        ARTIFACT_ENVIRONMENT_MANIFEST_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ENVIRONMENT_MANIFEST_REF
        ),
    }


def _build_artifacts_section(
    artifacts_index: dict[str, ArtifactRef],
    reports_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        ARTIFACT_EXEC_PLAN_REF: _ref_from_dict(artifacts_index, ARTIFACT_EXEC_PLAN_REF),
        ARTIFACT_PROGRAM_GRAPH_REF: _ref_from_dict(artifacts_index, ARTIFACT_PROGRAM_GRAPH_REF),
        ARTIFACT_SIMULATION_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SIMULATION_RESULT_REF
        ),
        ARTIFACT_STATE_SNAPSHOT_REF: _ref_from_dict(artifacts_index, ARTIFACT_STATE_SNAPSHOT_REF),
        ARTIFACT_METRICS_REF: _ref_from_dict(artifacts_index, ARTIFACT_METRICS_REF),
        ARTIFACT_INPUT_BINDING_REPORT_REF: _ref_from_dict(
            artifacts_index,
            ARTIFACT_INPUT_BINDING_REPORT_REF,
        ),
        REPORT_GOVERNANCE_REPORT_REF: _ref_from_dict(reports_index, REPORT_GOVERNANCE_REPORT_REF),
        REPORT_COMPILE_REPORT_REF: _ref_from_dict(reports_index, REPORT_COMPILE_REPORT_REF),
        REPORT_LINK_REPORT_REF: _ref_from_dict(reports_index, REPORT_LINK_REPORT_REF),
        REPORT_LEGAL_REPORT_REF: _ref_from_dict(reports_index, REPORT_LEGAL_REPORT_REF),
        REPORT_CHANGE_PROPOSAL_REF: _ref_from_dict(reports_index, REPORT_CHANGE_PROPOSAL_REF),
        ARTIFACT_CAUSAL_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_REPORT_REF),
        ARTIFACT_CAUSAL_ENVELOPE_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_ENVELOPE_REF),
        ARTIFACT_CAUSAL_ENSEMBLE_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_ENSEMBLE_REF),
        ARTIFACT_ABM_ALIGNMENT_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ABM_ALIGNMENT_REPORT_REF
        ),
        ARTIFACT_HTE_RESULT_REF: _ref_from_dict(artifacts_index, ARTIFACT_HTE_RESULT_REF),
        ARTIFACT_POLICY_RECOMMENDATION_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_POLICY_RECOMMENDATION_REF
        ),
        ARTIFACT_BACKTEST_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_BACKTEST_REPORT_REF),
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DISTRIBUTIONAL_REPORT_REF
        ),
        ARTIFACT_ECONOMETRIC_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_RESULT_REF
        ),
        ARTIFACT_ECONOMETRIC_EVIDENCE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_EVIDENCE_REF
        ),
        ARTIFACT_ECONOMETRIC_ENVELOPE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_ENVELOPE_REF
        ),
        ARTIFACT_DECISION_CARD_REF: _ref_from_dict(artifacts_index, ARTIFACT_DECISION_CARD_REF),
        ARTIFACT_NORM_IMPACT_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_NORM_IMPACT_REPORT_REF
        ),
        ARTIFACT_SENSITIVITY_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SENSITIVITY_RESULT_REF
        ),
        ARTIFACT_STRESS_TEST_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_STRESS_TEST_REPORT_REF
        ),
    }


def _ref_from_dict(index: dict[str, ArtifactRef], key: str) -> str | None:
    ref = index.get(key)
    return str(ref.artifact_id) if ref is not None else None


def _build_policy_summary(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
) -> tuple[str, int]:
    trinity_ref = state_inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return "N/A", 0

    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
    except Exception:
        return "Policy data unavailable", 0

    if not isinstance(payload, dict):
        return "Policy data attached", 0

    policy_spec = payload.get("policy_spec")
    if not isinstance(policy_spec, dict):
        return "Policy data attached", 0

    interventions = policy_spec.get("interventions")
    if isinstance(interventions, list):
        return f"Policy with {len(interventions)} intervention(s)", len(interventions)

    return "Policy data attached", 0


def _build_causal_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    envelope_ref = artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    ensemble_ref = artifacts_index.get(ARTIFACT_CAUSAL_ENSEMBLE_REF)
    if report_ref is None and envelope_ref is None and ensemble_ref is None:
        return None

    payload: dict[str, object] = {
        "report_ref": str(report_ref.artifact_id) if report_ref is not None else None,
        "envelope_ref": str(envelope_ref.artifact_id) if envelope_ref is not None else None,
        "ensemble_ref": str(ensemble_ref.artifact_id) if ensemble_ref is not None else None,
        "ensemble_member_count": None,
        "ensemble_methods": [],
        "ensemble_consensus_graph_ref": None,
    }

    if ensemble_ref is not None:
        try:
            ensemble = load_causal_model_ensemble(
                ctx.store,
                CausalModelEnsembleRef(artifact_id=ensemble_ref.artifact_id),
            )
            payload["ensemble_member_count"] = len(ensemble.members)
            payload["ensemble_methods"] = sorted({member.discovery_method for member in ensemble.members})
            payload["ensemble_consensus_graph_ref"] = ensemble.consensus_graph_ref
        except Exception:
            payload["ensemble_parse_warning"] = "causal_ensemble_parse_failed"

    if report_ref is not None:
        try:
            report_obj = from_canonical_bytes(ctx.store.get_bytes(report_ref.artifact_id))
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
                    "transportability_summary": _build_transportability_summary(report),
                }
            )
        except Exception:
            payload["parse_warning"] = "causal_report_parse_failed"

    return payload


def _build_transportability_summary(report: CausalEffectReport) -> dict[str, object] | None:
    transport = report.transport_result
    if transport is None:
        return None
    gap_vars = [gap.required_variable for gap in transport.data_gaps]
    return {
        "status": transport.status.value,
        "final_confidence": transport.final_confidence,
        "feasible": transport.feasible,
        "algorithm_version": transport.algorithm_version,
        "identification_engine": transport.identification_engine,
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


def _build_abm_alignment_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_ABM_ALIGNMENT_REPORT_REF)
    if report_ref is None:
        return None

    payload: dict[str, object] = {"report_ref": str(report_ref.artifact_id)}
    try:
        report = load_abm_alignment_report(
            ctx.store,
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
    except Exception:
        payload["parse_warning"] = "abm_alignment_report_parse_failed"

    return payload


def _build_hte_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, object] | None:
    hte_ref = artifacts_index.get(ARTIFACT_HTE_RESULT_REF)
    if hte_ref is None:
        return None
    from polisyos.core.contracts.hte import HTEResultRef

    payload: dict[str, object] = {"result_ref": str(hte_ref.artifact_id)}
    try:
        result = load_hte_result(
            ctx.store,
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
                    for item in sorted(
                        result.feature_importances, key=lambda x: x.importance_rank
                    )[:5]
                ],
                "warnings": result.metadata.get("warnings", []),
            }
        )
    except Exception:
        payload["parse_warning"] = "hte_result_parse_failed"
    return payload


def _build_targeting_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, object] | None:
    recommendation_ref = artifacts_index.get(ARTIFACT_POLICY_RECOMMENDATION_REF)
    if recommendation_ref is None:
        return None
    from polisyos.core.contracts.hte import PolicyRecommendationRef

    payload: dict[str, object] = {"recommendation_ref": str(recommendation_ref.artifact_id)}
    try:
        recommendation = load_policy_recommendation(
            ctx.store,
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
    except Exception:
        payload["parse_warning"] = "policy_recommendation_parse_failed"
    return payload


def _build_backtest_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, object] | None:
    backtest_ref = artifacts_index.get(ARTIFACT_BACKTEST_REPORT_REF)
    if backtest_ref is None:
        return None
    from polisyos.core.contracts.backtest import BacktestReportRef

    payload: dict[str, object] = {"report_ref": str(backtest_ref.artifact_id)}
    try:
        report = load_backtest_report(
            ctx.store,
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
                "trust_score": report.trust_score,
                "trust_grade": report.trust_grade,
            }
        )
    except Exception:
        payload["parse_warning"] = "backtest_report_parse_failed"
    return payload


def _build_distributional_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    if report_ref is None:
        return None

    payload: dict[str, object] = {
        "report_ref": str(report_ref.artifact_id),
    }
    try:
        report = load_distributional_report(
            ctx.store,
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
    except Exception:
        payload["parse_warning"] = "distributional_report_parse_failed"

    return payload


def _build_econometrics_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
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
            result_obj = from_canonical_bytes(ctx.store.get_bytes(result_ref.artifact_id))
            if isinstance(result_obj, dict):
                payload["result"] = result_obj.get("result", result_obj)
                if "envelope" in result_obj:
                    payload["envelope"] = result_obj["envelope"]
            else:
                payload["result_type"] = type(result_obj).__name__
        except Exception:
            payload["result_parse_warning"] = "econometric_result_parse_failed"

    if envelope_ref is not None:
        try:
            envelope = load_uncertainty_envelope(
                ctx.store,
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
        except Exception:
            payload["envelope_parse_warning"] = "econometric_envelope_parse_failed"

    return payload


def _build_aux_artifact_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    key: str,
) -> dict[str, object] | None:
    ref = artifacts_index.get(key)
    if ref is None:
        return None
    payload: dict[str, object] = {"ref": str(ref.artifact_id)}
    try:
        artifact_obj = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        if isinstance(artifact_obj, dict):
            payload["content"] = artifact_obj
        else:
            payload["content_type"] = type(artifact_obj).__name__
    except Exception:
        payload["parse_warning"] = "artifact_parse_failed"
    return payload


def _compute_replay_readiness(inputs_section: dict[str, str | None]) -> ReplayReadiness:
    missing_required = [key for key in _REQUIRED_INPUT_KEYS if inputs_section.get(key) is None]
    has_snapshot = bool(
        inputs_section.get(INPUT_INPUT_BINDINGS_REF)
        or inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
    )
    if missing_required or not has_snapshot:
        return ReplayReadiness.INCOMPLETE
    missing_optional = [key for key in _OPTIONAL_INPUT_KEYS if inputs_section.get(key) is None]
    if missing_optional:
        return ReplayReadiness.PARTIAL
    return ReplayReadiness.COMPLETE


def _build_replay_section(
    *,
    inputs_section: dict[str, str | None],
    artifacts_section: dict[str, str | None],
    readiness: ReplayReadiness,
    strategy_hint: str,
    seed: int,
    determinism_tier: Any,
) -> dict[str, object]:
    missing_refs, why_partial, suggested_next_step = _describe_replay_gaps(inputs_section)
    return {
        "readiness": readiness.value,
        "strategy_hint": strategy_hint,
        "effective_seed": seed,
        "seed_source": "params.random_seed",
        "determinism_tier": determinism_tier if isinstance(determinism_tier, str) else None,
        "missing_refs": missing_refs,
        "why_partial": why_partial,
        "suggested_next_step": suggested_next_step,
        "fallback_from_decision_packet": False,
        "has_exec_plan_ref": artifacts_section.get(ARTIFACT_EXEC_PLAN_REF) is not None,
    }


def _describe_replay_gaps(
    inputs_section: dict[str, str | None],
) -> tuple[list[str], list[str], str | None]:
    missing_required = sorted(
        key for key in _REQUIRED_INPUT_KEYS if inputs_section.get(key) is None
    )
    missing_optional = sorted(
        key for key in _OPTIONAL_INPUT_KEYS if inputs_section.get(key) is None
    )
    has_snapshot = bool(
        inputs_section.get(INPUT_INPUT_BINDINGS_REF)
        or inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
    )
    missing_refs = list(missing_required)
    why_partial: list[str] = []
    if not has_snapshot:
        missing_refs.append("state_source_ref")
        why_partial.append("missing_state_source")
    if missing_required:
        why_partial.append("missing_required_inputs")
    if missing_optional:
        why_partial.append("missing_optional_inputs")

    if INPUT_INPUT_BINDINGS_REF in missing_optional:
        suggested = "Persist input_bindings_ref for replay-grade completeness."
    elif not has_snapshot:
        suggested = "Attach data_snapshot_ref, state_snapshot_ref, or input_bindings_ref."
    elif INPUT_NORM_PACK_REF in missing_optional:
        suggested = "Persist norm_pack_ref to make legal context replayable."
    elif missing_optional:
        suggested = "Persist the missing optional replay references listed in replay.missing_refs."
    elif missing_required:
        suggested = "Persist the missing required replay references listed in replay.missing_refs."
    else:
        suggested = None

    missing_refs.extend(missing_optional)
    return missing_refs, why_partial, suggested


def _determine_strategy_hint(
    inputs_section: dict[str, str | None],
    artifacts_section: dict[str, str | None],
) -> str:
    has_registry = inputs_section.get(INPUT_REGISTRY_BUNDLE_REF) is not None
    has_snapshot = bool(
        inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_INPUT_BINDINGS_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
        or artifacts_section.get(ARTIFACT_STATE_SNAPSHOT_REF)
    )
    has_exec_plan = artifacts_section.get(ARTIFACT_EXEC_PLAN_REF) is not None
    has_trinity = inputs_section.get(INPUT_TRINITY_BUNDLE_REF) is not None
    if has_exec_plan and has_registry and has_snapshot:
        return "foundry"
    if has_trinity and has_registry and has_snapshot:
        return "scientist"
    return "none"


def _build_diagnostics_summary(
    *,
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
    state: ExperimentState,
) -> dict[str, object]:
    governance = packet_payload.get("governance")
    governance_dict = governance if isinstance(governance, dict) else {}
    issues = governance_dict.get("issues")
    issue_summary = _summarize_governance_issues(issues if isinstance(issues, list) else [])

    causal = packet_payload.get("causal")
    causal_dict = causal if isinstance(causal, dict) else {}
    transport_summary = causal_dict.get("transportability_summary")
    transport_dict = transport_summary if isinstance(transport_summary, dict) else {}

    replay = packet_payload.get("replay")
    replay_dict = replay if isinstance(replay, dict) else {}

    uncertainty = packet_payload.get("uncertainty")
    uncertainty_dict = uncertainty if isinstance(uncertainty, dict) else {}
    uncertainty_bounds = packet_payload.get("uncertainty_bounds")

    governance_links = governance_dict.get("links")
    legal_ref = None
    if isinstance(governance_links, dict):
        legal_ref = governance_links.get("legal_report_ref")
        if isinstance(legal_ref, dict):
            legal_ref = legal_ref.get("artifact_id")
    if not isinstance(legal_ref, str):
        artifacts = packet_payload.get("artifacts")
        artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
        fallback_legal_ref = artifacts_dict.get(REPORT_LEGAL_REPORT_REF)
        legal_ref = fallback_legal_ref if isinstance(fallback_legal_ref, str) else None

    has_legal_report = legal_ref is not None
    has_distributional_report = bool(packet_payload.get("distributional"))
    has_causal_report = bool(causal_dict)
    uncertainty_available = bool(uncertainty_dict.get("envelope_count")) or isinstance(
        uncertainty_bounds, dict
    )
    contract_warnings = _collect_contract_warnings(ctx, state)
    requires_expert_review = bool(transport_dict.get("requires_expert_review")) or bool(
        state.params.get("needs_expert_review")
    )
    human_review_needed = bool(state.params.get("require_human_gate")) or _has_governance_issue_code(
        issues if isinstance(issues, list) else [],
        code="HUMAN_REVIEW_REQUESTED",
    ) or requires_expert_review

    return {
        "governance_verdict": governance_dict.get("verdict"),
        "blocker_count": issue_summary["blocker_count"],
        "warning_count": issue_summary["warning_count"],
        "info_count": issue_summary["info_count"],
        "transport_status": transport_dict.get("status", "not_run"),
        "transport_engine": transport_dict.get("identification_engine", "not_available"),
        "requires_expert_review": requires_expert_review,
        "replay_readiness": replay_dict.get("readiness"),
        "replay_missing_inputs": list(replay_dict.get("missing_refs", []))
        if isinstance(replay_dict.get("missing_refs"), list)
        else [],
        "has_legal_report": has_legal_report,
        "legal_executed": has_legal_report,
        "has_distributional_report": has_distributional_report,
        "has_causal_report": has_causal_report,
        "uncertainty_available": uncertainty_available,
        "human_review_needed": human_review_needed,
        "determinism_tier": replay_dict.get("determinism_tier"),
        "seed_source": replay_dict.get("seed_source"),
        "contract_warnings": contract_warnings,
    }


def _build_analysis_limits(packet_payload: dict[str, object]) -> dict[str, object]:
    diagnostics = packet_payload.get("diagnostics_summary")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    labels: list[str] = []
    contract_warnings = diagnostics_dict.get("contract_warnings")
    normalized_contract_warnings = (
        [str(item) for item in contract_warnings if isinstance(item, str)]
        if isinstance(contract_warnings, list)
        else []
    )

    transport_engine = diagnostics_dict.get("transport_engine")
    if isinstance(transport_engine, str) and transport_engine.startswith("simplified"):
        labels.append("transportability_simplified_engine")
    if diagnostics_dict.get("legal_executed") is False:
        labels.append("legal_not_run")
    if diagnostics_dict.get("requires_expert_review") is True:
        labels.append("expert_review_required")

    replay_readiness = diagnostics_dict.get("replay_readiness")
    if replay_readiness == ReplayReadiness.PARTIAL.value:
        labels.append("partial_replay_readiness")
    elif replay_readiness == ReplayReadiness.INCOMPLETE.value:
        labels.append("incomplete_replay_readiness")

    if diagnostics_dict.get("uncertainty_available") is False:
        labels.append("missing_uncertainty_artifact")
    if packet_payload.get("causal") is None:
        labels.append("causal_not_run")
    if packet_payload.get("distributional") is None:
        labels.append("distributional_not_run")
    if packet_payload.get("abm_alignment") is None:
        labels.append("abm_alignment_not_run")
    if "deprecated_mechanism_bindings" in normalized_contract_warnings:
        labels.append("deprecated_mechanism_bindings")
    if "model_fidelity_level_ignored" in normalized_contract_warnings:
        labels.append("model_fidelity_level_ignored")
    if any(
        warning.startswith("missing_runtime_mechanism_support:")
        for warning in normalized_contract_warnings
    ):
        labels.append("missing_runtime_mechanism_support")

    return {
        "labels": labels,
        "transportability_simplified_engine": "transportability_simplified_engine" in labels,
        "legal_not_run": "legal_not_run" in labels,
        "expert_review_required": "expert_review_required" in labels,
        "partial_replay_readiness": "partial_replay_readiness" in labels,
        "incomplete_replay_readiness": "incomplete_replay_readiness" in labels,
        "missing_uncertainty_artifact": "missing_uncertainty_artifact" in labels,
        "deprecated_mechanism_bindings": "deprecated_mechanism_bindings" in labels,
        "model_fidelity_level_ignored": "model_fidelity_level_ignored" in labels,
        "missing_runtime_mechanism_support": "missing_runtime_mechanism_support" in labels,
    }


def _summarize_governance_issues(issues: list[dict[str, object]]) -> dict[str, int]:
    blocker_count = 0
    warning_count = 0
    info_count = 0
    for issue in issues:
        severity = str(issue.get("severity", "")).strip().lower()
        if severity == "blocker":
            blocker_count += 1
        elif severity == "warning":
            warning_count += 1
        elif severity == "info":
            info_count += 1
    return {
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "info_count": info_count,
    }


def _has_governance_issue_code(issues: list[dict[str, object]], *, code: str) -> bool:
    for issue in issues:
        if str(issue.get("code", "")).strip() == code:
            return True
    return False


def _collect_contract_warnings(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> list[str]:
    warnings: list[str] = []
    link_report_ref = state.reports_index.get(REPORT_LINK_REPORT_REF)
    if link_report_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(link_report_ref.artifact_id))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            for issue in payload.get("issues", []):
                if not isinstance(issue, dict):
                    continue
                if str(issue.get("severity", "")).strip().lower() != "warning":
                    continue
                code = issue.get("code")
                if isinstance(code, str):
                    _append_unique(warnings, code)

    compile_report_ref = state.reports_index.get(REPORT_COMPILE_REPORT_REF)
    if compile_report_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(compile_report_ref.artifact_id))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            for note in payload.get("notes", []):
                if not isinstance(note, str):
                    continue
                normalized = _normalize_compile_warning(note)
                if normalized is not None:
                    _append_unique(warnings, normalized)

    return warnings


def _normalize_compile_warning(note: str) -> str | None:
    if note.startswith("link_warning:"):
        return note.split(":", 1)[1]
    if note.startswith("missing_runtime_mechanism_support:"):
        return note
    return None


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _build_manifest_inputs(packet_payload: dict[str, object]) -> list[InputRef]:
    collected: dict[tuple[str, str], InputRef] = {}
    for section_name, prefix in (
        ("inputs", "input"),
        ("artifacts", "artifact"),
        ("uncertainty", "uncertainty"),
        ("hte", "hte"),
        ("targeting", "targeting"),
        ("abm_alignment", "abm_alignment"),
        ("backtest", "backtest"),
        ("distributional", "distributional"),
        ("econometrics", "econometrics"),
        ("norm_impact", "norm_impact"),
        ("sensitivity", "sensitivity"),
        ("stress_test", "stress_test"),
    ):
        section = packet_payload.get(section_name)
        _collect_manifest_refs(section, prefix, collected)
    return list(collected.values())


def _collect_manifest_refs(
    value: object,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
) -> None:
    if isinstance(value, str):
        try:
            artifact_id = ArtifactID.model_validate(value)
        except Exception:
            return
        collected[(artifact_id.hex, role_prefix)] = InputRef(
            artifact_id=artifact_id,
            role=role_prefix,
        )
        return

    if isinstance(value, list):
        for idx, nested in enumerate(value):
            _collect_manifest_refs(nested, f"{role_prefix}[{idx}]", collected)
        return

    if isinstance(value, dict):
        for key, nested in value.items():
            _collect_manifest_refs(nested, f"{role_prefix}.{key}", collected)


def _build_uncertainty_section(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
    state_artifacts: dict[str, ArtifactRef],
) -> dict[str, object]:
    envelope_refs: set[str] = set()
    legacy_bounds_refs: set[str] = set()
    output_envelope_refs: dict[str, str] = {}
    warnings: list[str] = []

    data_snapshot_ref = state_inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref.artifact_id))
            snapshot = DataSnapshot.model_validate(payload)
            if snapshot.uncertainty_envelope_ref is not None:
                envelope_refs.add(str(snapshot.uncertainty_envelope_ref.artifact_id))
            if snapshot.uncertainty_ref is not None:
                legacy_bounds_refs.add(str(snapshot.uncertainty_ref.artifact_id))
        except Exception:
            warnings.append("data_snapshot_uncertainty_parse_failed")

    simulation_result_ref = state_artifacts.get(ARTIFACT_SIMULATION_RESULT_REF)
    if simulation_result_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(simulation_result_ref.artifact_id))
            sim_result = SimulationResult.model_validate(payload)
            if sim_result.uncertainty_envelopes:
                for metric_id, ref in sim_result.uncertainty_envelopes.items():
                    ref_str = str(ref.artifact_id)
                    output_envelope_refs[str(metric_id)] = ref_str
                    envelope_refs.add(ref_str)
        except Exception:
            warnings.append("simulation_result_uncertainty_parse_failed")

    causal_env_ref = state_artifacts.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if causal_env_ref is not None:
        envelope_refs.add(str(causal_env_ref.artifact_id))
    econometric_env_ref = state_artifacts.get(ARTIFACT_ECONOMETRIC_ENVELOPE_REF)
    if econometric_env_ref is not None:
        envelope_refs.add(str(econometric_env_ref.artifact_id))

    return {
        "envelope_refs": sorted(envelope_refs),
        "legacy_bounds_refs": sorted(legacy_bounds_refs),
        "output_envelope_refs": output_envelope_refs,
        "causal_envelope_ref": str(causal_env_ref.artifact_id)
        if causal_env_ref is not None
        else None,
        "econometric_envelope_ref": str(econometric_env_ref.artifact_id)
        if econometric_env_ref is not None
        else None,
        "envelope_count": len(envelope_refs),
        "legacy_bounds_count": len(legacy_bounds_refs),
        "output_envelope_count": len(output_envelope_refs),
        "warnings": warnings,
    }


def _build_uncertainty_bounds(
    ctx: ExecutionContext,
    uncertainty_section: dict[str, object],
) -> dict[str, float] | None:
    output_refs = uncertainty_section.get("output_envelope_refs")
    if not isinstance(output_refs, dict):
        return None

    bounds: dict[str, float] = {}
    for metric_id, ref_str in output_refs.items():
        if not isinstance(metric_id, str) or not isinstance(ref_str, str):
            continue
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(ref_str))
            env = load_uncertainty_envelope(ctx.store, ref)
        except Exception:
            continue
        bounds[f"{metric_id}_lower"] = float(env.confidence_interval[0])
        bounds[f"{metric_id}_upper"] = float(env.confidence_interval[1])
        bounds[f"{metric_id}_point"] = float(env.point_estimate)
        if env.confidence_level is not None:
            bounds[f"{metric_id}_ci_level"] = float(env.confidence_level)

    causal_ref = uncertainty_section.get("causal_envelope_ref")
    if isinstance(causal_ref, str):
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(causal_ref))
            env = load_uncertainty_envelope(ctx.store, ref)
            bounds["causal_effect_lower"] = float(env.confidence_interval[0])
            bounds["causal_effect_upper"] = float(env.confidence_interval[1])
            bounds["causal_effect_point"] = float(env.point_estimate)
            if env.confidence_level is not None:
                bounds["causal_effect_ci_level"] = float(env.confidence_level)
        except Exception:
            pass

    econometric_ref = uncertainty_section.get("econometric_envelope_ref")
    if isinstance(econometric_ref, str):
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(econometric_ref))
            env = load_uncertainty_envelope(ctx.store, ref)
            bounds["econometric_effect_lower"] = float(env.confidence_interval[0])
            bounds["econometric_effect_upper"] = float(env.confidence_interval[1])
            bounds["econometric_effect_point"] = float(env.point_estimate)
            if env.confidence_level is not None:
                bounds["econometric_effect_ci_level"] = float(env.confidence_level)
        except Exception:
            pass

    return bounds or None
