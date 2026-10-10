"""Distributional summary and CAS artifact-persistence helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.foundry.methods.catalog.causal.density_ratio import (
    ScalarOTDistributionalResult,
    compute_scalar_distributional_effect,
)
from polisyos.ir.analytics.distributional import (
    CouplingDiagnostics,
    DiscreteDistributionSummary,
    DistributionBin,
    OTCouplingSummary,
    QuantileShiftEntry,
    QuantileShiftSummary,
    SubgroupDistributionComparison,
    TailRiskDeltaEntry,
    TailRiskDeltaSummary,
    persist_discrete_distribution_summary,
    persist_ot_coupling_summary,
    persist_quantile_shift_summary,
    persist_subgroup_distribution_comparison,
    persist_tail_risk_delta_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_justification import (
    _coupling_assumptions,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _income_quintile_subgroups,
    _SubgroupSpec,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeEvent,
)

_DISTRIBUTIONAL_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)


@dataclass(frozen=True)
class _PersistedScalarArtifacts:
    baseline_distribution_ref: Any
    counterfactual_distribution_ref: Any
    coupling_ref: Any
    quantile_shift_ref: Any
    tail_risk_delta_ref: Any
    coupling_diagnostics: CouplingDiagnostics


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
        _ensure_ir_artifact_store(ctx.store),
        _distribution_summary(
            outcome_name=outcome_name,
            values=baseline_values,
            result_measure=result.baseline_measure,
            metadata={**artifact_metadata, "distribution_role": "baseline"},
        ),
        inputs=inputs,
    )
    counterfactual_ref = persist_discrete_distribution_summary(
        _ensure_ir_artifact_store(ctx.store),
        _distribution_summary(
            outcome_name=outcome_name,
            values=counterfactual_values,
            result_measure=result.counterfactual_measure,
            metadata={**artifact_metadata, "distribution_role": "counterfactual"},
        ),
        inputs=inputs,
    )
    quantile_ref = persist_quantile_shift_summary(
        _ensure_ir_artifact_store(ctx.store),
        _quantile_summary(outcome_name=outcome_name, result=result, metadata=artifact_metadata),
        inputs=inputs,
    )
    tail_ref = persist_tail_risk_delta_summary(
        _ensure_ir_artifact_store(ctx.store),
        _tail_summary(outcome_name=outcome_name, result=result, metadata=artifact_metadata),
        inputs=inputs,
    )
    coupling_ref = persist_ot_coupling_summary(
        _ensure_ir_artifact_store(ctx.store),
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
    return persist_subgroup_distribution_comparison(
        _ensure_ir_artifact_store(ctx.store), comparison, inputs=inputs
    )
