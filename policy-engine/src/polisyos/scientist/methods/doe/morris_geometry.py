"""Validate ungrouped Morris trajectories in their admitted sampling coordinates."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np

if TYPE_CHECKING:
    from .designs import SensitivityPlan


def _validate_morris_plan_samples(
    plan: SensitivityPlan,
    samples: np.ndarray,
    problem: dict[str, object] | None = None,
) -> None:
    """Admit a plan's complete design before consumers may resample its blocks."""
    from .designs import _build_salib_problem

    if samples.ndim != 2 or samples.shape[1] != plan.num_parameters:
        raise ValueError("Morris samples must have one column per declared parameter")
    num_levels = plan.parameter_specs[0].num_levels
    if any(spec.num_levels != num_levels for spec in plan.parameter_specs):
        raise ValueError("Morris parameters must declare the same num_levels")
    if problem is None:
        problem, _ = _build_salib_problem(plan)
    _validate_morris_trajectories(
        samples,
        num_parameters=plan.num_parameters,
        num_levels=num_levels,
        unit_samples=_morris_unit_samples(samples, problem),
    )


def _morris_unit_samples(samples: np.ndarray, problem: dict[str, object]) -> np.ndarray:
    """Invert the canonical bounded SALib mapping without guessing a source law."""
    bounds = cast("list[list[float]]", problem["bounds"])
    distributions = cast("list[str]", problem.get("dists", ["unif"] * samples.shape[1]))
    unit = np.empty_like(samples, dtype=float)
    for column, (distribution, parameters) in enumerate(zip(distributions, bounds, strict=True)):
        lower, upper = parameters[:2]
        values = samples[:, column]
        if np.any((values < lower) | (values > upper)):
            raise ValueError("Morris samples exceed the declared physical support")
        if distribution == "unif":
            unit[:, column] = (values - lower) / (upper - lower)
        elif distribution == "truncnorm":
            from scipy.stats import truncnorm

            mean, std = parameters[2:]
            unit[:, column] = truncnorm.cdf(
                values, (lower - mean) / std, (upper - mean) / std, loc=mean, scale=std
            )
        elif distribution == "triang":
            from scipy.stats import triang

            unit[:, column] = triang.cdf(values, c=parameters[2], loc=lower, scale=upper - lower)
        else:
            raise ValueError(f"Morris coordinate mapping is not established for {distribution}")
    return unit


def _validate_morris_trajectories(
    samples: np.ndarray,
    *,
    num_parameters: int,
    num_levels: int,
    unit_samples: np.ndarray,
) -> None:
    """Require whole one-factor-at-a-time paths on the declared SALib grid.

    Grid and step tolerances apply in unit coordinates, so changing physical
    units cannot relax this invariant.  The allowed grid includes SALib's
    starting points and their delta offsets, including its odd-level design.
    This validates geometry, not authenticated trajectory provenance.
    """
    if (
        num_parameters < 1
        or samples.ndim != 2
        or samples.shape[1] != num_parameters
        or samples.shape[0] == 0
        or samples.shape[0] % (num_parameters + 1)
        or unit_samples.shape != samples.shape
    ):
        raise ValueError("Morris samples must contain complete trajectory blocks")
    if not np.all(np.isfinite(samples)) or not np.all(np.isfinite(unit_samples)):
        raise ValueError("Morris trajectory coordinates must be finite")
    if num_levels < 2:
        raise ValueError("Morris num_levels must be at least two")

    tolerance = 1e-8
    delta = num_levels / (2.0 * (num_levels - 1))
    n_starts = num_levels // 2
    if n_starts == 1:
        grid_distance = np.minimum(np.abs(unit_samples), np.abs(unit_samples - delta))
    else:
        # Find the nearest point on either of SALib's two uniform lattices.
        # Avoid a rows x parameters x num_levels distance tensor.
        spacing = (1.0 - delta) / (n_starts - 1)
        lower_index = np.clip(np.rint(unit_samples / spacing), 0, n_starts - 1)
        upper_index = np.clip(np.rint((unit_samples - delta) / spacing), 0, n_starts - 1)
        grid_distance = np.minimum(
            np.abs(unit_samples - lower_index * spacing),
            np.abs(unit_samples - delta - upper_index * spacing),
        )
    if np.any(grid_distance > tolerance):
        raise ValueError("Morris coordinates do not lie on the declared sampling grid")

    trajectories = unit_samples.reshape(-1, num_parameters + 1, num_parameters)
    steps = np.diff(trajectories, axis=1)
    # SALib uses the sign of every physical coordinate difference to select
    # outputs. Even a tiny second change must fail rather than enter its point
    # estimate while being ignored by our uncertainty calculation.
    physical_paths = samples.reshape(-1, num_parameters + 1, num_parameters)
    changed = np.diff(physical_paths, axis=1) != 0.0
    if np.any(np.sum(changed, axis=2) != 1):
        raise ValueError("Morris trajectory steps must change exactly one coordinate")
    if np.any(np.sum(changed, axis=1) != 1):
        raise ValueError("Morris trajectories must change each coordinate exactly once")
    if not np.all(np.isclose(np.abs(steps[changed]), delta, rtol=0.0, atol=tolerance)):
        raise ValueError("Morris trajectory step differs from the declared grid delta")
