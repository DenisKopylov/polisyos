"""Estimation helpers for coupled DES/ABM policy simulations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from math import sqrt
from typing import Any

import numpy as np

from polisyos.foundry.coupling.executor import CoupledRuntimeState

SummaryRunner = Callable[[Mapping[str, float], int | None], Mapping[str, float]]
PolicyRunner = Callable[[int], Mapping[str, float]]


@dataclass(frozen=True)
class QueueMLEEstimate:
    """Local MLE/partial-likelihood estimates for queue event logs."""

    arrival_rate: float
    service_rate: float
    abandonment_rate: float
    observation_window: float
    n_arrivals: int
    n_service_completions: int
    n_abandonments: int
    routing_probabilities: dict[str, float]


@dataclass(frozen=True)
class SMMResult:
    """Best summary-match fit over a bounded parameter search surface."""

    best_params: dict[str, float]
    best_loss: float
    fitted_summary: dict[str, float]
    observed_summary: dict[str, float]
    evaluated: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ParticleFilterResult:
    """Sequential queue-state filtering output."""

    filtered_mean: tuple[float, ...]
    filtered_std: tuple[float, ...]
    effective_sample_size: tuple[float, ...]
    log_likelihood: float


@dataclass(frozen=True)
class PairedMonteCarloResult:
    """Common-random-number policy effect summary."""

    mean_effects: dict[str, float]
    standard_errors: dict[str, float]
    paired_differences: tuple[dict[str, float], ...]
    n_replications: int


def estimate_queue_mle(
    event_log: Sequence[Mapping[str, Any]],
    *,
    time_key: str = "time",
    kind_key: str = "kind",
    entity_key: str = "entity_id",
    route_key: str = "route",
) -> QueueMLEEstimate:
    """Estimate local queue rates from arrival/start/complete/abandon event logs."""
    if not event_log:
        return QueueMLEEstimate(
            arrival_rate=0.0,
            service_rate=0.0,
            abandonment_rate=0.0,
            observation_window=0.0,
            n_arrivals=0,
            n_service_completions=0,
            n_abandonments=0,
            routing_probabilities={},
        )
    ordered = sorted(event_log, key=lambda row: float(row[time_key]))
    times = np.asarray([float(row[time_key]) for row in ordered], dtype=np.float64)
    observation_window = max(float(times[-1] - times[0]), 1e-9)
    kinds = [str(row.get(kind_key, "")) for row in ordered]
    n_arrivals = sum(kind in {"arrival", "claim_arrival", "queue_admit"} for kind in kinds)
    n_completed = sum(kind in {"service_complete", "eligibility_confirmed"} for kind in kinds)
    n_abandoned = sum(kind in {"abandon", "abandonment", "lwbs"} for kind in kinds)

    starts_by_entity: dict[str, float] = {}
    durations: list[float] = []
    for row in ordered:
        kind = str(row.get(kind_key, ""))
        entity = str(row.get(entity_key, ""))
        if "service_duration" in row:
            durations.append(max(float(row["service_duration"]), 0.0))
            continue
        if kind == "service_start" and entity:
            starts_by_entity[entity] = float(row[time_key])
        elif kind in {"service_complete", "eligibility_confirmed"} and entity in starts_by_entity:
            durations.append(max(float(row[time_key]) - starts_by_entity[entity], 0.0))

    arrival_rate = float(n_arrivals / observation_window)
    if durations:
        mean_duration = max(float(np.mean(durations)), 1e-9)
        service_rate = 1.0 / mean_duration
    else:
        service_rate = float(n_completed / observation_window)
    abandonment_rate = float(n_abandoned / observation_window)

    route_counts: dict[str, int] = {}
    for row in ordered:
        route = row.get(route_key)
        if route is not None:
            route_counts[str(route)] = route_counts.get(str(route), 0) + 1
    total_routes = max(sum(route_counts.values()), 1)
    routing_probabilities = {
        route: count / total_routes for route, count in sorted(route_counts.items())
    }

    return QueueMLEEstimate(
        arrival_rate=arrival_rate,
        service_rate=service_rate,
        abandonment_rate=abandonment_rate,
        observation_window=observation_window,
        n_arrivals=n_arrivals,
        n_service_completions=n_completed,
        n_abandonments=n_abandoned,
        routing_probabilities=routing_probabilities,
    )


def extract_coupled_summary(
    runtime: CoupledRuntimeState,
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    """Extract stable summary moments from a coupled simulation run."""
    state = runtime.global_state
    queue = runtime.queue_state
    completed_at = np.asarray(queue.completed_at, dtype=np.float64)
    queued_at = np.asarray(queue.queued_at, dtype=np.float64)
    completed_mask = completed_at >= 0.0
    waits = completed_at[completed_mask] - queued_at[completed_mask]
    queue_path = np.asarray(
        [float(item.get("queue/queue_length", np.nan)) for item in metrics],
        dtype=np.float64,
    )
    queue_path = queue_path[np.isfinite(queue_path)]
    return {
        "final_queue_length": float(np.asarray(queue.queue_length).item()),
        "admitted_count": float(np.asarray(queue.admitted_count).item()),
        "completed_count": float(np.asarray(queue.completed_count).item()),
        "rejected_count": float(np.asarray(queue.rejected_count).item()),
        "mean_wait": float(np.mean(waits)) if waits.size else 0.0,
        "p90_wait": float(np.quantile(waits, 0.90)) if waits.size else 0.0,
        "mean_queue_length": float(np.mean(queue_path)) if queue_path.size else 0.0,
        "final_mean_savings": float(np.mean(np.asarray(state.agents.savings))),
        "final_mean_income": float(np.mean(np.asarray(state.agents.income))),
    }


def summary_distance(
    simulated: Mapping[str, float],
    observed: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
) -> float:
    """Weighted squared distance between simulated and observed summary moments."""
    total = 0.0
    used = 0
    for name, observed_value in observed.items():
        if name not in simulated:
            continue
        weight = 1.0 if weights is None else float(weights.get(name, 1.0))
        if weight < 0.0 or not np.isfinite(weight):
            return float("inf")
        diff = float(simulated[name]) - float(observed_value)
        total += weight * diff * diff
        used += 1
    if used == 0:
        raise ValueError("No overlapping summary moments between simulated and observed")
    return float(total)


def calibrate_coupled_smm(
    parameter_grid: Mapping[str, Sequence[float]],
    runner: SummaryRunner,
    observed_summary: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
    seeds: Sequence[int | None] = (None,),
) -> SMMResult:
    """Grid-search SMM/indirect-inference adapter for coupled simulator outputs."""
    if not parameter_grid:
        raise ValueError("parameter_grid must not be empty")
    names = tuple(parameter_grid.keys())
    values = tuple(tuple(float(item) for item in parameter_grid[name]) for name in names)
    if any(not value for value in values):
        raise ValueError("each parameter_grid entry must contain at least one value")

    evaluated: list[dict[str, Any]] = []
    best_params: dict[str, float] | None = None
    best_summary: dict[str, float] | None = None
    best_loss = float("inf")
    for combination in product(*values):
        params = dict(zip(names, combination, strict=True))
        summaries = [runner(params, seed) for seed in seeds]
        averaged = _average_summaries(summaries)
        loss = summary_distance(averaged, observed_summary, weights=weights)
        evaluated.append({"params": params, "loss": loss, "summary": averaged})
        if loss < best_loss:
            best_loss = loss
            best_params = params
            best_summary = averaged

    assert best_params is not None
    assert best_summary is not None
    return SMMResult(
        best_params=best_params,
        best_loss=best_loss,
        fitted_summary=best_summary,
        observed_summary={key: float(value) for key, value in observed_summary.items()},
        evaluated=tuple(evaluated),
    )


def filter_queue_counts(
    observed_queue_lengths: Sequence[float],
    *,
    arrival_rate: float,
    service_rate: float,
    observation_std: float = 1.0,
    n_particles: int = 256,
    seed: int = 0,
) -> ParticleFilterResult:
    """Bootstrap particle filter for hidden queue length under Poisson flows."""
    observations = np.asarray(observed_queue_lengths, dtype=np.float64)
    if observations.ndim != 1:
        raise ValueError("observed_queue_lengths must be a 1D sequence")
    n_particles = max(int(n_particles), 1)
    observation_std = max(float(observation_std), 1e-9)
    rng = np.random.default_rng(seed)
    particles = np.full(n_particles, max(float(observations[0]) if observations.size else 0.0, 0.0))
    weights = np.full(n_particles, 1.0 / n_particles)
    means: list[float] = []
    stds: list[float] = []
    ess_values: list[float] = []
    log_likelihood = 0.0

    for obs in observations:
        arrivals = rng.poisson(max(float(arrival_rate), 0.0), size=n_particles)
        services = rng.poisson(max(float(service_rate), 0.0), size=n_particles)
        particles = np.maximum(particles + arrivals - np.minimum(services, particles), 0.0)
        residual = obs - particles
        likelihood = np.exp(-0.5 * (residual / observation_std) ** 2)
        likelihood = likelihood / (observation_std * np.sqrt(2.0 * np.pi))
        likelihood = np.maximum(likelihood, 1e-300)
        weights = weights * likelihood
        weight_sum = float(np.sum(weights))
        log_likelihood += float(np.log(weight_sum + 1e-300))
        weights = weights / max(weight_sum, 1e-300)
        mean = float(np.sum(weights * particles))
        variance = float(np.sum(weights * (particles - mean) ** 2))
        ess = 1.0 / max(float(np.sum(weights**2)), 1e-300)
        means.append(mean)
        stds.append(sqrt(max(variance, 0.0)))
        ess_values.append(ess)
        if ess < 0.5 * n_particles:
            indices = rng.choice(n_particles, size=n_particles, replace=True, p=weights)
            particles = particles[indices]
            weights = np.full(n_particles, 1.0 / n_particles)

    return ParticleFilterResult(
        filtered_mean=tuple(means),
        filtered_std=tuple(stds),
        effective_sample_size=tuple(ess_values),
        log_likelihood=log_likelihood,
    )


def paired_monte_carlo_effect(
    baseline_runner: PolicyRunner,
    policy_runner: PolicyRunner,
    *,
    seeds: Sequence[int],
    metric_names: Sequence[str],
) -> PairedMonteCarloResult:
    """Estimate policy effects with common random numbers."""
    if not seeds:
        raise ValueError("seeds must not be empty")
    if not metric_names:
        raise ValueError("metric_names must not be empty")
    diffs: list[dict[str, float]] = []
    for seed in seeds:
        baseline = baseline_runner(int(seed))
        policy = policy_runner(int(seed))
        diffs.append(
            {
                name: float(policy[name]) - float(baseline[name])
                for name in metric_names
                if name in policy and name in baseline
            }
        )
    if any(set(diff) != set(metric_names) for diff in diffs):
        raise ValueError("runner outputs are missing requested metric_names")

    mean_effects: dict[str, float] = {}
    standard_errors: dict[str, float] = {}
    for name in metric_names:
        values = np.asarray([diff[name] for diff in diffs], dtype=np.float64)
        mean_effects[name] = float(np.mean(values))
        if values.size <= 1:
            standard_errors[name] = 0.0
        else:
            standard_errors[name] = float(np.std(values, ddof=1) / sqrt(values.size))
    return PairedMonteCarloResult(
        mean_effects=mean_effects,
        standard_errors=standard_errors,
        paired_differences=tuple(diffs),
        n_replications=len(seeds),
    )


def _average_summaries(summaries: Sequence[Mapping[str, float]]) -> dict[str, float]:
    if not summaries:
        raise ValueError("at least one summary is required")
    names = sorted(set().union(*(summary.keys() for summary in summaries)))
    return {
        name: float(np.mean([float(summary[name]) for summary in summaries if name in summary]))
        for name in names
    }


__all__ = [
    "PairedMonteCarloResult",
    "ParticleFilterResult",
    "QueueMLEEstimate",
    "SMMResult",
    "calibrate_coupled_smm",
    "estimate_queue_mle",
    "extract_coupled_summary",
    "filter_queue_counts",
    "paired_monte_carlo_effect",
    "summary_distance",
]
