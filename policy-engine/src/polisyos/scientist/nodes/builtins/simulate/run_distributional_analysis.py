"""Public simulate run distributional analysis module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import FoundryInputBindings, SimulationResult, StateSnapshotRef
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_geography_breakdown,
    build_income_quintile_breakdown,
)
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.density_ratio import (
    ScalarOTDistributionalResult,
    compute_scalar_distributional_effect,
)
from polisyos.foundry.methods.catalog.causal.distributional_bounds import (
    POINTWISE_NON_UNIFORM_WARNING,
    DistributionalBoundsEngineMethod,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.foundry.methods.catalog.distributional.poverty_advanced import (
    OrdinalMultidimensionalPovertyEstimator,
)
from polisyos.ir.analytics.causal import (
    ProofBundle,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
    proof_bundle_from_negative_certificate,
)
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    CohortDimension,
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionalBoundsBundle,
    DistributionalBoundUniformity,
    DistributionalCouplingStatus,
    DistributionalDualCertificate,
    DistributionalEffectBundle,
    DistributionalFunctional,
    DistributionalJustification,
    DistributionalProofArtifact,
    DistributionalProofTarget,
    DistributionBin,
    OrdinalPovertyEstimate,
    OrdinalPovertyReport,
    OTCouplingSummary,
    QuantileShiftEntry,
    QuantileShiftSummary,
    SubgroupDistributionComparison,
    TailRiskDeltaEntry,
    TailRiskDeltaSummary,
    attach_distributional_dual_certificate_ref,
    persist_causal_assumption_card,
    persist_discrete_distribution_summary,
    persist_distributional_bounds_bundle,
    persist_distributional_dual_certificate,
    persist_distributional_effect_bundle,
    persist_distributional_proof_artifact,
    persist_distributional_report,
    persist_ordinal_poverty_report,
    persist_ot_coupling_summary,
    persist_quantile_shift_summary,
    persist_subgroup_distribution_comparison,
    persist_tail_risk_delta_summary,
)
from polisyos.ir.analytics.estimand import DistributionLawQuery, EstimandAST, persist_estimand_ast
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
    persist_negative_certificate,
)
from polisyos.ir.refs import (
    CausalAssumptionCardRef,
    CausalGraphModelRef,
    DistributionalBoundsBundleRef,
    DistributionalDualCertificateRef,
    DistributionalProofArtifactRef,
    EstimandASTRef,
    NegativeCertificateRef,
    OrdinalPovertyReportRef,
    ProofBundleRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_STATE_SNAPSHOT_REF,
)

_BASE_CAUSAL_ASSUMPTIONS = [
    "distributional_estimand_not_proof_kernel_identified",
    "scenario_level_ot_coupling",
    "sinkhorn_regularized_discrete_measure_approximation",
]
_ASSUMPTION_DESCRIPTIONS = {
    "distributional_estimand_not_proof_kernel_identified": (
        "No proof-kernel identification result is attached for the counterfactual marginal law "
        "on this path, so the distributional claim must remain below identified/bounded status."
    ),
    "scenario_level_ot_coupling": (
        "The OT coupling is rendered as a scenario object unless a separate joint-law "
        "identification or set-identification argument is supplied."
    ),
    "sinkhorn_regularized_discrete_measure_approximation": (
        "The transport plan is a Sinkhorn-regularized discrete approximation used for "
        "numerical stability and visualization, not a proof of a structural joint law."
    ),
    "uniform_weighting_used": (
        "Distributional summaries use uniform unit weights rather than density-ratio reweighting."
    ),
    "positivity": "Positivity / overlap must hold on the support of the interventional query.",
    "overlap": "Source and target supports must overlap on the covariate region used by the query.",
    "sutva": "SUTVA must hold so each unit's potential outcome is well defined.",
    "consistency": "Consistency must link the observed outcome to the potential outcome under the realized treatment.",
    "no_interference": "No interference must hold unless the query explicitly models spillovers.",
    "time_stationarity": "Time-stationarity assumptions must hold for longitudinal identification formulas.",
    "selection": "Selection assumptions must justify the observed conditioning event used by the query.",
    "exclusion_restriction": "Exclusion restriction must hold for IV-style distributional identification claims.",
}
_TESTABLE_ASSUMPTIONS = {
    "positivity",
    "overlap",
    "time_stationarity",
    "selection",
    "uniform_weighting_used",
    "sinkhorn_regularized_discrete_measure_approximation",
}
_GEOGRAPHY_MIN_GROUP_SIZE = 10
_DISTRIBUTIONAL_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_distributional_analysis@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Distributional Analysis",
    description="Build DistributionalReport and DistributionalEffectBundle from simulation state snapshots.",
    tags=["builtin", "simulate", "distributional"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        f"inputs.{INPUT_STATE_SNAPSHOT_REF}",
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        "params.distributional_treatment_variable",
        "params.query_treatment",
        "params.treatment_variable",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF}",
    ],
    produces=[
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
        ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ],
)


@dataclass(frozen=True)
class _SubgroupSpec:
    dimension: CohortDimension
    subgroup_id: str
    subgroup_label: str
    mask: np.ndarray


@dataclass(frozen=True)
class _PersistedScalarArtifacts:
    baseline_distribution_ref: Any
    counterfactual_distribution_ref: Any
    coupling_ref: Any
    quantile_shift_ref: Any
    tail_risk_delta_ref: Any
    coupling_diagnostics: CouplingDiagnostics


@dataclass(frozen=True)
class _PersistedAssumptionCards:
    all_refs: list[CausalAssumptionCardRef]
    marginal_refs: list[CausalAssumptionCardRef]
    coupling_refs: list[CausalAssumptionCardRef]


@dataclass(frozen=True)
class _DistributionalJustificationResolution:
    marginal_justification: DistributionalJustification
    coupling_justification: DistributionalJustification | None
    causal_assumptions: list[str]
    coupling_assumptions: list[str]
    metadata: dict[str, Any]
    proof_bundle: ProofBundle | None = None
    coupling_negative_certificate: NegativeCertificate | None = None


@dataclass(frozen=True)
class _DistributionalBoundsResolution:
    refs: list[DistributionalBoundsBundleRef]
    assumptions: list[str]
    metadata: dict[str, Any]
    theorem_families: list[str]
    functionals: list[str]
    bound_uniformity: DistributionalBoundUniformity
    proof_target: DistributionalProofTarget


@dataclass(frozen=True)
class _OrdinalPovertyResolution:
    ref: OrdinalPovertyReportRef | None
    summary: dict[str, Any]
    events: tuple[NodeEvent, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RunDistributionalAnalysisNode:
    """Run distributional analysis node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        sim_result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if sim_result_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No simulation_result_ref; skip distributional analysis",
                    )
                ],
            )

        try:
            sim_payload = from_canonical_bytes(ctx.store.get_bytes(sim_result_ref.artifact_id))
            sim_result = SimulationResult.model_validate(sim_payload)
        except _DISTRIBUTIONAL_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message=f"Unable to load SimulationResult: {exc}")],
            )

        if sim_result.state_snapshot_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="SimulationResult has no state_snapshot_ref; skip distributional analysis",
                    )
                ],
            )

        baseline_ref = _resolve_baseline_snapshot_ref(ctx, state)
        if baseline_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No baseline snapshot available; skip distributional analysis",
                    )
                ],
            )

        try:
            baseline_state = load_state_snapshot(ctx.store, snapshot_ref=baseline_ref)
            simulated_state = load_state_snapshot(
                ctx.store, snapshot_ref=sim_result.state_snapshot_ref
            )
        except _DISTRIBUTIONAL_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message=f"Unable to load state snapshots: {exc}")],
            )

        incomes_before = np.asarray(baseline_state.agents.income, dtype=np.float64)
        incomes_after = np.asarray(simulated_state.agents.income, dtype=np.float64)
        if incomes_before.size < 10 or incomes_after.size < 10:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info", message="Insufficient agents for distributional analysis"
                    )
                ],
            )

        geography_groups, geography_skipped_reasons = _aligned_geography_subgroups(
            baseline_state=baseline_state,
            simulated_state=simulated_state,
        )
        breakdowns = [build_income_quintile_breakdown(incomes_before, incomes_after)]

        geography_breakdown = _build_aligned_geography_breakdown(
            baseline_state=baseline_state,
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            geography_groups=geography_groups,
        )
        if geography_breakdown is not None:
            breakdowns.append(geography_breakdown)

        artifact_inputs = _distributional_inputs(
            sim_result_ref=sim_result_ref,
            simulated_snapshot_ref=sim_result.state_snapshot_ref,
            baseline_snapshot_ref=baseline_ref,
        )
        ordinal_poverty = _maybe_build_ordinal_poverty_report(
            ctx,
            state,
            artifact_inputs=artifact_inputs,
            sim_result_ref=sim_result_ref,
            baseline_agent_count=int(incomes_before.size),
            counterfactual_agent_count=int(incomes_after.size),
        )
        report = build_distributional_report(
            breakdowns,
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            ordinal_poverty_summary=ordinal_poverty.summary,
            source_simulation_ref=str(sim_result_ref.artifact_id),
            metadata={
                "run_id": state.run_id,
                "geography_breakdown_status": "included"
                if geography_breakdown is not None
                else "skipped",
                "geography_breakdown_skipped_reasons": list(geography_skipped_reasons),
                "geography_group_ids": [group.subgroup_id for group in geography_groups],
                **ordinal_poverty.metadata,
            },
        )

        try:
            overall_result = compute_scalar_distributional_effect(
                incomes_before,
                incomes_after,
                n_bins=_recommended_n_bins(min(incomes_before.size, incomes_after.size)),
            )
            justification_resolution = _resolve_distributional_justification(
                ctx,
                state,
                outcome_name="income",
                weighting_mode=overall_result.weighting_mode,
            )
            bounds_resolution = _resolve_distributional_bounds(
                ctx,
                state,
                baseline_values=incomes_before,
                counterfactual_values=incomes_after,
                inputs=artifact_inputs,
            )
            if (
                bounds_resolution.refs
                and justification_resolution.marginal_justification
                is not DistributionalJustification.IDENTIFIED
            ):
                bounded_assumptions = [
                    assumption
                    for assumption in justification_resolution.causal_assumptions
                    if assumption != "distributional_estimand_not_proof_kernel_identified"
                ]
                justification_resolution = _DistributionalJustificationResolution(
                    marginal_justification=DistributionalJustification.BOUNDED,
                    coupling_justification=justification_resolution.coupling_justification,
                    causal_assumptions=_merge_assumptions(
                        bounded_assumptions,
                        bounds_resolution.assumptions,
                    ),
                    coupling_assumptions=justification_resolution.coupling_assumptions,
                    metadata={
                        **justification_resolution.metadata,
                        "marginal_law_justification": DistributionalJustification.BOUNDED.value,
                        "distributional_bounds": bounds_resolution.metadata,
                        "bounded_functionals": bounds_resolution.functionals,
                        "bounds_theorem_families": bounds_resolution.theorem_families,
                        "bound_uniformity": bounds_resolution.bound_uniformity.value,
                    },
                    proof_bundle=justification_resolution.proof_bundle,
                    coupling_negative_certificate=justification_resolution.coupling_negative_certificate,
                )
            marginal_assumptions = list(justification_resolution.causal_assumptions)
            causal_assumptions = _merge_assumptions(
                marginal_assumptions,
                justification_resolution.coupling_assumptions,
            )
            overall_refs = _persist_scalar_artifacts(
                ctx,
                outcome_name="income",
                baseline_values=incomes_before,
                counterfactual_values=incomes_after,
                result=overall_result,
                inputs=artifact_inputs,
                coupling_assumptions=justification_resolution.coupling_assumptions,
                metadata={"scope": "overall", "run_id": state.run_id},
            )
            subgroup_refs, subgroup_events = _persist_subgroup_artifacts(
                ctx,
                incomes_before=incomes_before,
                incomes_after=incomes_after,
                inputs=artifact_inputs,
                base_assumptions=marginal_assumptions,
                coupling_assumptions=justification_resolution.coupling_assumptions,
                geography_groups=geography_groups,
                geography_skip_reasons=geography_skipped_reasons,
            )
            assumption_cards = _persist_distributional_assumption_cards(
                ctx,
                inputs=artifact_inputs,
                marginal_assumptions=justification_resolution.causal_assumptions,
                coupling_assumptions=justification_resolution.coupling_assumptions,
                marginal_justification=justification_resolution.marginal_justification,
                default_theorem_family=_distributional_theorem_family(
                    proof_bundle=justification_resolution.proof_bundle,
                    metadata=justification_resolution.metadata,
                ),
            )
            distributional_proof_ref, coupling_proof_ref = _persist_distributional_proof_artifacts(
                ctx,
                inputs=artifact_inputs,
                proof_bundle=justification_resolution.proof_bundle,
                metadata=justification_resolution.metadata,
                marginal_justification=justification_resolution.marginal_justification,
                coupling_justification=justification_resolution.coupling_justification,
                marginal_assumption_refs=assumption_cards.marginal_refs,
                coupling_assumption_refs=assumption_cards.coupling_refs,
                coupling_negative_certificate=justification_resolution.coupling_negative_certificate,
                distributional_bounds_refs=bounds_resolution.refs,
                distributional_bounds_metadata=bounds_resolution.metadata,
                distributional_bounds_uniformity=bounds_resolution.bound_uniformity,
                distributional_bounds_target=bounds_resolution.proof_target,
            )
            bundle = DistributionalEffectBundle(
                outcome_name="income",
                distributional_query_kind="interventional_law",
                justification=justification_resolution.marginal_justification,
                marginal_justification=justification_resolution.marginal_justification,
                marginal_law_justification=justification_resolution.marginal_justification,
                coupling_justification=justification_resolution.coupling_justification,
                baseline_distribution_ref=overall_refs.baseline_distribution_ref,
                counterfactual_distribution_ref=overall_refs.counterfactual_distribution_ref,
                coupling_ref=overall_refs.coupling_ref,
                coupling_diagnostics=overall_refs.coupling_diagnostics,
                wasserstein_distance=float(overall_result.wasserstein_distance),
                quantile_shift_ref=overall_refs.quantile_shift_ref,
                tail_risk_delta_ref=overall_refs.tail_risk_delta_ref,
                ordinal_poverty_ref=ordinal_poverty.ref,
                subgroup_distribution_refs=subgroup_refs,
                marginal_law_proof_ref=distributional_proof_ref,
                distributional_proof_ref=distributional_proof_ref,
                coupling_proof_ref=coupling_proof_ref,
                distributional_bounds_refs=bounds_resolution.refs,
                causal_assumption_refs=assumption_cards.all_refs,
                causal_assumptions=causal_assumptions,
                readiness_cap="simulation_ready",
                metadata={
                    "run_id": state.run_id,
                    "source_simulation_ref": str(sim_result_ref.artifact_id),
                    "weighting_mode": overall_result.weighting_mode,
                    "distributional_query_kind": "interventional_law",
                    **ordinal_poverty.metadata,
                    **justification_resolution.metadata,
                },
            )
            bundle_ref = persist_distributional_effect_bundle(
                ctx.store, bundle, inputs=artifact_inputs
            )
            report_ref = persist_distributional_report(ctx.store, report, inputs=artifact_inputs)
        except _DISTRIBUTIONAL_EXECUTION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(level="error", message=f"Distributional D.1 build failed: {exc}")
                ],
                error=NodeError(
                    code="distributional_analysis_failed",
                    message="Failed to build OT distributional artifacts",
                    details={"reason": str(exc)},
                ),
            )

        new_state = branch_state(state, write_paths=("artifacts_index",)).state
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF] = report_ref
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF] = bundle_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                report_ref,
                bundle_ref,
                *([ordinal_poverty.ref] if ordinal_poverty.ref is not None else []),
            ],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Distributional report generated with {len(report.breakdowns)} breakdown(s) "
                        f"and OT bundle with {len(subgroup_refs)} subgroup comparison(s)"
                    ),
                ),
                *ordinal_poverty.events,
                *subgroup_events,
            ],
        )


