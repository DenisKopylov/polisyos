"""Public simulate run distributional analysis module API."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

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
from polisyos.foundry.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.causal.density_ratio import (
    ScalarOTDistributionalResult,
    compute_scalar_distributional_effect,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionBin,
    DistributionalEffectBundle,
    DistributionalJustification,
    OTCouplingSummary,
    QuantileShiftEntry,
    QuantileShiftSummary,
    SubgroupDistributionComparison,
    TailRiskDeltaEntry,
    TailRiskDeltaSummary,
    persist_discrete_distribution_summary,
    persist_distributional_effect_bundle,
    persist_distributional_report,
    persist_ot_coupling_summary,
    persist_quantile_shift_summary,
    persist_subgroup_distribution_comparison,
    persist_tail_risk_delta_summary,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
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
_GEOGRAPHY_MIN_GROUP_SIZE = 10

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
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"inputs.{INPUT_STATE_SNAPSHOT_REF}",
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
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
                events=[NodeEvent(level="info", message="No simulation_result_ref; skip distributional analysis")],
            )

        try:
            sim_payload = from_canonical_bytes(ctx.store.get_bytes(sim_result_ref.artifact_id))
            sim_result = SimulationResult.model_validate(sim_payload)
        except Exception as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="warn", message=f"Unable to load SimulationResult: {exc}")],
            )

        if sim_result.state_snapshot_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="SimulationResult has no state_snapshot_ref; skip distributional analysis")],
            )

        baseline_ref = _resolve_baseline_snapshot_ref(ctx, state)
        if baseline_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="No baseline snapshot available; skip distributional analysis")],
            )

        try:
            baseline_state = load_state_snapshot(ctx.store, snapshot_ref=baseline_ref)
            simulated_state = load_state_snapshot(ctx.store, snapshot_ref=sim_result.state_snapshot_ref)
        except Exception as exc:
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
                events=[NodeEvent(level="info", message="Insufficient agents for distributional analysis")],
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

        report = build_distributional_report(
            breakdowns,
            incomes_before=incomes_before,
            incomes_after=incomes_after,
            source_simulation_ref=str(sim_result_ref.artifact_id),
            metadata={
                "run_id": state.run_id,
                "geography_breakdown_status": "included" if geography_breakdown is not None else "skipped",
                "geography_breakdown_skipped_reasons": list(geography_skipped_reasons),
                "geography_group_ids": [group.subgroup_id for group in geography_groups],
            },
        )
        artifact_inputs = _distributional_inputs(
            sim_result_ref=sim_result_ref,
            simulated_snapshot_ref=sim_result.state_snapshot_ref,
            baseline_snapshot_ref=baseline_ref,
        )

        try:
            overall_result = compute_scalar_distributional_effect(
                incomes_before,
                incomes_after,
                n_bins=_recommended_n_bins(min(incomes_before.size, incomes_after.size)),
            )
            causal_assumptions = _causal_assumptions(weighting_mode=overall_result.weighting_mode)
            overall_refs = _persist_scalar_artifacts(
                ctx,
                outcome_name="income",
                baseline_values=incomes_before,
                counterfactual_values=incomes_after,
                result=overall_result,
                inputs=artifact_inputs,
                metadata={"scope": "overall", "run_id": state.run_id},
            )
            subgroup_refs, subgroup_events = _persist_subgroup_artifacts(
                ctx,
                incomes_before=incomes_before,
                incomes_after=incomes_after,
                inputs=artifact_inputs,
                base_assumptions=causal_assumptions,
                geography_groups=geography_groups,
                geography_skip_reasons=geography_skipped_reasons,
            )
            bundle = DistributionalEffectBundle(
                outcome_name="income",
                justification=DistributionalJustification.SCENARIO,
                baseline_distribution_ref=overall_refs.baseline_distribution_ref,
                counterfactual_distribution_ref=overall_refs.counterfactual_distribution_ref,
                coupling_ref=overall_refs.coupling_ref,
                coupling_diagnostics=overall_refs.coupling_diagnostics,
                wasserstein_distance=float(overall_result.wasserstein_distance),
                quantile_shift_ref=overall_refs.quantile_shift_ref,
                tail_risk_delta_ref=overall_refs.tail_risk_delta_ref,
                subgroup_distribution_refs=subgroup_refs,
                causal_assumptions=causal_assumptions,
                readiness_cap="simulation_ready",
                metadata={
                    "run_id": state.run_id,
                    "source_simulation_ref": str(sim_result_ref.artifact_id),
                    "weighting_mode": overall_result.weighting_mode,
                },
            )
            bundle_ref = persist_distributional_effect_bundle(ctx.store, bundle, inputs=artifact_inputs)
            report_ref = persist_distributional_report(ctx.store, report, inputs=artifact_inputs)
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                events=[NodeEvent(level="error", message=f"Distributional D.1 build failed: {exc}")],
                error=NodeError(
                    code="distributional_analysis_failed",
                    message="Failed to build OT distributional artifacts",
                    details={"reason": str(exc)},
                ),
            )

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_REPORT_REF] = report_ref
        new_state.artifacts_index[ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF] = bundle_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[report_ref, bundle_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Distributional report generated with {len(report.breakdowns)} breakdown(s) "
                        f"and OT bundle with {len(subgroup_refs)} subgroup comparison(s)"
                    ),
                ),
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


def _causal_assumptions(*, weighting_mode: str) -> list[str]:
    assumptions = list(_BASE_CAUSAL_ASSUMPTIONS)
    if weighting_mode != "density_ratio":
        assumptions.append("uniform_weighting_used")
    return assumptions


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
    metadata: dict[str, Any] | None = None,
) -> _PersistedScalarArtifacts:
    artifact_metadata = dict(metadata or {})
    assumptions = _causal_assumptions(weighting_mode=result.weighting_mode)
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
    if baseline_arr.ndim != 1 or simulated_arr.ndim != 1 or baseline_arr.shape != simulated_arr.shape:
        return [], ["Geography subgroup comparisons skipped: employer_id shape mismatch"]
    if not np.array_equal(baseline_arr, simulated_arr):
        return [], ["Geography subgroup comparisons skipped: employer_id not aligned between snapshots"]

    groups: list[_SubgroupSpec] = []
    warnings: list[str] = []
    valid_mask = baseline_arr >= 0
    if int(np.sum(valid_mask)) < _GEOGRAPHY_MIN_GROUP_SIZE:
        return [], ["Geography subgroup comparisons skipped: insufficient aligned geography observations"]

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
        warnings.append("Geography subgroup comparisons skipped: fewer than two sufficiently sized aligned regions")
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
        except Exception:
            return None

    input_bindings_ref = state.inputs.get(INPUT_INPUT_BINDINGS_REF)
    if input_bindings_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(input_bindings_ref.artifact_id))
            bindings = FoundryInputBindings.model_validate(payload)
            return bindings.bound_state_snapshot_ref
        except Exception:
            return None

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref.artifact_id))
        snapshot = DataSnapshot.model_validate(payload)
    except Exception:
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
    except Exception:
        return None


__all__ = ["RunDistributionalAnalysisNode"]
