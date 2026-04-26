"""Basin-estimation helpers for feedback fixed-point multiplicity reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from polisyos.core.contracts.foundry import BasinEstimate, EquilibriumBasinInterval

from .diagnostics import scaled_inf_norm

if TYPE_CHECKING:
    from .config import PreparedFeedbackConfig


@dataclass(frozen=True)
class BasinCluster:
    """Minimal cluster view required for basin assignment."""

    equilibrium_id: str
    solution: np.ndarray


@dataclass(frozen=True)
class BasinAssignment:
    """One basin draw assignment."""

    start: np.ndarray
    equilibrium_id: str | None
    status: str
    residual_norm: float | None = None


def finite_start_bounds(prepared: PreparedFeedbackConfig) -> tuple[np.ndarray, np.ndarray]:
    """Return finite sampling bounds for all feedback variables."""

    lower = prepared.lower_bounds.astype(float).copy()
    upper = prepared.upper_bounds.astype(float).copy()
    center = prepared.initial_values.astype(float)
    width = np.maximum(prepared.scales.astype(float), 1.0)
    for index in range(len(center)):
        if not np.isfinite(lower[index]) and not np.isfinite(upper[index]):
            lower[index] = center[index] - width[index]
            upper[index] = center[index] + width[index]
        elif not np.isfinite(lower[index]):
            lower[index] = min(center[index] - width[index], upper[index] - 2.0 * width[index])
        elif not np.isfinite(upper[index]):
            upper[index] = max(center[index] + width[index], lower[index] + 2.0 * width[index])
        if lower[index] >= upper[index]:
            spread = max(width[index], 1.0e-6)
            lower[index] = center[index] - spread
            upper[index] = center[index] + spread
    return lower, upper


def latin_hypercube_starts(
    prepared: PreparedFeedbackConfig,
    count: int,
    *,
    seed: int,
) -> list[np.ndarray]:
    """Generate deterministic Latin-hypercube starts over the feedback domain."""

    if count <= 0:
        return []
    rng = np.random.default_rng(seed)
    lower, upper = finite_start_bounds(prepared)
    dim = len(prepared.variable_ids)
    samples = np.zeros((count, dim), dtype=float)
    for index in range(dim):
        perm = rng.permutation(count)
        jitter = rng.random(count)
        unit = (perm + jitter) / float(count)
        samples[:, index] = lower[index] + unit * (upper[index] - lower[index])
    return [np.minimum(np.maximum(sample, prepared.lower_bounds), prepared.upper_bounds) for sample in samples]


def assign_cluster(
    *,
    prepared: PreparedFeedbackConfig,
    solution: np.ndarray,
    clusters: list[BasinCluster],
    merge_tol: float,
) -> BasinCluster | None:
    """Assign a solved point to the nearest known equilibrium cluster."""

    distances = [
        (
            scaled_inf_norm(np.asarray(solution, dtype=float) - cluster.solution, prepared=prepared),
            cluster,
        )
        for cluster in clusters
    ]
    if not distances:
        return None
    distance, cluster = min(distances, key=lambda item: item[0])
    if distance <= merge_tol:
        return cluster
    return None


def estimate_basin_shares(
    *,
    prepared: PreparedFeedbackConfig,
    clusters: list[BasinCluster],
    starts: list[np.ndarray],
    solve_start: Callable[[np.ndarray], tuple[bool, str, np.ndarray, float | None]],
) -> tuple[list[BasinEstimate], dict[str, int], list[BasinAssignment]]:
    """Estimate basin shares from a declared start distribution."""

    hits = {cluster.equilibrium_id: 0 for cluster in clusters}
    assignments: list[BasinAssignment] = []
    for start in starts:
        converged, status, solution, residual_norm = solve_start(start)
        if not converged:
            assignments.append(
                BasinAssignment(
                    start=np.asarray(start, dtype=float),
                    equilibrium_id=None,
                    status=status,
                    residual_norm=residual_norm,
                )
            )
            continue
        assigned = assign_cluster(
            prepared=prepared,
            solution=solution,
            clusters=clusters,
            merge_tol=prepared.config.solver.fixed_point_merge_tol,
        )
        if assigned is None:
            assignments.append(
                BasinAssignment(
                    start=np.asarray(start, dtype=float),
                    equilibrium_id=None,
                    status="unassigned",
                    residual_norm=residual_norm,
                )
            )
            continue
        hits[assigned.equilibrium_id] += 1
        assignments.append(
            BasinAssignment(
                start=np.asarray(start, dtype=float),
                equilibrium_id=assigned.equilibrium_id,
                status="assigned",
                residual_norm=residual_norm,
            )
        )

    draws = len(starts)
    estimates = [
        BasinEstimate(
            equilibrium_id=cluster.equilibrium_id,
            draws=draws,
            hits=hits[cluster.equilibrium_id],
            share_hat=hits[cluster.equilibrium_id] / draws if draws else None,
            ci_95=wilson_interval(hits[cluster.equilibrium_id], draws) if draws else None,
        )
        for cluster in clusters
    ]
    return estimates, hits, assignments


def wilson_interval(hits: int, draws: int) -> EquilibriumBasinInterval:
    """Compute a 95 percent Wilson interval for a binomial basin share."""

    if draws <= 0:
        return EquilibriumBasinInterval(lower=0.0, upper=1.0)
    z = 1.959963984540054
    p_hat = hits / draws
    denom = 1.0 + (z * z) / draws
    center = (p_hat + (z * z) / (2.0 * draws)) / denom
    half = (
        z
        * np.sqrt((p_hat * (1.0 - p_hat) + (z * z) / (4.0 * draws)) / draws)
        / denom
    )
    return EquilibriumBasinInterval(
        lower=max(0.0, float(center - half)),
        upper=min(1.0, float(center + half)),
    )