def _distributional_inputs(
    *,
    sim_result_ref: Any,
    simulated_snapshot_ref: StateSnapshotRef,
    baseline_snapshot_ref: StateSnapshotRef,
) -> list[InputRef]:
    return [
        InputRef(artifact_id=sim_result_ref.artifact_id, role="simulation_result"),
        InputRef(artifact_id=simulated_snapshot_ref.artifact_id, role="simulated_state_snapshot"),
        InputRef(artifact_id=baseline_snapshot_ref.artifact_id, role="baseline_state_snapshot"),
    ]


def _coerce_optional_bool(raw_value: Any, *, name: str, default: bool) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    raise TypeError(f"{name} must be True/False when provided")


def _coerce_ordinal_category_matrix(
    raw_matrix: Any,
    *,
    name: str,
    expected_agents: int | None = None,
) -> np.ndarray:
    matrix = np.asarray(raw_matrix, dtype=object)
    if matrix.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if matrix.shape[0] == 0:
        raise ValueError(f"{name} must not be empty")
    if expected_agents is not None and matrix.shape[0] != expected_agents:
        raise ValueError(
            f"{name} row count must match agent count {expected_agents}, got {matrix.shape[0]}"
        )
    return matrix


def _coerce_ordinal_weights(raw_weights: Any, *, n_dimensions: int) -> np.ndarray:
    if raw_weights is None:
        return np.full(n_dimensions, 1.0 / n_dimensions, dtype=np.float64)
    weights = np.asarray(raw_weights, dtype=np.float64)
    if weights.ndim != 1:
        raise ValueError("ordinal_poverty weights must be a 1D vector")
    if weights.shape[0] != n_dimensions:
        raise ValueError("ordinal_poverty weights length must match the number of dimensions")
    if np.any(~np.isfinite(weights)):
        raise ValueError("ordinal_poverty weights must be finite")
    if np.any(weights < 0.0):
        raise ValueError("ordinal_poverty weights must be non-negative")
    if float(np.sum(weights)) <= 0.0:
        raise ValueError("ordinal_poverty weights must sum to a positive value")
    return weights


