"""Public doe analysis module API."""
from __future__ import annotations

import math

import numpy as np

from .designs import RunFailurePolicy, SensitivityMethod, SensitivityPlan, SensitivityResult


def analyze_sensitivity(
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
) -> SensitivityResult:
    """Analyze sensitivity helper."""
    if outputs.ndim != 1:
        raise ValueError("outputs must be a 1D array")
    if samples.ndim != 2:
        raise ValueError("samples must be a 2D array")
    if samples.shape[0] != outputs.shape[0]:
        raise ValueError("samples and outputs must have the same row count")

    raw_outputs = np.asarray(outputs, dtype=float)
    prepared_samples, prepared_outputs, successful, failed = _prepare_analysis_inputs(
        plan,
        np.asarray(samples, dtype=float),
        raw_outputs,
    )

    result = SensitivityResult(
        method=plan.method,
        parameter_names=[item.name for item in plan.parameter_specs],
        total_runs=int(len(outputs)),
        successful_runs=successful,
        failed_runs=failed,
        metadata={
            "run_failure_policy": plan.run_failure_policy.value,
            "estimated_runs": plan.estimated_runs,
            "n_trajectories": plan.n_trajectories,
        },
    )

    problem = _plan_to_salib_problem(plan)
    names = result.parameter_names

    if plan.method == SensitivityMethod.MORRIS:
        from SALib.analyze import morris as morris_analyzer  # type: ignore[import-not-found]

        salib_result = morris_analyzer.analyze(
            problem,
            prepared_samples,
            prepared_outputs,
            conf_level=plan.confidence_level,
            num_levels=plan.parameter_specs[0].num_levels,
        )
        for idx, name in enumerate(names):
            result.mu_star[name] = float(salib_result["mu_star"][idx])
            result.sigma[name] = float(salib_result["sigma"][idx])
            conf = salib_result.get("mu_star_conf")
            if conf is not None:
                result.mu_star_conf[name] = [float(conf[idx])]
        result.ranking = sorted(names, key=lambda item: result.mu_star.get(item, 0.0), reverse=True)
        return result

    if plan.method == SensitivityMethod.SOBOL:
        from SALib.analyze import sobol as sobol_analyzer  # type: ignore[import-not-found]

        salib_result = sobol_analyzer.analyze(
            problem,
            prepared_outputs,
            calc_second_order=True,
            conf_level=plan.confidence_level,
        )
        for idx, name in enumerate(names):
            result.s1[name] = float(salib_result["S1"][idx])
            result.st[name] = float(salib_result["ST"][idx])
            result.s1_conf[name] = [float(salib_result["S1_conf"][idx])]
            result.st_conf[name] = [float(salib_result["ST_conf"][idx])]

        s2_matrix = salib_result.get("S2")
        if s2_matrix is not None:
            interaction_pairs: list[tuple[str, str, float]] = []
            for i, left in enumerate(names):
                interactions: dict[str, float] = {}
                for j, right in enumerate(names):
                    if i == j:
                        continue
                    value = float(s2_matrix[i][j])
                    if math.isnan(value):
                        continue
                    interactions[right] = value
                    if i < j:
                        interaction_pairs.append((left, right, value))
                if interactions:
                    result.s2[left] = interactions
            # Sort by absolute S2 value descending
            interaction_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            result.top_interactions = interaction_pairs
        result.ranking = sorted(names, key=lambda item: result.st.get(item, 0.0), reverse=True)
        return result

    if plan.method == SensitivityMethod.FAST:
        from SALib.analyze import fast as fast_analyzer  # type: ignore[import-not-found]

        salib_result = fast_analyzer.analyze(problem, prepared_outputs)
        for idx, name in enumerate(names):
            result.s1[name] = float(salib_result["S1"][idx])
            result.st[name] = float(salib_result["ST"][idx])
        result.ranking = sorted(names, key=lambda item: result.st.get(item, 0.0), reverse=True)
        return result

    raise ValueError(f"Unsupported sensitivity method: {plan.method}")


def _prepare_analysis_inputs(
    plan: SensitivityPlan,
    samples: np.ndarray,
    outputs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    valid_mask = np.isfinite(outputs)
    success_count = int(np.sum(valid_mask))
    failed_count = int(outputs.shape[0] - success_count)
    min_success = int(math.ceil(outputs.shape[0] * plan.min_success_rate))

    if success_count < min_success:
        raise ValueError(
            "Sensitivity analysis aborted: successful runs below min_success_rate "
            f"({success_count}/{outputs.shape[0]} < {min_success})."
        )

    if failed_count == 0:
        return samples, outputs, success_count, failed_count

    if plan.run_failure_policy == RunFailurePolicy.FAIL_FAST:
        raise ValueError(
            "Sensitivity analysis aborted: failed simulation runs detected "
            f"({failed_count}/{outputs.shape[0]})."
        )

    if plan.run_failure_policy == RunFailurePolicy.DROP_FAILED:
        if plan.method not in (SensitivityMethod.MORRIS, SensitivityMethod.SOBOL):
            raise ValueError(
                "DROP_FAILED is only supported for MORRIS and SOBOL; use IMPUTE_BASELINE for FAST."
            )
        return samples[valid_mask], outputs[valid_mask], success_count, failed_count

    # IMPUTE_BASELINE
    if success_count == 0:
        imputed = np.zeros_like(outputs)
    else:
        baseline = float(np.nanmedian(outputs[valid_mask]))
        imputed = outputs.copy()
        imputed[~valid_mask] = baseline
    return samples, imputed, success_count, failed_count


def _plan_to_salib_problem(plan: SensitivityPlan) -> dict:
    from .designs import ParameterDist

    problem: dict = {
        "num_vars": len(plan.parameter_specs),
        "names": [item.name for item in plan.parameter_specs],
        "bounds": [[item.lower_bound, item.upper_bound] for item in plan.parameter_specs],
    }
    # Add distribution hints for SALib when non-uniform distributions are used
    has_non_uniform = any(
        p.distribution != ParameterDist.UNIFORM for p in plan.parameter_specs
    )
    if has_non_uniform:
        dists: list[str] = []
        for p in plan.parameter_specs:
            if p.distribution == ParameterDist.NORMAL:
                dists.append("norm")
            elif p.distribution == ParameterDist.LOGNORMAL:
                dists.append("lognorm")
            elif p.distribution == ParameterDist.TRIANGULAR:
                dists.append("triang")
            else:
                dists.append("unif")
        problem["dists"] = dists
    return problem

