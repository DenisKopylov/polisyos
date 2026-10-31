"""Public doe sampling module API."""

from __future__ import annotations

import itertools

import numpy as np

from .designs import (
    AdversarialPlan,
    AdversarialStrategy,
    SensitivityMethod,
    SensitivityPlan,
    _admit_sensitivity_plan,
    _build_salib_problem,
    _derive_backend_seed,
)
from .morris_geometry import _declared_morris_num_levels


def _sampling_kwargs(plan: SensitivityPlan) -> dict[str, object]:
    """Select every supported sampler option instead of mutable backend defaults."""
    seed = _derive_backend_seed(plan.seed, f"sampling:{plan.method.value}")
    if plan.method == SensitivityMethod.MORRIS:
        return {
            "N": plan.n_trajectories,
            "num_levels": _declared_morris_num_levels(plan),
            "optimal_trajectories": None,
            "local_optimization": True,
            "seed": seed,
        }
    if plan.method == SensitivityMethod.SOBOL:
        return {
            "N": plan.n_trajectories,
            "calc_second_order": True,
            "scramble": True,
            "skip_values": 0,
            "seed": seed,
        }
    return {"N": plan.n_trajectories, "M": 4, "seed": seed}


def generate_sensitivity_samples(plan: SensitivityPlan) -> np.ndarray:
    """Generate parameter samples for the configured sensitivity plan."""
    plan = _admit_sensitivity_plan(plan)
    problem = _plan_to_salib_problem(plan)
    kwargs = _sampling_kwargs(plan)

    if plan.method == SensitivityMethod.MORRIS:
        from SALib.sample import morris as morris_sampler  # type: ignore[import-not-found]

        return morris_sampler.sample(problem, **kwargs)

    if plan.method == SensitivityMethod.SOBOL:
        try:
            from SALib.sample import sobol as sobol_sampler  # type: ignore[import-not-found]
        except ImportError:
            from SALib.sample import saltelli as saltelli_sampler  # type: ignore[import-not-found]

            if plan.seed is not None:
                raise RuntimeError(
                    "Seeded Sobol sampling requires SALib's seed-capable sobol backend"
                )
            return saltelli_sampler.sample(
                problem,
                N=plan.n_trajectories,
                calc_second_order=True,
            )
        return sobol_sampler.sample(problem, **kwargs)

    if plan.method == SensitivityMethod.FAST:
        from SALib.sample import fast_sampler  # type: ignore[import-not-found]

        return fast_sampler.sample(problem, **kwargs)

    raise ValueError(f"Unsupported sensitivity method: {plan.method}")


def generate_adversarial_samples(plan: AdversarialPlan) -> np.ndarray:
    """Generate adversarial parameter settings that stress the configured vulnerability region."""
    n_params = len(plan.parameter_specs)
    bounds = np.array(
        [(item.lower_bound, item.upper_bound) for item in plan.parameter_specs],
        dtype=float,
    )

    if plan.strategy == AdversarialStrategy.GRID_EXTREME:
        corners = itertools.product(*[(lo, hi) for lo, hi in bounds])
        # Cap the iterator before materialization.  Slicing a fully-built
        # NumPy array would still enumerate and retain every corner first.
        return np.array(list(itertools.islice(corners, plan.max_iterations)), dtype=float)

    if plan.strategy == AdversarialStrategy.RANDOM_TAIL:
        rng = np.random.default_rng(plan.seed)
        samples = np.empty((plan.max_iterations, n_params), dtype=float)
        for i, (lo, hi) in enumerate(bounds):
            span = hi - lo
            for j in range(plan.max_iterations):
                if rng.random() < 0.5:
                    samples[j, i] = lo + rng.uniform(0.0, plan.tail_percentile) * span
                else:
                    samples[j, i] = hi - rng.uniform(0.0, plan.tail_percentile) * span
        return samples

    # SEARCH_LOOP -> diverse initial points.
    try:
        from scipy.stats import qmc

        sampler = qmc.LatinHypercube(d=n_params, seed=plan.seed)
        unit = sampler.random(n=min(plan.max_iterations, 32))
        return qmc.scale(unit, bounds[:, 0], bounds[:, 1])
    except Exception:
        rng = np.random.default_rng(plan.seed)
        out = np.empty((min(plan.max_iterations, 32), n_params), dtype=float)
        for idx, (lo, hi) in enumerate(bounds):
            out[:, idx] = rng.uniform(lo, hi, size=out.shape[0])
        return out


def _plan_to_salib_problem(plan: SensitivityPlan) -> dict:
    problem, _ = _build_salib_problem(plan)
    return problem