def _ordinal_estimate_summary(estimate: OrdinalPovertyEstimate) -> dict[str, Any]:
    cutoff_diagnostics = dict(estimate.cutoff_diagnostics)
    cutoff_excerpt = (
        {
            "current_cutoffs": cutoff_diagnostics.get("current_cutoffs", []),
            "local_slopes": cutoff_diagnostics.get("local_slopes", {}),
            "flip_shares": cutoff_diagnostics.get("flip_shares", {}),
            "preferred_cutoff_plateau": cutoff_diagnostics.get("preferred_cutoff_plateau", []),
            "recoding_invariance_bound": cutoff_diagnostics.get("recoding_invariance_bound", 0.0),
        }
        if cutoff_diagnostics
        else {}
    )
    return {
        "headcount_h": estimate.headcount_h,
        "ordinal_intensity_a": estimate.ordinal_intensity_a,
        "ordinal_adjusted_headcount_q": estimate.ordinal_adjusted_headcount_q,
        "af_m0_baseline": estimate.af_m0_baseline,
        "beta": estimate.beta,
        "k_threshold": estimate.k_threshold,
        "n_agents": estimate.n_agents,
        "n_dimensions": estimate.n_dimensions,
        "n_poor": estimate.n_poor,
        "dimension_names": list(estimate.dimension_names),
        "deprivation_cutoffs": list(estimate.deprivation_cutoffs),
        "dimension_weights": list(estimate.dimension_weights),
        "threshold_weights_basis": estimate.threshold_weights_basis,
        "dimension_contributions": dict(estimate.dimension_contributions),
        "cutoff_sensitivity": cutoff_excerpt,
        "legacy_gap_envelope": dict(estimate.legacy_gap_envelope),
    }


def _ordinal_poverty_summary_from_report(
    report: OrdinalPovertyReport,
    *,
    ref: OrdinalPovertyReportRef,
) -> dict[str, Any]:
    summary = {
        "status": "included" if report.counterfactual is not None else "baseline_only",
        "methodology": report.methodology,
        "ordinal_poverty_ref": str(ref.artifact_id),
        "baseline": _ordinal_estimate_summary(report.baseline),
        "deltas": dict(report.deltas),
    }
    if report.counterfactual is not None:
        summary["counterfactual"] = _ordinal_estimate_summary(report.counterfactual)
    return summary


def _run_ordinal_poverty_estimate(
    config: Mapping[str, Any],
    *,
    category_matrix: np.ndarray,
    label: str,
) -> OrdinalPovertyEstimate:
    n_dimensions = int(category_matrix.shape[1])
    weights = _coerce_ordinal_weights(
        config.get("dimension_weights", config.get("weights")),
        n_dimensions=n_dimensions,
    )
    params = {
        "category_orders": config.get("category_orders"),
        "deprivation_cutoffs": config.get("deprivation_cutoffs"),
        "k_threshold": config.get("poverty_cutoff_K", config.get("k_threshold", 0.33)),
        "beta": config.get("beta", 1.0),
        "threshold_weights": config.get("threshold_weights", "equal"),
        "dimension_names": config.get("dimension_names"),
        "return_censored_scores": _coerce_optional_bool(
            config.get("return_censored_scores"),
            name="ordinal_poverty.return_censored_scores",
            default=True,
        ),
        "return_dimension_contributions": _coerce_optional_bool(
            config.get("return_dimension_contributions"),
            name="ordinal_poverty.return_dimension_contributions",
            default=True,
        ),
        "return_cutoff_diagnostics": _coerce_optional_bool(
            config.get("return_cutoff_diagnostics"),
            name="ordinal_poverty.return_cutoff_diagnostics",
            default=True,
        ),
        "cutoff_grid": config.get("cutoff_grid"),
        "max_cutoff_grid_size": int(config.get("max_cutoff_grid_size", 256)),
        "comparator_recodings": config.get("comparator_recodings"),
    }
    payload = OrdinalMultidimensionalPovertyEstimator.pure_step(
        {
            "category_matrix": category_matrix,
            "weights": weights,
        },
        params,
    )
    estimate = OrdinalPovertyEstimate.model_validate(
        {
            **payload["result"],
            "metadata": {
                "population_label": label,
                **dict(payload["result"].get("metadata", {})),
            },
        }
    )
    return estimate


def _maybe_build_ordinal_poverty_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    artifact_inputs: list[InputRef],
    sim_result_ref: Any,
    baseline_agent_count: int,
    counterfactual_agent_count: int,
) -> _OrdinalPovertyResolution:
    raw_config = state.params.get("ordinal_poverty")
    if raw_config is None:
        return _OrdinalPovertyResolution(
            ref=None,
            summary={},
            events=(),
            metadata={"ordinal_poverty_status": "not_requested"},
        )
    if not isinstance(raw_config, Mapping):
        message = "ordinal_poverty config must be a mapping; skipping ordinal poverty integration"
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "skipped", "reason": message},
            events=(NodeEvent(level="warn", message=message),),
            metadata={
                "ordinal_poverty_status": "skipped",
                "ordinal_poverty_reason": message,
            },
        )

    try:
        enabled = _coerce_optional_bool(
            raw_config.get("enabled"),
            name="ordinal_poverty.enabled",
            default=True,
        )
    except _DISTRIBUTIONAL_VALIDATION_ERRORS as exc:
        message = f"Ordinal poverty config invalid: {exc}"
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "skipped", "reason": str(exc)},
            events=(NodeEvent(level="warn", message=message),),
            metadata={
                "ordinal_poverty_status": "skipped",
                "ordinal_poverty_reason": str(exc),
            },
        )

    if not enabled:
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "disabled"},
            events=(),
            metadata={"ordinal_poverty_status": "disabled"},
        )

    try:
        baseline_raw = raw_config.get("baseline_category_matrix", raw_config.get("category_matrix"))
        baseline_matrix = _coerce_ordinal_category_matrix(
            baseline_raw,
            name="ordinal_poverty.baseline_category_matrix",
            expected_agents=baseline_agent_count,
        )
        counterfactual_raw = raw_config.get(
            "counterfactual_category_matrix",
            raw_config.get("simulated_category_matrix"),
        )
        counterfactual_matrix = (
            _coerce_ordinal_category_matrix(
                counterfactual_raw,
                name="ordinal_poverty.counterfactual_category_matrix",
                expected_agents=counterfactual_agent_count,
            )
            if counterfactual_raw is not None
            else None
        )
        baseline = _run_ordinal_poverty_estimate(
            raw_config,
            category_matrix=baseline_matrix,
            label="baseline",
        )
        counterfactual = (
            _run_ordinal_poverty_estimate(
                raw_config,
                category_matrix=counterfactual_matrix,
                label="counterfactual",
            )
            if counterfactual_matrix is not None
            else None
        )
        report = OrdinalPovertyReport(
            methodology=str(raw_config.get("methodology", "oraf_phase2")),
            baseline=baseline,
            counterfactual=counterfactual,
            source_simulation_ref=str(sim_result_ref.artifact_id),
            metadata={
                "run_id": state.run_id,
                "baseline_agent_count": baseline_agent_count,
                "counterfactual_agent_count": counterfactual_agent_count,
            },
        )
        ref = persist_ordinal_poverty_report(ctx.store, report, inputs=artifact_inputs)
        summary = _ordinal_poverty_summary_from_report(report, ref=ref)
        event_message = (
            "Ordinal multidimensional poverty report generated"
            if counterfactual is not None
            else "Ordinal multidimensional poverty baseline report generated"
        )
        return _OrdinalPovertyResolution(
            ref=ref,
            summary=summary,
            events=(NodeEvent(level="info", message=event_message),),
            metadata={
                "ordinal_poverty_status": summary["status"],
                "ordinal_poverty_ref": str(ref.artifact_id),
                "ordinal_poverty_methodology": report.methodology,
            },
        )
    except _DISTRIBUTIONAL_VALIDATION_ERRORS as exc:
        message = f"Ordinal poverty analysis skipped: {exc}"
        return _OrdinalPovertyResolution(
            ref=None,
            summary={"status": "skipped", "reason": str(exc)},
            events=(NodeEvent(level="warn", message=message),),
            metadata={
                "ordinal_poverty_status": "skipped",
                "ordinal_poverty_reason": str(exc),
            },
        )


def _causal_assumptions(
    *,
    weighting_mode: str,
    proof_kernel_identified: bool = False,
) -> list[str]:
    assumptions = [
        assumption
        for assumption in _BASE_CAUSAL_ASSUMPTIONS
        if (
            not proof_kernel_identified
            or assumption != "distributional_estimand_not_proof_kernel_identified"
        )
    ]
    if weighting_mode != "density_ratio":
        assumptions.append("uniform_weighting_used")
    return assumptions


def _resolve_distributional_treatment_variable(state: ExperimentState) -> str | None:
    for key in ("distributional_treatment_variable", "query_treatment", "treatment_variable"):
        raw = state.params.get(key)
        if raw is None:
            continue
        candidate = str(raw).strip()
        if candidate:
            return candidate
    return None


