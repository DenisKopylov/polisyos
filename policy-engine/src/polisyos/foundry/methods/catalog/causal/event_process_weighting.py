"""Estimate event-process policy curves via local-independence weighting."""

from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.causal.protocols import EventProcessObservationalData
from polisyos.foundry.methods.catalog.causal.structural_time_series import (
    TemporalTrajectoryResult,
)
from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
    compile_temporal_estimand,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    TemporalIdentificationCertificate,
    TemporalInterventionTrajectory,
    TemporalPathRepresentation,
    TemporalTargetFunctional,
)


def _derive_at_risk(
    outcome_events: np.ndarray,
    censoring_events: np.ndarray,
) -> np.ndarray:
    n_units, n_periods = outcome_events.shape
    at_risk = np.ones((n_units, n_periods), dtype=bool)
    for index in range(1, n_periods):
        at_risk[:, index] = (
            at_risk[:, index - 1]
            & (outcome_events[:, index - 1] < 0.5)
            & (censoring_events[:, index - 1] < 0.5)
        )
    return at_risk


def _weighted_curve(
    *,
    outcome_events: np.ndarray,
    weights: np.ndarray,
    at_risk: np.ndarray,
    target_functional: TemporalTargetFunctional,
) -> tuple[np.ndarray, np.ndarray]:
    n_periods = outcome_events.shape[1]
    hazards = np.zeros(n_periods, dtype=float)
    survival = np.ones(n_periods, dtype=float)
    curve = np.zeros(n_periods, dtype=float)
    running_survival = 1.0
    for index in range(n_periods):
        risk_weights = weights[:, index] * at_risk[:, index].astype(float)
        denom = float(risk_weights.sum())
        hazard = 0.0
        if denom > 0.0:
            numer = float(
                np.sum(
                    weights[:, index] * at_risk[:, index].astype(float) * outcome_events[:, index]
                )
            )
            hazard = min(max(numer / denom, 0.0), 1.0)
        hazards[index] = hazard
        running_survival *= 1.0 - hazard
        survival[index] = running_survival
        curve[index] = (
            running_survival
            if target_functional is TemporalTargetFunctional.SURVIVAL_CURVE
            else 1.0 - running_survival
        )
    return curve, hazards


