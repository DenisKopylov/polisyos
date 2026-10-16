"""Estimation helpers for coupled DES/ABM policy simulations."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from math import sqrt
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

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
    """Best summary-match fit with metric counts and its comparison basis."""

    best_params: dict[str, float] | None
    best_loss: float
    fitted_summary: dict[str, float]
    observed_summary: dict[str, float]
    evaluated: tuple[dict[str, Any], ...]
    comparison_status: Literal["comparable", "no_comparable"]
    status: Literal["ready", "blocked"]
    required_moments: tuple[str, ...] = ()
    fitted_moment_counts: dict[str, int] = field(default_factory=dict)
    fitted_repeat_denominator: int | None = None
    comparison_basis: Literal["required_moments_only"] = "required_moments_only"
    optional_moment_status: Literal["diagnostic_only"] = "diagnostic_only"


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
    standard_errors: dict[str, float | None]
    standard_error_status: dict[str, Literal["estimated", "standard_error_not_estimated"]]
    paired_differences: tuple[dict[str, float], ...]
    n_replications: int


def _observed_series(
    values: npt.ArrayLike,
    *,
    name: str,
) -> np.ndarray | None:
    """Return a finite one-dimensional observation series, or ``None`` if empty.

    Missing samples stay absent. A supplied malformed or non-finite series is
    rejected so it cannot be treated as an empty sample by a downstream reducer.
    """
    try:
        samples = np.asarray(values, dtype=np.float64)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} observations must be numeric") from error
    if samples.ndim != 1:
        raise ValueError(f"{name} observations must be one-dimensional")
    if samples.size == 0:
        return None
    if not np.all(np.isfinite(samples)):
        raise ValueError(f"{name} observations must be finite")
    return samples


def _reduce_observed_series(
    values: npt.ArrayLike,
    *,
    name: str,
    reducer: Callable[[np.ndarray], Any],
) -> float | None:
    """Reduce a complete finite sample series while preserving absence."""
    samples = _observed_series(values, name=name)
    if samples is None:
        return None
    result = float(reducer(samples))
    if not np.isfinite(result):
        raise ValueError(f"{name} reduction must be finite")
    return result


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
        raise ValueError("event_log must not be empty")
    event_times = _observed_series(
        [row[time_key] for row in event_log],
        name="event_log times",
    )
    if event_times is None:
        raise ValueError("event_log must not be empty")
    order = np.argsort(event_times, kind="stable")
    ordered = [event_log[int(index)] for index in order]
    times = event_times[order]
    observation_window = float(times[-1] - times[0])
    if not np.isfinite(observation_window) or observation_window <= 0.0:
        raise ValueError("event_log must span a finite positive observation window")
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
            duration_samples = _observed_series([row["service_duration"]], name="service_duration")
            if duration_samples is None:
                raise ValueError("service_duration must contain a value")
            durations.append(max(float(duration_samples[0]), 0.0))
            continue
        if kind == "service_start" and entity:
            starts_by_entity[entity] = float(row[time_key])
        elif kind in {"service_complete", "eligibility_confirmed"} and entity in starts_by_entity:
            durations.append(max(float(row[time_key]) - starts_by_entity[entity], 0.0))

    arrival_rate = float(n_arrivals / observation_window)
    if durations:
        duration_samples = _observed_series(durations, name="service durations")
        if duration_samples is None:
            raise ValueError("service durations must contain observations")
        mean_duration = max(float(np.mean(duration_samples)), 1e-9)
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
    completed_at = _observed_series(queue.completed_at, name="completed_at")
    queued_at = _observed_series(queue.queued_at, name="queued_at")
    completed_size = 0 if completed_at is None else completed_at.size
    queued_size = 0 if queued_at is None else queued_at.size
    if completed_size != queued_size:
        raise ValueError("completed_at and queued_at observations must have matching sizes")
    waits = np.asarray([], dtype=np.float64)
    if completed_at is not None and queued_at is not None:
        completed_mask = completed_at >= 0.0
        waits = completed_at[completed_mask] - queued_at[completed_mask]

    if any(not isinstance(item, Mapping) for item in metrics):
        raise ValueError("coupled metric observations must be mappings")
    queue_path: list[Any] = []
    queue_path_complete = bool(metrics)
    for item in metrics:
        if "queue/queue_length" in item:
            queue_path.append(item["queue/queue_length"])
        else:
            queue_path_complete = False
    if not queue_path_complete:
        _observed_series(queue_path, name="mean_queue_length")
        queue_path = []

    summary = {
        "final_queue_length": float(np.asarray(queue.queue_length).item()),
        "admitted_count": float(np.asarray(queue.admitted_count).item()),
        "completed_count": float(np.asarray(queue.completed_count).item()),
        "rejected_count": float(np.asarray(queue.rejected_count).item()),
    }
    moment_samples: tuple[tuple[str, npt.ArrayLike, Callable[[np.ndarray], Any]], ...] = (
        ("mean_wait", waits, np.mean),
        ("p90_wait", waits, lambda samples: np.quantile(samples, 0.90)),
        ("mean_queue_length", queue_path, np.mean),
        ("final_mean_savings", state.agents.savings, np.mean),
        ("final_mean_income", state.agents.income, np.mean),
    )
    for name, samples, reducer in moment_samples:
        value = _reduce_observed_series(samples, name=name, reducer=reducer)
        if value is not None:
            summary[name] = value
    return summary


def summary_distance(
    simulated: Mapping[str, float],
    observed: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
    required_moment_names: Sequence[str] | None = None,
) -> float:
    """Weighted squared distance over one declared set of summary moments.

    A candidate that omits a required moment is not comparable to the observed
    summary.  It fails closed instead of receiving a deceptively small loss
    from the moments that happen to overlap.
    """

    required = (
        tuple(observed.keys()) if required_moment_names is None else tuple(required_moment_names)
    )
    if not required:
        raise ValueError("required_moment_names must not be empty")
    if len(set(required)) != len(required):
        raise ValueError("required_moment_names must be unique")
    missing = tuple(name for name in required if name not in simulated or name not in observed)
    if missing:
        raise ValueError(f"required summary moments missing: {', '.join(missing)}")

    total = 0.0
    for name in required:
        observed_value = observed[name]
        weight = 1.0 if weights is None else float(weights.get(name, 1.0))
        if weight < 0.0 or not np.isfinite(weight):
            return float("inf")
        diff = float(simulated[name]) - float(observed_value)
        total += weight * diff * diff
    return float(total)


def calibrate_coupled_smm(
    parameter_grid: Mapping[str, Sequence[float]],
    runner: SummaryRunner,
    observed_summary: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
    seeds: Sequence[int | None] = (None,),
    required_moment_names: Sequence[str] | None = None,
) -> SMMResult:
    """Grid-search SMM over a fixed, explicitly declared moment set.

    Missing required moments make a candidate incomparable and therefore give
    it an infinite loss.  The evaluation record retains per-moment counts and
    missing names so that partial simulations remain visible for diagnosis.
    """

    if not parameter_grid:
        raise ValueError("parameter_grid must not be empty")
    names = tuple(parameter_grid.keys())
    values = tuple(tuple(float(item) for item in parameter_grid[name]) for name in names)
    if any(not value for value in values):
        raise ValueError("each parameter_grid entry must contain at least one value")
    required = (
        tuple(observed_summary.keys())
        if required_moment_names is None
        else tuple(required_moment_names)
    )
    if not required:
        raise ValueError("required_moment_names must not be empty")
    if len(set(required)) != len(required):
        raise ValueError("required_moment_names must be unique")
    if any(name not in observed_summary for name in required):
        missing_observed = tuple(name for name in required if name not in observed_summary)
        raise ValueError(
            "required summary moments missing from observed summary: " + ", ".join(missing_observed)
        )

    evaluated: list[dict[str, Any]] = []
    best_params: dict[str, float] | None = None
    best_summary: dict[str, float] | None = None
    best_moment_counts: dict[str, int] | None = None
    best_repeat_denominator: int | None = None
    best_loss = float("inf")
    for combination in product(*values):
        params = dict(zip(names, combination, strict=True))
        summaries = [runner(params, seed) for seed in seeds]
        averaged = _average_summaries(summaries)
        returned_moment_names = sorted(
            set(required).union(*(summary.keys() for summary in summaries))
        )
        moment_counts = {
            name: sum(1 for summary in summaries if name in summary)
            for name in returned_moment_names
        }
        diagnostic_only_moments = tuple(
            name for name in returned_moment_names if name not in required
        )
        missing_moments = tuple(name for name in required if moment_counts[name] != len(summaries))
        if missing_moments:
            loss = float("inf")
        else:
            loss = summary_distance(
                averaged,
                observed_summary,
                weights=weights,
                required_moment_names=required,
            )
        evaluated.append(
            {
                "params": params,
                "loss": loss,
                "summary": averaged,
                "required_moments": required,
                "moment_counts": moment_counts,
                "repeat_denominator": len(summaries),
                "diagnostic_only_moments": diagnostic_only_moments,
                "optional_moment_status": "diagnostic_only",
                "comparison_basis": "required_moments_only",
                "missing_moments": missing_moments,
            }
        )
        if np.isfinite(loss) and (best_params is None or loss < best_loss):
            best_loss = loss
            best_params = params
            best_summary = averaged
            best_moment_counts = moment_counts
            best_repeat_denominator = len(summaries)

    comparison_status: Literal["comparable", "no_comparable"] = (
        "comparable" if best_params is not None else "no_comparable"
    )
    status: Literal["ready", "blocked"] = "ready" if best_params is not None else "blocked"
    return SMMResult(
        best_params=best_params,
        best_loss=best_loss,
        fitted_summary=best_summary or {},
        observed_summary={key: float(value) for key, value in observed_summary.items()},
        evaluated=tuple(evaluated),
        comparison_status=comparison_status,
        status=status,
        required_moments=required,
        fitted_moment_counts=best_moment_counts or {},
        fitted_repeat_denominator=best_repeat_denominator,
        comparison_basis="required_moments_only",
        optional_moment_status="diagnostic_only",
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
    observations = _observed_series(observed_queue_lengths, name="observed_queue_lengths")
    if observations is None:
        raise ValueError("observed_queue_lengths must not be empty")
    n_particles = max(int(n_particles), 1)
    observation_std = max(float(observation_std), 1e-9)
    rng = np.random.default_rng(seed)
    particles = np.full(n_particles, max(float(observations[0]), 0.0))
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
    normalized_seeds = tuple(int(seed) for seed in seeds)
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("seeds must be unique")
    normalized_metrics = tuple(str(name) for name in metric_names)
    if len(set(normalized_metrics)) != len(normalized_metrics):
        raise ValueError("metric_names must be unique")
    diffs: list[dict[str, float]] = []
    for seed in normalized_seeds:
        baseline = baseline_runner(seed)
        policy = policy_runner(seed)
        diffs.append(
            {
                name: float(policy[name]) - float(baseline[name])
                for name in normalized_metrics
                if name in policy and name in baseline
            }
        )
    if any(set(diff) != set(normalized_metrics) for diff in diffs):
        raise ValueError("runner outputs are missing requested metric_names")

    mean_effects: dict[str, float] = {}
    standard_errors: dict[str, float | None] = {}
    standard_error_status: dict[str, Literal["estimated", "standard_error_not_estimated"]] = {}
    for name in normalized_metrics:
        values = np.asarray([diff[name] for diff in diffs], dtype=np.float64)
        mean_effects[name] = float(np.mean(values))
        if values.size <= 1:
            standard_errors[name] = None
            standard_error_status[name] = "standard_error_not_estimated"
        else:
            standard_errors[name] = float(np.std(values, ddof=1) / sqrt(values.size))
            standard_error_status[name] = "estimated"
    return PairedMonteCarloResult(
        mean_effects=mean_effects,
        standard_errors=standard_errors,
        standard_error_status=standard_error_status,
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