def _resolve_distributional_graph(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[CausalGraphModelRef | None, Any | None]:
    raw = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
    if raw is None:
        raw = state.params.get("causal_graph_ref")
    if raw is None:
        return None, None
    try:
        payload = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
        graph_ref = CausalGraphModelRef.model_validate(payload)
        return graph_ref, load_causal_graph_model(ctx.store, graph_ref)
    except _DISTRIBUTIONAL_LOAD_ERRORS:
        return None, None


def _resolve_distributional_justification(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    outcome_name: str,
    weighting_mode: str,
) -> _DistributionalJustificationResolution:
    base_metadata = {
        "distributional_query_kind": "interventional_law",
        "coupling_justification": DistributionalJustification.SCENARIO.value,
        "marginal_law_justification": DistributionalJustification.SCENARIO.value,
    }
    treatment = _resolve_distributional_treatment_variable(state)
    if treatment is None:
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=_coupling_assumptions(weighting_mode=weighting_mode),
            metadata={
                **base_metadata,
                "proof_kernel": {
                    "status": "unavailable",
                    "reason": "missing_treatment_variable",
                },
            },
        )

    graph_ref, graph = _resolve_distributional_graph(ctx, state)
    if graph_ref is None or graph is None:
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=_coupling_assumptions(weighting_mode=weighting_mode),
            metadata={
                **base_metadata,
                "proof_kernel": {
                    "status": "unavailable",
                    "reason": "missing_reconciled_causal_graph",
                    "treatment_variable": treatment,
                },
            },
        )

    query = DistributionLawQuery(
        outcome_variables=(outcome_name,),
        intervention_set=(treatment,),
        support_space="real",
        representation="cdf",
    )
    engine = CausalEngine(registry=None, knowledge_base=None)
    result = engine.identify(
        treatment,
        outcome_name,
        graph,
        distribution_query=query,
    )
    coupling_assumptions = _coupling_assumptions(weighting_mode=weighting_mode)

    if isinstance(result, IdentificationResult):
        proof_bundle = proof_bundle_from_identification_result(
            result,
            graph_ref=str(graph_ref.artifact_id),
        )
        proof_metadata = {
            "status": proof_bundle.proof_status,
            "theorem_family": proof_bundle.theorem_family,
            "proof_stratum": proof_bundle.proof_stratum,
            "query_kind": proof_bundle.metadata.get("query_kind"),
            "distributional_query_kind": "interventional_law",
            "distribution_family": proof_bundle.metadata.get("distribution_family"),
            "generator_type": proof_bundle.metadata.get("generator_type"),
            "parameter_domain": proof_bundle.metadata.get("parameter_domain"),
            "support_space": proof_bundle.metadata.get("support_space"),
            "representation": proof_bundle.metadata.get("representation"),
            "derived_functionals_allowed": proof_bundle.metadata.get("derived_functionals_allowed"),
            "not_identified_objects": proof_bundle.metadata.get("not_identified_objects"),
            "query_ref": proof_bundle.query_ref,
            "graph_ref": str(graph_ref.artifact_id),
            "treatment_variable": treatment,
            "outcome_name": outcome_name,
        }
        if result.status is IdentificationStatus.IDENTIFIED:
            assumptions = _causal_assumptions(
                weighting_mode=weighting_mode,
                proof_kernel_identified=True,
            )
            for assumption in proof_bundle.assumptions:
                if assumption not in assumptions:
                    assumptions.append(assumption)
            return _DistributionalJustificationResolution(
                marginal_justification=DistributionalJustification.IDENTIFIED,
                coupling_justification=DistributionalJustification.SCENARIO,
                causal_assumptions=assumptions,
                coupling_assumptions=coupling_assumptions,
                metadata={
                    **base_metadata,
                    "marginal_law_justification": DistributionalJustification.IDENTIFIED.value,
                    "proof_kernel": proof_metadata,
                },
                proof_bundle=proof_bundle,
                coupling_negative_certificate=_coupling_negative_certificate(
                    treatment=treatment,
                    outcome_name=outcome_name,
                    graph_ref=str(graph_ref.artifact_id),
                    marginal_proof=proof_bundle,
                ),
            )
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=coupling_assumptions,
            metadata={
                **base_metadata,
                "proof_kernel": proof_metadata,
            },
            proof_bundle=proof_bundle,
        )

    if isinstance(result, NegativeCertificate):
        proof_bundle = proof_bundle_from_negative_certificate(
            result,
            graph_ref=str(graph_ref.artifact_id),
            query_ref=f"P({outcome_name} in A | do({treatment}))",
            theorem_family="negative_distribution_law",
            status_raw="hedge_found",
        ).model_copy(
            update={
                "metadata": {
                    "query_kind": "distribution_law",
                    "distribution_family": "cdf",
                    "generator_type": query.generator_type,
                    "parameter_domain": query.resolved_parameter_domain,
                    "measure_determination_regime": "countable_generator_reduction",
                    "regularity_assumptions": [
                        "cdf_monotone",
                        "cdf_right_continuous",
                        "cdf_limits_0_1",
                    ],
                    "derived_functionals_allowed": [
                        "survival",
                        "tail_probability",
                        "quantile",
                        "expected_shortfall",
                        "quantile_shift",
                        "tail_risk_delta",
                        "histogram",
                    ],
                    "not_identified_objects": [
                        "ot_coupling",
                        "joint_potential_outcome_law",
                        "individual_treatment_effect_distribution",
                        "cross_world_transport_map",
                    ],
                    "status": "non_identified",
                    "required_distributions_count": len(result.required_distributions),
                },
            }
        )
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=coupling_assumptions,
            metadata={
                **base_metadata,
                "proof_kernel": {
                    "status": "non_identified",
                    "reason": result.to_summary(),
                    "blocking_type": result.blocking_type.value,
                    "query_kind": "distribution_law",
                    "distributional_query_kind": "interventional_law",
                    "treatment_variable": treatment,
                    "outcome_name": outcome_name,
                    "graph_ref": str(graph_ref.artifact_id),
                },
            },
            proof_bundle=proof_bundle,
        )

    return _DistributionalJustificationResolution(
        marginal_justification=DistributionalJustification.SCENARIO,
        coupling_justification=DistributionalJustification.SCENARIO,
        causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
        coupling_assumptions=_coupling_assumptions(weighting_mode=weighting_mode),
        metadata={
            **base_metadata,
            "proof_kernel": {
                "status": "unavailable",
                "reason": "unexpected_distribution_proof_result",
                "distributional_query_kind": "interventional_law",
                "treatment_variable": treatment,
                "outcome_name": outcome_name,
            },
        },
    )


def _resolve_distributional_bounds(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
    inputs: list[InputRef],
) -> _DistributionalBoundsResolution:
    config = _distributional_bounds_config(state)
    if config is None:
        return _empty_distributional_bounds_resolution({"status": "not_requested"})

    refs: list[DistributionalBoundsBundleRef] = []
    theorem_families: list[str] = []
    functionals: list[str] = []
    assumptions: list[str] = []
    skipped: list[str] = []
    bundle_summaries: list[dict[str, Any]] = []

    for index, request in enumerate(_distributional_bounds_requests(config)):
        family = str(request.get("theorem_family", request.get("method_family", ""))).strip()
        if family not in {
            "lee_trimming_distributional",
            "makarov_pointwise",
            "mtr_headcount",
            "mtr_theil",
            "mtr_atkinson",
            "mtr_gini_lorenz",
            "sd_headcount",
            "sd_theil",
            "sd_atkinson",
            "sd_gini_lorenz",
        }:
            skipped.append(f"request_{index}:unsupported_theorem_family")
            continue
        request_assumptions = _string_list(
            request.get("assumptions")
            or config.get("assumptions")
            or state.params.get("distributional_bound_assumptions")
        )
        state_payload = _distributional_bounds_state_payload(
            request,
            family=family,
            baseline_values=baseline_values,
            counterfactual_values=counterfactual_values,
        )
        if state_payload is None:
            skipped.append(f"request_{index}:missing_required_data")
            continue
        if (
            family == "lee_trimming_distributional"
            and "monotone_selection_S1_ge_S0" not in request_assumptions
        ):
            skipped.append(f"request_{index}:missing_monotone_selection_assumption")
            continue
        if family in {"mtr_headcount", "mtr_theil", "mtr_atkinson", "mtr_gini_lorenz"} and (
            "monotone_treatment_response_y1_ge_y0" not in request_assumptions
        ):
            skipped.append(f"request_{index}:missing_mtr_assumption")
            continue
        if family in {"sd_headcount", "sd_theil", "sd_atkinson", "sd_gini_lorenz"} and (
            "first_order_stochastic_dominance_y1_ge_y0" not in request_assumptions
        ):
            skipped.append(f"request_{index}:missing_fosd_assumption")
            continue
        if family == "makarov_pointwise" and not _makarov_marginals_licensed(request, config):
            skipped.append(f"request_{index}:marginal_laws_not_licensed")
            continue

        for functional, axis_values in _distributional_bounds_functional_axes(
            request,
            family=family,
            baseline_values=baseline_values,
            counterfactual_values=counterfactual_values,
        ):
            try:
                output = DistributionalBoundsEngineMethod.pure_step(
                    state_payload,
                    {
                        "theorem_family": family,
                        "functional": functional.value,
                        "axis_values": axis_values,
                        "target_potential_outcome": request.get("target_potential_outcome", "y1"),
                        "support_floor": request.get("support_floor"),
                        "support_ceiling": request.get("support_ceiling"),
                        "mean_floor": request.get("mean_floor"),
                        "outcome_unit": request.get("outcome_unit", "income"),
                    },
                )
                bundle_payload = output["result"]["distributional_bounds_bundle"]
                bundle = DistributionalBoundsBundle.model_validate(bundle_payload)
                dual_certificate_ref: DistributionalDualCertificateRef | None = None
                dual_certificate_payload = output["result"].get(
                    "distributional_dual_certificate_payload"
                )
                if isinstance(dual_certificate_payload, dict):
                    certificate = DistributionalDualCertificate.model_validate(
                        dual_certificate_payload
                    )
                    dual_certificate_ref = persist_distributional_dual_certificate(
                        ctx.store,
                        certificate,
                        inputs=inputs,
                    )
                    bundle = attach_distributional_dual_certificate_ref(
                        bundle, dual_certificate_ref
                    )
                ref = persist_distributional_bounds_bundle(
                    ctx.store,
                    bundle,
                    inputs=[
                        *inputs,
                        *(
                            [
                                InputRef(
                                    artifact_id=str(dual_certificate_ref.artifact_id),
                                    role="distributional_dual_certificate",
                                )
                            ]
                            if dual_certificate_ref is not None
                            else []
                        ),
                    ],
                )
            except _DISTRIBUTIONAL_EXECUTION_ERRORS as exc:
                skipped.append(f"request_{index}:{functional.value}:{exc.__class__.__name__}")
                continue
            refs.append(ref)
            theorem_families.append(str(bundle.metadata.get("theorem_family") or family))
            functionals.append(bundle.functional.value)
            assumptions.extend(request_assumptions)
            if bundle.method_summaries:
                assumptions.extend(
                    str(item) for item in bundle.method_summaries[0].assumptions_used
                )
            bundle_summaries.append(
                {
                    "ref": ref.model_dump(mode="json"),
                    "functional": bundle.functional.value,
                    "estimand_type": bundle.estimand_type,
                    "theorem_family": bundle.metadata.get("theorem_family") or family,
                    "sharpness_status": bundle.sharpness_status,
                    "warnings": list(bundle.warnings),
                    "pointwise_not_uniform": bool(bundle.metadata.get("pointwise_not_uniform")),
                    "dual_certificate_ref": (
                        bundle.dual_certificate_ref.model_dump(mode="json")
                        if bundle.dual_certificate_ref is not None
                        else None
                    ),
                }
            )

    if not refs:
        return _empty_distributional_bounds_resolution(
            {
                "status": "requested_but_not_applicable",
                "skipped_reasons": skipped,
            }
        )

    unique_theorems = _stable_unique(theorem_families)
    unique_functionals = _stable_unique(functionals)
    uniformity = _distributional_bounds_uniformity(bundle_summaries)
    return _DistributionalBoundsResolution(
        refs=refs,
        assumptions=_stable_unique(
            [
                *assumptions,
                "distributional_bounds_theorem_family",
                "bounded_distributional_functional",
            ]
        ),
        metadata={
            "status": "bounded",
            "primary_theorem_family": unique_theorems[0]
            if unique_theorems
            else "distributional_bounds",
            "theorem_families": unique_theorems,
            "functionals": unique_functionals,
            "bound_uniformity": uniformity.value,
            "bounds": bundle_summaries,
            "skipped_reasons": skipped,
            "pointwise_warning": any(
                POINTWISE_NON_UNIFORM_WARNING in summary.get("warnings", ())
                for summary in bundle_summaries
            ),
        },
        theorem_families=unique_theorems,
        functionals=unique_functionals,
        bound_uniformity=uniformity,
        proof_target=(
            DistributionalProofTarget.MARGINAL_PAIR
            if "makarov_pointwise" in unique_theorems
            else DistributionalProofTarget.CDF
        ),
    )


