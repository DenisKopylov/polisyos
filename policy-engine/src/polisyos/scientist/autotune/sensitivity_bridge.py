"""Bridge from autotune search space to DOE sensitivity analysis."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _try_import_doe():
    """Lazy import of DOE analysis module."""
    try:
        import numpy as np

        from polisyos.scientist.doe.analysis import analyze_sensitivity
        from polisyos.scientist.doe.designs import (
            ParameterSpec,
            SensitivityMethod,
            SensitivityPlan,
        )

        return analyze_sensitivity, ParameterSpec, SensitivityMethod, SensitivityPlan, np
    except ImportError:
        return None


class SensitivityBridge:
    """Bridges autotune search space bounds to DOE sensitivity analysis.

    Converts search-space parameter bounds into ``ParameterSpec`` objects
    and calls ``analyze_sensitivity`` to rank parameter importance.
    """

    def analyze_search_space(
        self,
        bounds: list[dict[str, Any]],
        evaluator: Any,
        *,
        method: str = "morris",
        n_trajectories: int = 10,
        n_levels: int = 4,
    ) -> dict[str, Any]:
        """Run sensitivity analysis over a search space.

        Parameters
        ----------
        bounds:
            List of dicts with keys: name, lower, upper.
        evaluator:
            Callable(params_dict) -> float.
        method:
            "morris" or "sobol".
        n_trajectories:
            Number of trajectories / sample sets.
        n_levels:
            Grid levels for Morris method.

        Returns
        -------
        Dict with keys: ranking (list[str]), result (SensitivityResult), method.
        """
        deps = _try_import_doe()
        if deps is None:
            raise ImportError("DOE analysis module not available")

        analyze_sensitivity, ParameterSpec, SensitivityMethod, SensitivityPlan, np = deps

        if not bounds:
            return {"ranking": [], "result": None, "method": method}

        param_specs = [
            ParameterSpec(
                name=b["name"],
                lower_bound=b.get("lower", 0.0),
                upper_bound=b.get("upper", 1.0),
                num_levels=n_levels,
            )
            for b in bounds
        ]

        sa_method = SensitivityMethod.MORRIS if method == "morris" else SensitivityMethod.SOBOL
        plan = SensitivityPlan(
            method=sa_method,
            parameter_specs=param_specs,
            n_trajectories=n_trajectories,
        )

        # Generate samples using SALib
        from SALib.sample import morris as morris_sampler  # type: ignore[import-not-found]
        from SALib.sample import saltelli  # type: ignore[import-not-found]

        problem = {
            "num_vars": len(param_specs),
            "names": [p.name for p in param_specs],
            "bounds": [[p.lower_bound, p.upper_bound] for p in param_specs],
        }

        if sa_method == SensitivityMethod.MORRIS:
            samples = morris_sampler.sample(problem, N=n_trajectories, num_levels=n_levels)
        else:
            samples = saltelli.sample(problem, N=n_trajectories)

        # Evaluate
        outputs = np.array(
            [
                evaluator({p.name: samples[i, j] for j, p in enumerate(param_specs)})
                for i in range(samples.shape[0])
            ]
        )

        result = analyze_sensitivity(plan, samples, outputs)

        # DOE now exposes normalized method-specific maps plus a canonical ranking.
        if result.ranking:
            ranking = list(result.ranking)
        else:
            scores = result.mu_star or result.st or result.s1
            ranking = sorted(
                result.parameter_names,
                key=lambda name: abs(float(scores.get(name, 0.0))),
                reverse=True,
            )

        return {"ranking": ranking, "result": result, "method": method}