def _bootstrap_effect_paths(
    *,
    outcome_events: np.ndarray,
    censoring_events: np.ndarray,
    policy_weights: np.ndarray,
    baseline_weights: np.ndarray,
    at_risk: np.ndarray,
    target_functional: TemporalTargetFunctional,
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n_units = outcome_events.shape[0]
    draws = np.empty((max(1, n_draws), outcome_events.shape[1]), dtype=float)
    for index in range(draws.shape[0]):
        sample = rng.integers(0, n_units, size=n_units)
        policy_curve, _ = _weighted_curve(
            outcome_events=outcome_events[sample],
            weights=policy_weights[sample],
            at_risk=at_risk[sample],
            target_functional=target_functional,
        )
        baseline_curve, _ = _weighted_curve(
            outcome_events=outcome_events[sample],
            weights=baseline_weights[sample],
            at_risk=at_risk[sample],
            target_functional=target_functional,
        )
        draws[index] = policy_curve - baseline_curve
    return draws


def estimate_event_process_weighting_trajectory(
    data: EventProcessObservationalData | dict[str, Any],
    query: ContinuousTimeQuery,
    *,
    resolved_intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
    identification_certificate: TemporalIdentificationCertificate | dict[str, Any] | None = None,
) -> TemporalTrajectoryResult:
    """Estimate marginal policy curves from event-process data and weights."""

    event_data = (
        data
        if isinstance(data, EventProcessObservationalData)
        else EventProcessObservationalData.model_validate(data)
    )
    intervention = (
        None
        if resolved_intervention is None
        else (
            resolved_intervention
            if isinstance(resolved_intervention, TemporalInterventionTrajectory)
            else TemporalInterventionTrajectory.model_validate(resolved_intervention)
        )
    )
    plan = compile_temporal_estimand(
        query,
        data=event_data,
        resolved_intervention=intervention,
        identification_certificate=identification_certificate,
        allow_discrete_fallback=False,
    )
    positions = np.asarray(plan.time_index_positions, dtype=int)
    time_grid = np.asarray(plan.time_grid, dtype=float)
    outcome_events = np.asarray(event_data.outcome_events[:, positions], dtype=float)
    censoring_events = (
        np.zeros_like(outcome_events)
        if event_data.censoring_events is None
        else np.asarray(event_data.censoring_events[:, positions], dtype=float)
    )
    policy_weights = (
        np.ones_like(outcome_events, dtype=float)
        if event_data.policy_weights is None
        else np.asarray(event_data.policy_weights[:, positions], dtype=float)
    )
    baseline_weights = (
        np.ones_like(outcome_events, dtype=float)
        if event_data.baseline_weights is None
        else np.asarray(event_data.baseline_weights[:, positions], dtype=float)
    )
    at_risk = (
        _derive_at_risk(outcome_events, censoring_events)
        if event_data.at_risk is None
        else np.asarray(event_data.at_risk[:, positions], dtype=bool)
    )

    policy_curve, policy_hazards = _weighted_curve(
        outcome_events=outcome_events,
        weights=policy_weights,
        at_risk=at_risk,
        target_functional=query.target_functional,
    )
    baseline_curve, baseline_hazards = _weighted_curve(
        outcome_events=outcome_events,
        weights=baseline_weights,
        at_risk=at_risk,
        target_functional=query.target_functional,
    )
    effect_path = policy_curve - baseline_curve

    rng = np.random.default_rng(int((event_data.metadata or {}).get("bootstrap_seed", 0)))
    effect_samples = _bootstrap_effect_paths(
        outcome_events=outcome_events,
        censoring_events=censoring_events,
        policy_weights=policy_weights,
        baseline_weights=baseline_weights,
        at_risk=at_risk,
        target_functional=query.target_functional,
        n_draws=int(plan.solver_config.get("bootstrap_draws", 200)),
        rng=rng,
    )
    confidence_band_lower = np.quantile(effect_samples, 0.025, axis=0)
    confidence_band_upper = np.quantile(effect_samples, 0.975, axis=0)

    return TemporalTrajectoryResult(
        plan=plan,
        observed_path=tuple(float(value) for value in policy_curve.tolist()),
        counterfactual_path=tuple(float(value) for value in baseline_curve.tolist()),
        effect_path=tuple(float(value) for value in effect_path.tolist()),
        solver_mean_path=tuple(float(value) for value in effect_path.tolist()),
        confidence_band_lower=tuple(float(value) for value in confidence_band_lower.tolist()),
        confidence_band_upper=tuple(float(value) for value in confidence_band_upper.tolist()),
        integral_effect=float(np.trapezoid(effect_path, time_grid)),
        solver_family=str(plan.solver_config.get("solver_family", "local_independence_weighting")),
        path_representation=TemporalPathRepresentation.EVENT_PROCESS_WEIGHTING,
        discretization_error=None,
        discretization_note="not_applicable_for_event_process_weighting",
        causal_translation_certificate=None,
        causal_equivalence_note=None,
        continuous_time_degraded=False,
        diagnostics={
            "backend_target": plan.backend_target.value,
            "target_functional": plan.target_functional.value,
            "comparator_semantics": plan.comparator_semantics.value,
            "policy_hazards": [float(value) for value in policy_hazards.tolist()],
            "baseline_hazards": [float(value) for value in baseline_hazards.tolist()],
            "n_units": int(outcome_events.shape[0]),
            "grid_source": plan.grid_source,
            "process_family": str(event_data.metadata.get("process_family", "counting_process")),
        },
        metadata={
            "policy_curve_semantics": query.target_functional.value,
            "weighting_backend": "local_independence_weighting",
            "intervention_contract_status": plan.intervention_contract_status,
        },
    )


__all__ = ["estimate_event_process_weighting_trajectory"]