def _empty_distributional_bounds_resolution(
    metadata: dict[str, Any] | None = None,
) -> _DistributionalBoundsResolution:
    return _DistributionalBoundsResolution(
        refs=[],
        assumptions=[],
        metadata=dict(metadata or {}),
        theorem_families=[],
        functionals=[],
        bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
        proof_target=DistributionalProofTarget.CDF,
    )


def _distributional_bounds_config(state: ExperimentState) -> dict[str, Any] | None:
    raw = state.params.get("distributional_bounds")
    if raw is None:
        raw = state.params.get("distributional_bounds_config")
    if not isinstance(raw, dict):
        return None
    if raw.get("enabled") is False:
        return None
    return dict(raw)


def _distributional_bounds_requests(config: dict[str, Any]) -> list[dict[str, Any]]:
    requests = config.get("requests")
    if isinstance(requests, list):
        return [dict(item) for item in requests if isinstance(item, dict)]
    return [dict(config)]


def _distributional_bounds_state_payload(
    request: dict[str, Any],
    *,
    family: str,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
) -> dict[str, Any] | None:
    data = request.get("data") if isinstance(request.get("data"), dict) else request
    if family == "lee_trimming_distributional":
        outcome = _numeric_array(data.get("outcome"))
        treatment = _numeric_array(data.get("treatment"))
        selected = _numeric_array(data.get("selected"))
        if outcome is None or treatment is None or selected is None:
            return None
        return {"outcome": outcome, "treatment": treatment, "selected": selected}
    if family in {
        "mtr_headcount",
        "mtr_theil",
        "mtr_atkinson",
        "mtr_gini_lorenz",
        "sd_headcount",
        "sd_theil",
        "sd_atkinson",
        "sd_gini_lorenz",
    }:
        outcome = _numeric_array(data.get("outcome"))
        treatment = _numeric_array(data.get("treatment"))
        if outcome is None or treatment is None:
            return None
        return {"outcome": outcome, "treatment": treatment}

    treated = _numeric_array(data.get("treated_outcome"))
    control = _numeric_array(data.get("control_outcome"))
    if treated is None and bool(request.get("use_distributional_samples_as_marginals")):
        treated = np.asarray(counterfactual_values, dtype=float)
    if control is None and bool(request.get("use_distributional_samples_as_marginals")):
        control = np.asarray(baseline_values, dtype=float)
    if treated is None or control is None:
        return None
    return {"treated_outcome": treated, "control_outcome": control}


def _distributional_bounds_functional_axes(
    request: dict[str, Any],
    *,
    family: str,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
) -> list[tuple[DistributionalFunctional, tuple[float, ...]]]:
    if family == "lee_trimming_distributional":
        return [
            (
                DistributionalFunctional.TAIL_DELTA,
                _axis_values_from_request(
                    request,
                    keys=("tail_thresholds", "thresholds"),
                    default=(float(np.median(baseline_values)),),
                ),
            ),
            (
                DistributionalFunctional.QUANTILE_SHIFT,
                _axis_values_from_request(
                    request,
                    keys=("quantiles",),
                    default=(0.25, 0.5, 0.75),
                ),
            ),
        ]
    if family in {"mtr_headcount", "sd_headcount"}:
        return [
            (
                DistributionalFunctional.POVERTY_HEADCOUNT,
                _axis_values_from_request(
                    request,
                    keys=("poverty_lines", "poverty_line", "thresholds"),
                    default=(float(np.median(baseline_values)),),
                ),
            ),
        ]
    if family in {"mtr_theil", "sd_theil"}:
        return [
            (
                DistributionalFunctional.THEIL_T,
                (1.0,),
            ),
        ]
    if family in {"mtr_atkinson", "sd_atkinson"}:
        return [
            (DistributionalFunctional.ATKINSON, (epsilon,))
            for epsilon in _axis_values_from_request(
                request,
                keys=("atkinson_epsilons", "atkinson_epsilon", "epsilons", "epsilon"),
                default=(0.5,),
            )
        ]
    if family in {"mtr_gini_lorenz", "sd_gini_lorenz"}:
        return [
            (
                DistributionalFunctional.GINI,
                (1.0,),
            ),
        ]
    return [
        (
            DistributionalFunctional.ITE_TAIL_RISK,
            _axis_values_from_request(
                request,
                keys=("harm_thresholds", "thresholds"),
                default=(0.0,),
            ),
        ),
        (
            DistributionalFunctional.QUANTILE,
            _axis_values_from_request(
                request,
                keys=("quantiles",),
                default=(0.25, 0.5, 0.75),
            ),
        ),
    ]


def _axis_values_from_request(
    request: dict[str, Any],
    *,
    keys: tuple[str, ...],
    default: tuple[float, ...],
) -> tuple[float, ...]:
    axis_payload = request.get("axis_values")
    if isinstance(axis_payload, dict):
        for key in keys:
            values = _float_tuple(axis_payload.get(key))
            if values:
                return values
    for key in keys:
        values = _float_tuple(request.get(key))
        if values:
            return values
    return default


def _makarov_marginals_licensed(
    request: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    status = (
        str(request.get("marginal_law_status") or config.get("marginal_law_status") or "")
        .strip()
        .lower()
    )
    if status in {"identified", "bounded", "licensed"}:
        return True
    return bool(request.get("marginal_laws_licensed") or config.get("marginal_laws_licensed"))


def _distributional_bounds_uniformity(
    summaries: list[dict[str, Any]],
) -> DistributionalBoundUniformity:
    if any(summary.get("pointwise_not_uniform") for summary in summaries):
        return DistributionalBoundUniformity.POINTWISE_ONLY
    if any(POINTWISE_NON_UNIFORM_WARNING in summary.get("warnings", ()) for summary in summaries):
        return DistributionalBoundUniformity.POINTWISE_ONLY
    statuses = {str(summary.get("sharpness_status", "")) for summary in summaries}
    if statuses == {"sharp"}:
        return DistributionalBoundUniformity.UNIFORM_SHARP
    return DistributionalBoundUniformity.UNIFORM_OUTER


def _numeric_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        return None
    return array


def _float_tuple(value: Any) -> tuple[float, ...]:
    if value is None:
        return ()
    if isinstance(value, (int, float)):
        return (float(value),)
    if not isinstance(value, (list, tuple)):
        return ()
    output: list[float] = []
    for item in value:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            output.append(number)
    return tuple(output)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _stable_unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = str(value).strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            output.append(candidate)
    return output


def _coupling_assumptions(*, weighting_mode: str) -> list[str]:
    assumptions = [
        assumption
        for assumption in _causal_assumptions(
            weighting_mode=weighting_mode,
            proof_kernel_identified=True,
        )
        if assumption != "distributional_estimand_not_proof_kernel_identified"
    ]
    return assumptions


def _coupling_negative_certificate(
    *,
    treatment: str,
    outcome_name: str,
    graph_ref: str,
    marginal_proof: ProofBundle,
) -> NegativeCertificate:
    return NegativeCertificate(
        blocking_type=BlockingType.COUPLING_NOT_IDENTIFIED,
        blocking_description=(
            f"Marginal counterfactual law P({outcome_name} in A | do({treatment})) is certified, "
            "but the OT coupling / joint counterfactual law is not identified from current assumptions."
        ),
        technical_detail=(
            "Identified marginals do not determine the cross-world or transport coupling without "
            "additional assumptions such as rank invariance, monotone response, or panel linkage."
        ),
        quantitative_diagnostics={
            "graph_ref": graph_ref,
            "marginal_theorem_family": marginal_proof.theorem_family,
            "marginal_proof_status": marginal_proof.proof_status,
            "marginal_proof_stratum": marginal_proof.proof_stratum,
            "distribution_family": marginal_proof.metadata.get("distribution_family"),
            "not_identified_objects": list(
                marginal_proof.metadata.get("not_identified_objects") or []
            ),
        },
        constructive_message=(
            "Keep marginal distribution claims on the proof-carrying path, but treat coupling, "
            "transport heatmaps, and individual-level movement claims as scenario-only unless a "
            "separate coupling identification theorem is supplied."
        ),
    )


def _merge_assumptions(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for assumption in group:
            candidate = str(assumption).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            merged.append(candidate)
    return merged


def _distributional_theorem_family(
    *,
    proof_bundle: ProofBundle | None,
    metadata: dict[str, Any],
) -> str:
    if proof_bundle is not None:
        return proof_bundle.theorem_family
    proof_kernel = metadata.get("proof_kernel")
    if isinstance(proof_kernel, dict):
        status = str(proof_kernel.get("status", "") or "").strip().lower()
        if status:
            return f"distribution_law_{status}"
    return "distribution_law_scenario"


def _assumption_scope(assumption: str, *, default_scope: str) -> str:
    if assumption == "scenario_level_ot_coupling":
        return "coupling"
    if assumption in {
        "sinkhorn_regularized_discrete_measure_approximation",
        "uniform_weighting_used",
    }:
        return "estimation"
    return default_scope


def _assumption_status(
    assumption: str,
    *,
    marginal_justification: DistributionalJustification,
    default_scope: str,
) -> str:
    scope = _assumption_scope(assumption, default_scope=default_scope)
    if scope in {"coupling", "estimation"}:
        return "scenario_only"
    if marginal_justification is DistributionalJustification.BOUNDED:
        return "bound_needed"
    return "identified_needed"


def _assumption_theorem_family(
    assumption: str,
    *,
    default_theorem_family: str,
) -> str:
    if assumption == "scenario_level_ot_coupling":
        return "ot_coupling_scenario"
    if assumption == "sinkhorn_regularized_discrete_measure_approximation":
        return "ot_sinkhorn_transport"
    if assumption == "uniform_weighting_used":
        return "distributional_weighting_mode"
    if assumption == "distributional_estimand_not_proof_kernel_identified":
        return "distribution_law_unavailable"
    return default_theorem_family


def _assumption_description(assumption: str) -> str:
    description = _ASSUMPTION_DESCRIPTIONS.get(assumption)
    if description is not None:
        return description
    return assumption.replace("_", " ")


def _persist_distributional_assumption_cards(
    ctx: ExecutionContext,
    *,
    inputs: list[InputRef],
    marginal_assumptions: list[str],
    coupling_assumptions: list[str],
    marginal_justification: DistributionalJustification,
    default_theorem_family: str,
) -> _PersistedAssumptionCards:
    seen: set[str] = set()
    all_refs: list[CausalAssumptionCardRef] = []
    marginal_refs: list[CausalAssumptionCardRef] = []
    coupling_refs: list[CausalAssumptionCardRef] = []

    def _persist_group(assumptions: list[str], *, default_scope: str) -> None:
        for assumption in assumptions:
            candidate = str(assumption).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            scope = _assumption_scope(candidate, default_scope=default_scope)
            ref = persist_causal_assumption_card(
                ctx.store,
                CausalAssumptionCard(
                    scope=scope,
                    status=_assumption_status(
                        candidate,
                        marginal_justification=marginal_justification,
                        default_scope=default_scope,
                    ),
                    theorem_family=_assumption_theorem_family(
                        candidate,
                        default_theorem_family=default_theorem_family,
                    ),
                    assumption_type=candidate,
                    description=_assumption_description(candidate),
                    testable=candidate in _TESTABLE_ASSUMPTIONS,
                ),
                inputs=inputs,
            )
            all_refs.append(ref)
            if scope == "coupling":
                coupling_refs.append(ref)
            elif scope == "estimation":
                marginal_refs.append(ref)
                coupling_refs.append(ref)
            else:
                marginal_refs.append(ref)

    _persist_group(marginal_assumptions, default_scope="marginal")
    _persist_group(coupling_assumptions, default_scope="coupling")
    return _PersistedAssumptionCards(
        all_refs=all_refs,
        marginal_refs=marginal_refs,
        coupling_refs=coupling_refs,
    )


def _maybe_persist_distributional_estimand_ast(
    ctx: ExecutionContext,
    *,
    proof_bundle: ProofBundle | None,
    inputs: list[InputRef],
) -> EstimandASTRef | None:
    if proof_bundle is None or proof_bundle.estimand_ast is None:
        return None
    try:
        estimand_ast = (
            proof_bundle.estimand_ast
            if isinstance(proof_bundle.estimand_ast, EstimandAST)
            else EstimandAST.model_validate(proof_bundle.estimand_ast)
        )
    except _DISTRIBUTIONAL_VALIDATION_ERRORS:
        return None
    return persist_estimand_ast(ctx.store, estimand_ast, inputs=inputs)


def _bound_uniformity_for_justification(
    justification: DistributionalJustification,
) -> DistributionalBoundUniformity:
    if justification is DistributionalJustification.IDENTIFIED:
        return DistributionalBoundUniformity.IDENTIFIED
    if justification is DistributionalJustification.BOUNDED:
        return DistributionalBoundUniformity.UNIFORM_OUTER
    return DistributionalBoundUniformity.NOT_APPLICABLE


def _coupling_status_for_justification(
    justification: DistributionalJustification | None,
) -> DistributionalCouplingStatus:
    if justification is DistributionalJustification.IDENTIFIED:
        return DistributionalCouplingStatus.IDENTIFIED
    if justification is DistributionalJustification.BOUNDED:
        return DistributionalCouplingStatus.SET_IDENTIFIED
    if justification is DistributionalJustification.SCENARIO:
        return DistributionalCouplingStatus.SCENARIO_ONLY
    return DistributionalCouplingStatus.NOT_USED


def _persist_distributional_proof_artifacts(
    ctx: ExecutionContext,
    *,
    inputs: list[InputRef],
    proof_bundle: ProofBundle | None,
    metadata: dict[str, Any],
    marginal_justification: DistributionalJustification,
    coupling_justification: DistributionalJustification | None,
    marginal_assumption_refs: list[CausalAssumptionCardRef],
    coupling_assumption_refs: list[CausalAssumptionCardRef],
    coupling_negative_certificate: NegativeCertificate | None,
    distributional_bounds_refs: list[DistributionalBoundsBundleRef] | None = None,
    distributional_bounds_metadata: dict[str, Any] | None = None,
    distributional_bounds_uniformity: DistributionalBoundUniformity | None = None,
    distributional_bounds_target: DistributionalProofTarget | None = None,
) -> tuple[DistributionalProofArtifactRef | None, DistributionalProofArtifactRef | None]:
    proof_bundle_ref: ProofBundleRef | None = None
    if proof_bundle is not None:
        proof_bundle_ref = persist_proof_bundle(ctx.store, proof_bundle, inputs=inputs)
    estimand_ast_ref = _maybe_persist_distributional_estimand_ast(
        ctx,
        proof_bundle=proof_bundle,
        inputs=inputs,
    )
    theorem_family = _distributional_theorem_family(
        proof_bundle=proof_bundle,
        metadata=metadata,
    )
    marginal_ref: DistributionalProofArtifactRef | None = None
    bounds_refs = list(distributional_bounds_refs or [])
    if proof_bundle_ref is not None:
        marginal_ref = persist_distributional_proof_artifact(
            ctx.store,
            DistributionalProofArtifact(
                base_proof_ref=proof_bundle_ref,
                estimand_ast_ref=estimand_ast_ref,
                target=(
                    distributional_bounds_target
                    if (
                        marginal_justification is DistributionalJustification.BOUNDED
                        and distributional_bounds_target is not None
                    )
                    else DistributionalProofTarget.CDF
                ),
                bounded_curve_ref=(
                    bounds_refs[0]
                    if (
                        marginal_justification is DistributionalJustification.BOUNDED
                        and bounds_refs
                    )
                    else None
                ),
                bound_uniformity=(
                    distributional_bounds_uniformity
                    if (
                        marginal_justification is DistributionalJustification.BOUNDED
                        and distributional_bounds_uniformity is not None
                    )
                    else _bound_uniformity_for_justification(marginal_justification)
                ),
                coupling_status=DistributionalCouplingStatus.NOT_USED,
                theorem_family=theorem_family,
                assumption_card_refs=marginal_assumption_refs,
                metadata={
                    "distributional_query_kind": metadata.get("distributional_query_kind"),
                    "proof_kernel": metadata.get("proof_kernel"),
                    "proof_status": proof_bundle.proof_status,
                    "justification": marginal_justification.value,
                    "distributional_bounds_refs": [
                        ref.model_dump(mode="json") for ref in bounds_refs
                    ],
                },
            ),
            inputs=inputs,
        )
    if marginal_ref is None and bounds_refs:
        bounds_metadata = dict(distributional_bounds_metadata or {})
        first_bounds_ref = bounds_refs[0]
        marginal_ref = persist_distributional_proof_artifact(
            ctx.store,
            DistributionalProofArtifact(
                target=distributional_bounds_target or DistributionalProofTarget.CDF,
                bounded_curve_ref=first_bounds_ref,
                bound_uniformity=(
                    distributional_bounds_uniformity or DistributionalBoundUniformity.UNIFORM_OUTER
                ),
                coupling_status=DistributionalCouplingStatus.NOT_USED,
                theorem_family=str(
                    bounds_metadata.get("primary_theorem_family")
                    or bounds_metadata.get("theorem_family")
                    or theorem_family
                    or "distributional_bounds"
                ),
                assumption_card_refs=marginal_assumption_refs,
                metadata={
                    "distributional_query_kind": metadata.get("distributional_query_kind"),
                    "justification": marginal_justification.value,
                    "distributional_bounds_refs": [
                        ref.model_dump(mode="json") for ref in bounds_refs
                    ],
                    **bounds_metadata,
                },
            ),
            inputs=[
                *inputs,
                *(
                    InputRef(artifact_id=str(ref.artifact_id), role="distributional_bounds_bundle")
                    for ref in bounds_refs
                ),
            ],
        )

    coupling_negative_ref: NegativeCertificateRef | None = None
    if coupling_negative_certificate is not None:
        coupling_negative_ref = persist_negative_certificate(
            ctx.store,
            coupling_negative_certificate,
            inputs=inputs,
        )
    coupling_ref: DistributionalProofArtifactRef | None = None
    coupling_status = _coupling_status_for_justification(coupling_justification)
    if coupling_status is not DistributionalCouplingStatus.NOT_USED:
        coupling_ref = persist_distributional_proof_artifact(
            ctx.store,
            DistributionalProofArtifact(
                base_proof_ref=proof_bundle_ref,
                estimand_ast_ref=estimand_ast_ref,
                target=DistributionalProofTarget.COUPLING,
                bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
                coupling_status=coupling_status,
                theorem_family=(
                    theorem_family
                    if coupling_status is not DistributionalCouplingStatus.SCENARIO_ONLY
                    else "ot_coupling_scenario"
                ),
                assumption_card_refs=coupling_assumption_refs,
                metadata={
                    "distributional_query_kind": metadata.get("distributional_query_kind"),
                    "proof_kernel": metadata.get("proof_kernel"),
                    "negative_certificate_ref": (
                        coupling_negative_ref.model_dump(mode="json")
                        if coupling_negative_ref is not None
                        else None
                    ),
                    "justification": coupling_justification.value
                    if coupling_justification is not None
                    else None,
                },
            ),
            inputs=inputs,
        )
    return marginal_ref, coupling_ref


def _recommended_n_bins(sample_size: int) -> int:
    return max(4, min(64, int(sample_size // 2) if sample_size < 128 else 64))


def _distribution_summary(
    *,
    outcome_name: str,
    values: np.ndarray,
    result_measure: Any,
    metadata: dict[str, Any] | None = None,
) -> DiscreteDistributionSummary:
    counts, _ = np.histogram(values, bins=result_measure.bin_edges)
    bins = [
        DistributionBin(
            index=index,
            lower_edge=float(result_measure.bin_edges[index]),
            upper_edge=float(result_measure.bin_edges[index + 1]),
            midpoint=float(result_measure.support[index]),
            probability=float(result_measure.probabilities[index]),
            sample_count=int(counts[index]),
        )
        for index in range(result_measure.support.shape[0])
    ]
    return DiscreteDistributionSummary(
        outcome_name=outcome_name,
        sample_size=int(result_measure.sample_size),
        total_weight=float(result_measure.total_weight),
        weighting_mode=str(result_measure.weighting_mode),
        mean_value=float(result_measure.mean_value),
        min_value=float(result_measure.min_value),
        max_value=float(result_measure.max_value),
        bins=bins,
        metadata=dict(metadata or {}),
    )


def _quantile_summary(
    *,
    outcome_name: str,
    result: ScalarOTDistributionalResult,
    metadata: dict[str, Any] | None = None,
) -> QuantileShiftSummary:
    return QuantileShiftSummary(
        outcome_name=outcome_name,
        entries=[
            QuantileShiftEntry(
                quantile=float(quantile),
                baseline_value=float(baseline_value),
                counterfactual_value=float(counterfactual_value),
                shift=float(shift),
            )
            for quantile, baseline_value, counterfactual_value, shift in zip(
                result.quantile_shift.quantiles,
                result.quantile_shift.baseline_values,
                result.quantile_shift.counterfactual_values,
                result.quantile_shift.shifts,
                strict=True,
            )
        ],
        metadata=dict(metadata or {}),
    )


def _maybe_none(value: float) -> float | None:
    return None if not math.isfinite(float(value)) else float(value)


def _tail_summary(
    *,
    outcome_name: str,
    result: ScalarOTDistributionalResult,
    metadata: dict[str, Any] | None = None,
) -> TailRiskDeltaSummary:
    return TailRiskDeltaSummary(
        outcome_name=outcome_name,
        entries=[
            TailRiskDeltaEntry(
                baseline_quantile=float(baseline_quantile),
                threshold_value=float(threshold_value),
                baseline_exceedance_probability=float(baseline_exceedance),
                counterfactual_exceedance_probability=float(counterfactual_exceedance),
                exceedance_probability_delta=float(exceedance_delta),
                baseline_expected_shortfall=_maybe_none(baseline_shortfall),
                counterfactual_expected_shortfall=_maybe_none(counterfactual_shortfall),
                expected_shortfall_delta=_maybe_none(shortfall_delta),
            )
            for baseline_quantile, threshold_value, baseline_exceedance, counterfactual_exceedance, exceedance_delta, baseline_shortfall, counterfactual_shortfall, shortfall_delta in zip(
                result.tail_risk.tail_probs,
                result.tail_risk.thresholds,
                result.tail_risk.baseline_exceedance_probs,
                result.tail_risk.counterfactual_exceedance_probs,
                result.tail_risk.exceedance_deltas,
                result.tail_risk.baseline_expected_shortfalls,
                result.tail_risk.counterfactual_expected_shortfalls,
                result.tail_risk.expected_shortfall_deltas,
                strict=True,
            )
        ],
        metadata=dict(metadata or {}),
    )


def _coupling_summary(
    *,
    result: ScalarOTDistributionalResult,
    metadata: dict[str, Any] | None = None,
) -> OTCouplingSummary:
    matrix = tuple(
        tuple(float(value) for value in row)
        for row in np.asarray(result.coupling_matrix, dtype=float)
    )
    return OTCouplingSummary(
        source_support=tuple(float(value) for value in result.baseline_measure.support),
        target_support=tuple(float(value) for value in result.counterfactual_measure.support),
        transport_matrix=matrix,
        regularization_strength=float(result.regularization_strength),
        sinkhorn_iterations=int(result.sinkhorn_iterations),
        convergence_delta=float(result.convergence_delta),
        weighting_mode=result.weighting_mode,
        density_ratio_diagnostics=dict(result.density_ratio_diagnostics),
        metadata=dict(metadata or {}),
    )


def _coupling_diagnostics(
    *,
    result: ScalarOTDistributionalResult,
    assumptions: list[str],
    metadata: dict[str, Any] | None = None,
) -> CouplingDiagnostics:
    return CouplingDiagnostics(
        mass_conservation_error=float(result.mass_conservation_error),
        source_marginal_l1_error=float(result.source_marginal_l1_error),
        target_marginal_l1_error=float(result.target_marginal_l1_error),
        support_mismatch_note=result.support_mismatch_note,
        regularization_strength=float(result.regularization_strength),
        sinkhorn_iterations=int(result.sinkhorn_iterations),
        convergence_delta=float(result.convergence_delta),
        weighting_mode=result.weighting_mode,
        identifiability_assumptions=list(assumptions),
        metadata=dict(metadata or {}),
    )


def _persist_scalar_artifacts(
    ctx: ExecutionContext,
    *,
    outcome_name: str,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
    result: ScalarOTDistributionalResult,
    inputs: list[InputRef],
    coupling_assumptions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> _PersistedScalarArtifacts:
    artifact_metadata = dict(metadata or {})
    assumptions = list(
        coupling_assumptions
        if coupling_assumptions is not None
        else _coupling_assumptions(weighting_mode=result.weighting_mode)
    )
    baseline_ref = persist_discrete_distribution_summary(
        ctx.store,
        _distribution_summary(
            outcome_name=outcome_name,
            values=baseline_values,
            result_measure=result.baseline_measure,
            metadata={**artifact_metadata, "distribution_role": "baseline"},
        ),
        inputs=inputs,
    )
    counterfactual_ref = persist_discrete_distribution_summary(
        ctx.store,
        _distribution_summary(
            outcome_name=outcome_name,
            values=counterfactual_values,
            result_measure=result.counterfactual_measure,
            metadata={**artifact_metadata, "distribution_role": "counterfactual"},
        ),
        inputs=inputs,
    )
    quantile_ref = persist_quantile_shift_summary(
        ctx.store,
        _quantile_summary(outcome_name=outcome_name, result=result, metadata=artifact_metadata),
        inputs=inputs,
    )
    tail_ref = persist_tail_risk_delta_summary(
        ctx.store,
        _tail_summary(outcome_name=outcome_name, result=result, metadata=artifact_metadata),
        inputs=inputs,
    )
    coupling_ref = persist_ot_coupling_summary(
        ctx.store,
        _coupling_summary(result=result, metadata=artifact_metadata),
        inputs=inputs,
    )
    diagnostics = _coupling_diagnostics(
        result=result,
        assumptions=assumptions,
        metadata=artifact_metadata,
    )
    return _PersistedScalarArtifacts(
        baseline_distribution_ref=baseline_ref,
        counterfactual_distribution_ref=counterfactual_ref,
        coupling_ref=coupling_ref,
        quantile_shift_ref=quantile_ref,
        tail_risk_delta_ref=tail_ref,
        coupling_diagnostics=diagnostics,
    )


def _persist_subgroup_artifacts(
    ctx: ExecutionContext,
    *,
    incomes_before: np.ndarray,
    incomes_after: np.ndarray,
    inputs: list[InputRef],
    base_assumptions: list[str],
    coupling_assumptions: list[str],
    geography_groups: list[_SubgroupSpec],
    geography_skip_reasons: list[str],
) -> tuple[list[Any], list[NodeEvent]]:
    refs: list[Any] = []
    events: list[NodeEvent] = []

    for subgroup in _income_quintile_subgroups(incomes_before):
        refs.append(
            _persist_subgroup_comparison(
                ctx,
                subgroup=subgroup,
                baseline_values=incomes_before[subgroup.mask],
                counterfactual_values=incomes_after[subgroup.mask],
                inputs=inputs,
                causal_assumptions=base_assumptions,
                coupling_assumptions=coupling_assumptions,
            )
        )

    for reason in geography_skip_reasons:
        events.append(NodeEvent(level="warn", message=reason))
    for subgroup in geography_groups:
        refs.append(
            _persist_subgroup_comparison(
                ctx,
                subgroup=subgroup,
                baseline_values=incomes_before[subgroup.mask],
                counterfactual_values=incomes_after[subgroup.mask],
                inputs=inputs,
                causal_assumptions=base_assumptions,
                coupling_assumptions=coupling_assumptions,
            )
        )
    return refs, events


def _persist_subgroup_comparison(
    ctx: ExecutionContext,
    *,
    subgroup: _SubgroupSpec,
    baseline_values: np.ndarray,
    counterfactual_values: np.ndarray,
    inputs: list[InputRef],
    causal_assumptions: list[str],
    coupling_assumptions: list[str],
) -> Any:
    result = compute_scalar_distributional_effect(
        baseline_values,
        counterfactual_values,
        n_bins=_recommended_n_bins(min(baseline_values.size, counterfactual_values.size)),
    )
    artifact_metadata = {
        "scope": "subgroup",
        "subgroup_dimension": subgroup.dimension.value,
        "subgroup_id": subgroup.subgroup_id,
    }
    persisted = _persist_scalar_artifacts(
        ctx,
        outcome_name="income",
        baseline_values=baseline_values,
        counterfactual_values=counterfactual_values,
        result=result,
        inputs=inputs,
        coupling_assumptions=coupling_assumptions,
        metadata=artifact_metadata,
    )
    comparison = SubgroupDistributionComparison(
        subgroup_dimension=subgroup.dimension,
        subgroup_id=subgroup.subgroup_id,
        subgroup_label=subgroup.subgroup_label,
        baseline_distribution_ref=persisted.baseline_distribution_ref,
        counterfactual_distribution_ref=persisted.counterfactual_distribution_ref,
        coupling_ref=persisted.coupling_ref,
        coupling_diagnostics=persisted.coupling_diagnostics,
        quantile_shift_ref=persisted.quantile_shift_ref,
        tail_risk_delta_ref=persisted.tail_risk_delta_ref,
        wasserstein_distance=float(result.wasserstein_distance),
        baseline_sample_size=int(baseline_values.size),
        counterfactual_sample_size=int(counterfactual_values.size),
        causal_assumptions=list(causal_assumptions),
        metadata=artifact_metadata,
    )
    return persist_subgroup_distribution_comparison(ctx.store, comparison, inputs=inputs)


def _income_quintile_subgroups(incomes_before: np.ndarray) -> list[_SubgroupSpec]:
    edges = np.percentile(incomes_before, [0, 20, 40, 60, 80, 100])
    groups: list[_SubgroupSpec] = []
    for index in range(5):
        lower = edges[index]
        upper = edges[index + 1]
        if index == 4:
            mask = incomes_before >= lower
        else:
            mask = (incomes_before >= lower) & (incomes_before < upper)
        if int(np.sum(mask)) == 0:
            continue
        groups.append(
            _SubgroupSpec(
                dimension=CohortDimension.INCOME_QUINTILE,
                subgroup_id=f"Q{index + 1}",
                subgroup_label=f"Q{index + 1} ({index * 20}-{(index + 1) * 20}%)",
                mask=mask,
            )
        )
    return groups


def _aligned_geography_subgroups(
    *,
    baseline_state: object,
    simulated_state: object,
) -> tuple[list[_SubgroupSpec], list[str]]:
    baseline_regions = getattr(getattr(baseline_state, "agents", object()), "employer_id", None)
    simulated_regions = getattr(getattr(simulated_state, "agents", object()), "employer_id", None)
    if baseline_regions is None or simulated_regions is None:
        return [], ["Geography subgroup comparisons skipped: employer_id missing"]

    baseline_arr = np.asarray(baseline_regions)
    simulated_arr = np.asarray(simulated_regions)
    if (
        baseline_arr.ndim != 1
        or simulated_arr.ndim != 1
        or baseline_arr.shape != simulated_arr.shape
    ):
        return [], ["Geography subgroup comparisons skipped: employer_id shape mismatch"]
    if not np.array_equal(baseline_arr, simulated_arr):
        return [], [
            "Geography subgroup comparisons skipped: employer_id not aligned between snapshots"
        ]

    groups: list[_SubgroupSpec] = []
    warnings: list[str] = []
    valid_mask = baseline_arr >= 0
    if int(np.sum(valid_mask)) < _GEOGRAPHY_MIN_GROUP_SIZE:
        return [], [
            "Geography subgroup comparisons skipped: insufficient aligned geography observations"
        ]

    for region in np.unique(baseline_arr[valid_mask]):
        mask = baseline_arr == region
        count = int(np.sum(mask))
        if count < _GEOGRAPHY_MIN_GROUP_SIZE:
            warnings.append(
                f"Geography subgroup {int(region)} skipped: only {count} observations (< {_GEOGRAPHY_MIN_GROUP_SIZE})"
            )
            continue
        groups.append(
            _SubgroupSpec(
                dimension=CohortDimension.GEOGRAPHY,
                subgroup_id=f"region_{int(region)}",
                subgroup_label=f"Employer Region {int(region)}",
                mask=mask,
            )
        )
    if len(groups) < 2:
        warnings.append(
            "Geography subgroup comparisons skipped: fewer than two sufficiently sized aligned regions"
        )
        return [], warnings
    return groups, warnings


def _resolve_baseline_snapshot_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> StateSnapshotRef | None:
    explicit = state.inputs.get(INPUT_STATE_SNAPSHOT_REF)
    if explicit is not None:
        try:
            return StateSnapshotRef.model_validate(explicit.model_dump())
        except _DISTRIBUTIONAL_VALIDATION_ERRORS:
            return None

    input_bindings_ref = state.inputs.get(INPUT_INPUT_BINDINGS_REF)
    if input_bindings_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(input_bindings_ref.artifact_id))
            bindings = FoundryInputBindings.model_validate(payload)
            return bindings.bound_state_snapshot_ref
        except _DISTRIBUTIONAL_LOAD_ERRORS:
            return None

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref.artifact_id))
        snapshot = DataSnapshot.model_validate(payload)
    except _DISTRIBUTIONAL_LOAD_ERRORS:
        return None
    if snapshot.data_ref.kind != "foundry.state_snapshot":
        return None
    return StateSnapshotRef(artifact_id=snapshot.data_ref.artifact_id)


def _build_aligned_geography_breakdown(
    *,
    baseline_state: object,
    incomes_before: np.ndarray,
    incomes_after: np.ndarray,
    geography_groups: list[_SubgroupSpec],
):
    if not geography_groups:
        return None
    region_ids = getattr(getattr(baseline_state, "agents", object()), "employer_id", None)
    if region_ids is None:
        return None
    region_ids_arr = np.asarray(region_ids)
    if region_ids_arr.ndim != 1 or region_ids_arr.shape[0] != incomes_after.shape[0]:
        return None
    retained_mask = np.zeros(region_ids_arr.shape[0], dtype=bool)
    labels: dict[int, str] = {}
    for group in geography_groups:
        retained_mask |= group.mask
        try:
            region_id = int(str(group.subgroup_id).removeprefix("region_"))
        except ValueError:
            continue
        labels[region_id] = group.subgroup_label
    if int(np.sum(retained_mask)) < (2 * _GEOGRAPHY_MIN_GROUP_SIZE):
        return None
    region_ids_clean = region_ids_arr[retained_mask]
    if np.unique(region_ids_clean).size < 2:
        return None
    try:
        return build_geography_breakdown(
            region_ids_clean,
            labels,
            incomes_before[retained_mask],
            incomes_after[retained_mask],
            primary_metric="regional_income_change_pct",
        )
    except _DISTRIBUTIONAL_EXECUTION_ERRORS:
        return None


__all__ = ["RunDistributionalAnalysisNode"]
