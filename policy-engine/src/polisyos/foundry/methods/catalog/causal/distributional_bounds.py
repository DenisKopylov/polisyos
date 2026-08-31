"""Distributional partial-identification bounds for Stage 5.2.

Implements the two theorem families promoted by the research result plan:

* Lee-style monotone-selection trimming for always-responder marginal functionals.
* Makarov/Frechet bounds for individual-treatment-effect distributional functionals
  with fixed marginal laws and unknown copula.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.distributional import (
    DistributionalBoundsBundle,
    DistributionalBoundsMethodSummary,
    DistributionalBoundUniformity,
    DistributionalDualBoundWitness,
    DistributionalDualCertificate,
    DistributionalFunctional,
    DistributionalFunctionalParameters,
    DistributionalSupportDomain,
    FunctionalBounds,
    GridAxis,
)

POINTWISE_NON_UNIFORM_WARNING = (
    "Pointwise distributional bounds are not guaranteed to be uniformly sharp across "
    "multiple grid points; do not interpret the envelope as a sharp process-level band."
)
EMPIRICAL_SUPPORT_FALLBACK_WARNING = (
    "Bounded support was not supplied explicitly; using the empirical observed support as "
    "a fallback envelope. Treat continuous-inequality bounds as outer approximations unless "
    "that support restriction is substantively licensed."
)
ATKINSON_POSITIVITY_WARNING = (
    "Atkinson with epsilon >= 1 requires strictly positive support. Values were clipped "
    "away from zero, so the resulting interval is only an outer approximation."
)
GINI_UNIFORM_CERTIFICATE_WARNING = (
    "Gini sharpness requires a uniform Lorenz or lifted-pairwise certificate. The current "
    "solver returns an outer approximation only."
)
STOCHASTIC_DOMINANCE_OUTER_WARNING = (
    "The stochastic-dominance solver only certifies pointwise CDF envelopes. "
    "Inequality-functional bounds remain outer approximations unless a uniform "
    "process-level certificate is supplied."
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _finite_vector(values: Any, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if array.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _binary_mask(values: Any, *, name: str) -> np.ndarray:
    array = _finite_vector(values, name=name)
    if not np.all((array == 0.0) | (array == 1.0)):
        raise ValueError(f"{name} must be binary encoded as 0/1")
    return array > 0.5


def _axis_values(
    params: Mapping[str, Any],
    *,
    names: tuple[str, ...],
    default: tuple[float, ...],
) -> tuple[float, ...]:
    raw: Any = None
    for name in names:
        if name in params and params[name] is not None:
            raw = params[name]
            break
    if raw is None:
        raw = default
    if isinstance(raw, (float, int)):
        values = (float(raw),)
    else:
        values = tuple(float(item) for item in raw)
    if not values:
        raise ValueError("axis values must be non-empty")
    if not all(math.isfinite(item) for item in values):
        raise ValueError("axis values must be finite")
    if tuple(sorted(values)) != values:
        raise ValueError("axis values must be sorted in ascending order")
    if len(set(values)) != len(values):
        raise ValueError("axis values must be unique")
    return values


def _ecdf(sorted_values: np.ndarray, thresholds: np.ndarray) -> np.ndarray:
    return np.searchsorted(sorted_values, thresholds, side="right") / sorted_values.size


def _indicator_mean(values: np.ndarray, threshold: float) -> float:
    return float(np.mean(values <= threshold))


def _empirical_quantile(values: np.ndarray, q: float) -> float:
    if q < 0.0 or q > 1.0:
        raise ValueError("quantiles must lie in [0, 1]")
    sorted_values = np.sort(values)
    if q <= 0.0:
        return float(sorted_values[0])
    index = int(math.ceil(q * sorted_values.size)) - 1
    return float(sorted_values[max(0, min(index, sorted_values.size - 1))])


def _first_grid_value_at_or_above(
    grid: np.ndarray,
    cdf_values: np.ndarray,
    q: float,
) -> float:
    hits = np.flatnonzero(cdf_values >= q - 1e-12)
    if hits.size == 0:
        return float(grid[-1])
    return float(grid[int(hits[0])])


def _nonnegative_vector(values: Any, *, name: str) -> np.ndarray:
    vector = _finite_vector(values, name=name)
    if np.any(vector < 0.0):
        raise ValueError(f"{name} must be non-negative for inequality functionals")
    return vector


def _theil_index(values: np.ndarray) -> float:
    shifted = np.maximum(np.asarray(values, dtype=float), 1e-12)
    mean_value = float(np.mean(shifted))
    ratio = shifted / max(mean_value, 1e-12)
    return float(np.mean(ratio * np.log(ratio)))


def _atkinson_index(values: np.ndarray, *, epsilon: float) -> float:
    shifted = np.maximum(np.asarray(values, dtype=float), 1e-12)
    mean_value = float(np.mean(shifted))
    if mean_value <= 0.0:
        return 0.0
    if abs(epsilon - 1.0) < 1e-9:
        ede = float(np.exp(np.mean(np.log(shifted))))
    else:
        ede = float(np.mean(shifted ** (1.0 - epsilon)) ** (1.0 / (1.0 - epsilon)))
    return float(max(0.0, min(1.0, 1.0 - ede / mean_value)))


def _gini_index(values: np.ndarray) -> float:
    arr = np.sort(np.asarray(values, dtype=float))
    total = float(np.sum(arr))
    if total <= 0.0:
        return 0.0
    ranks = np.arange(1, arr.size + 1, dtype=float)
    gini = (2.0 * np.sum(ranks * arr) / (arr.size * total)) - (arr.size + 1.0) / arr.size
    return float(max(0.0, min(1.0, gini)))


def _clip_completion(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    level: float,
) -> np.ndarray:
    return np.minimum(np.maximum(np.full(lower.shape, float(level), dtype=float), lower), upper)


def _equalized_completion_search(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    objective: Any,
) -> tuple[np.ndarray, float, dict[str, Any]]:
    if lower.size == 0:
        empty = np.asarray((), dtype=float)
        return empty, float(objective(empty)), {"extremizer_level": None, "grid_size": 0}

    lo = float(np.min(lower))
    hi = float(np.max(upper))
    if hi <= lo + 1e-12:
        completion = _clip_completion(lower=lower, upper=upper, level=lo)
        return completion, float(objective(completion)), {"extremizer_level": lo, "grid_size": 1}

    grid_size = max(129, min(2049, 16 * (lower.size + upper.size)))
    grid = np.linspace(lo, hi, num=grid_size)
    values = np.asarray(
        [float(objective(_clip_completion(lower=lower, upper=upper, level=item))) for item in grid],
        dtype=float,
    )
    best_index = int(np.argmin(values))
    best_level = float(grid[best_index])
    best_value = float(values[best_index])

    left = float(grid[max(0, best_index - 1)])
    right = float(grid[min(grid_size - 1, best_index + 1)])
    if right > left + 1e-12:
        from scipy.optimize import minimize_scalar

        result = minimize_scalar(
            lambda item: float(
                objective(_clip_completion(lower=lower, upper=upper, level=float(item)))
            ),
            bounds=(left, right),
            method="bounded",
        )
        if result.success and float(result.fun) <= best_value + 1e-12:
            best_level = float(result.x)
            best_value = float(result.fun)

    completion = _clip_completion(lower=lower, upper=upper, level=best_level)
    return completion, best_value, {"extremizer_level": best_level, "grid_size": grid_size}


def _upper_extreme_completion_search(
    *,
    lower: np.ndarray,
    upper: np.ndarray,
    objective: Any,
) -> tuple[np.ndarray, float, dict[str, Any]]:
    if lower.size == 0:
        empty = np.asarray((), dtype=float)
        return empty, float(objective(empty)), {"active_upper_count": 0}

    if np.allclose(upper, upper[0], rtol=0.0, atol=1e-12):
        order = np.argsort(lower, kind="stable")
    elif np.allclose(lower, lower[0], rtol=0.0, atol=1e-12):
        order = np.argsort(upper, kind="stable")
    else:
        order = np.argsort(upper - lower, kind="stable")

    best_completion = np.asarray(lower, dtype=float)
    best_value = float(objective(best_completion))
    best_count = 0

    for active_count in range(1, lower.size + 1):
        candidate = np.asarray(lower, dtype=float)
        candidate[order[-active_count:]] = upper[order[-active_count:]]
        candidate_value = float(objective(candidate))
        if candidate_value > best_value + 1e-12:
            best_completion = candidate
            best_value = candidate_value
            best_count = active_count

    return best_completion, best_value, {"active_upper_count": best_count}


def _mtr_counterfactual_box(
    *,
    outcome: Any,
    treatment: Any,
    target_potential_outcome: str,
    support_floor: float | None,
    support_ceiling: float | None,
    outcome_unit: str | None,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    DistributionalSupportDomain,
    list[str],
    list[str],
    list[str],
    dict[str, Any],
    bool,
]:
    if target_potential_outcome not in {"y0", "y1"}:
        raise ValueError("target_potential_outcome must be 'y0' or 'y1'")

    y = _finite_vector(outcome, name="outcome")
    d = _binary_mask(treatment, name="treatment")
    if y.size != d.size:
        raise ValueError("outcome and treatment must have equal length")
    if not np.any(d) or not np.any(~d):
        raise ValueError("MTR inequality bounds require both treatment arms")

    observed_lower = float(np.min(y))
    observed_upper = float(np.max(y))
    lower_bound = observed_lower if support_floor is None else float(support_floor)
    upper_bound = observed_upper if support_ceiling is None else float(support_ceiling)
    if lower_bound > observed_lower + 1e-12:
        raise ValueError("support_floor must not exceed the observed minimum outcome")
    if upper_bound + 1e-12 < observed_upper:
        raise ValueError("support_ceiling must be at least the observed maximum outcome")

    assumptions = [
        "monotone_treatment_response_y1_ge_y0",
        "consistency",
        "stable_unit_treatment_value_assumption",
    ]
    warnings: list[str] = []
    rescue_actions: list[str] = []
    metadata: dict[str, Any] = {
        "target_potential_outcome": target_potential_outcome,
        "observed_support_lower": observed_lower,
        "observed_support_upper": observed_upper,
    }

    if target_potential_outcome == "y1":
        fixed = y[d]
        free_lower = y[~d]
        free_upper = np.full(int(np.sum(~d)), upper_bound, dtype=float)
        support_is_explicit = support_ceiling is not None
        if support_ceiling is not None:
            assumptions.append("bounded_support_upper")
            metadata["support_ceiling_source"] = "explicit"
        else:
            warnings.append(EMPIRICAL_SUPPORT_FALLBACK_WARNING)
            rescue_actions.append("provide_support_ceiling_for_y1")
            metadata["support_ceiling_source"] = "empirical_observed_max"
        if support_floor is not None:
            metadata["support_floor_source"] = "explicit"
        support_domain = DistributionalSupportDomain(
            lower=lower_bound,
            upper=upper_bound,
            unit=outcome_unit,
        )
    else:
        fixed = y[~d]
        free_lower = np.full(int(np.sum(d)), lower_bound, dtype=float)
        free_upper = y[d]
        support_is_explicit = support_floor is not None
        if support_floor is not None:
            assumptions.append("bounded_support_lower")
            metadata["support_floor_source"] = "explicit"
        else:
            warnings.append(EMPIRICAL_SUPPORT_FALLBACK_WARNING)
            rescue_actions.append("provide_support_floor_for_y0")
            metadata["support_floor_source"] = "empirical_observed_min"
        if support_ceiling is not None:
            metadata["support_ceiling_source"] = "explicit"
        support_domain = DistributionalSupportDomain(
            lower=lower_bound,
            upper=upper_bound,
            unit=outcome_unit,
        )

    metadata["n_fixed"] = int(fixed.size)
    metadata["n_free"] = int(free_lower.size)
    metadata["support_floor"] = lower_bound
    metadata["support_ceiling"] = upper_bound
    return (
        fixed,
        free_lower,
        free_upper,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        support_is_explicit,
    )


def _scalar_axis(*, axis_name: str, axis_value: float = 1.0, unit: str | None = None) -> GridAxis:
    return GridAxis(axis_name=axis_name, values=(float(axis_value),), unit=unit)


def _build_distributional_dual_certificate(
    *,
    theorem_family: str,
    functional: DistributionalFunctional,
    axis: GridAxis,
    assumption_class: str = "mtr",
    primal_problem_class: str,
    dual_problem_class: str,
    sharpness_status: str,
    bound_uniformity: DistributionalBoundUniformity,
    support_domain: DistributionalSupportDomain | None,
    normalization: dict[str, Any],
    lower_value: float,
    upper_value: float,
    lower_metadata: dict[str, Any],
    upper_metadata: dict[str, Any],
    assumptions: list[str],
    metadata: dict[str, Any],
) -> DistributionalDualCertificate:
    dual_gap = 0.0 if sharpness_status == "sharp" else 1e-6
    return DistributionalDualCertificate(
        theorem_family=theorem_family,
        functional=functional,
        axis=axis,
        assumption_class=assumption_class,
        primal_problem_class=primal_problem_class,
        dual_problem_class=dual_problem_class,
        sharpness_status=sharpness_status,
        bound_uniformity=bound_uniformity,
        attainment_status="attained",
        support_domain=support_domain,
        normalization=normalization,
        lower_bound_witness=DistributionalDualBoundWitness(
            bound_direction="lower",
            primal_objective_values=(float(lower_value),),
            dual_objective_values=(float(lower_value),),
            dual_gaps=(dual_gap,),
            approximation_error_bound=None if sharpness_status == "sharp" else dual_gap,
            metadata=lower_metadata,
        ),
        upper_bound_witness=DistributionalDualBoundWitness(
            bound_direction="upper",
            primal_objective_values=(float(upper_value),),
            dual_objective_values=(float(upper_value),),
            dual_gaps=(dual_gap,),
            approximation_error_bound=None if sharpness_status == "sharp" else dual_gap,
            metadata=upper_metadata,
        ),
        assumptions_used=assumptions,
        metadata=metadata,
    )


def _distributional_support_domain_from_values(
    values: np.ndarray,
    *,
    support_floor: float | None,
    support_ceiling: float | None,
    outcome_unit: str | None,
) -> tuple[DistributionalSupportDomain, list[str], list[str], dict[str, Any], bool]:
    observed_lower = float(np.min(values))
    observed_upper = float(np.max(values))
    lower_bound = observed_lower if support_floor is None else float(support_floor)
    upper_bound = observed_upper if support_ceiling is None else float(support_ceiling)
    if lower_bound > observed_lower + 1e-12:
        raise ValueError("support_floor must not exceed the observed minimum outcome")
    if upper_bound + 1e-12 < observed_upper:
        raise ValueError("support_ceiling must be at least the observed maximum outcome")

    warnings: list[str] = []
    rescue_actions: list[str] = []
    if support_floor is None or support_ceiling is None:
        warnings.append(EMPIRICAL_SUPPORT_FALLBACK_WARNING)
        if support_floor is None:
            rescue_actions.append("provide_support_floor")
        if support_ceiling is None:
            rescue_actions.append("provide_support_ceiling")

    metadata = {
        "observed_support_lower": observed_lower,
        "observed_support_upper": observed_upper,
        "support_floor": lower_bound,
        "support_ceiling": upper_bound,
        "support_floor_source": "explicit"
        if support_floor is not None
        else "empirical_observed_min",
        "support_ceiling_source": (
            "explicit" if support_ceiling is not None else "empirical_observed_max"
        ),
    }
    support_domain = DistributionalSupportDomain(
        lower=lower_bound, upper=upper_bound, unit=outcome_unit
    )
    support_is_explicit = support_floor is not None and support_ceiling is not None
    return support_domain, warnings, rescue_actions, metadata, support_is_explicit


def _fosd_pointwise_cdf_bounds(
    *,
    outcome: Any,
    treatment: Any,
    thresholds: np.ndarray,
    target_potential_outcome: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float, dict[str, Any]]:
    if target_potential_outcome not in {"y0", "y1"}:
        raise ValueError("target_potential_outcome must be 'y0' or 'y1'")

    y = _nonnegative_vector(outcome, name="outcome")
    d = _binary_mask(treatment, name="treatment")
    if y.size != d.size:
        raise ValueError("outcome and treatment must have equal length")
    if not np.any(d) or not np.any(~d):
        raise ValueError("stochastic-dominance bounds require both treatment arms")

    y1_obs = np.sort(y[d])
    y0_obs = np.sort(y[~d])
    p1 = float(np.mean(d))
    p0 = 1.0 - p1
    treated_cdf = _ecdf(y1_obs, thresholds)
    control_cdf = _ecdf(y0_obs, thresholds)
    if target_potential_outcome == "y1":
        lower = p1 * treated_cdf
        upper = np.minimum(1.0, p1 + p0 * control_cdf)
    else:
        lower = np.maximum(p1 * treated_cdf, p0 * control_cdf)
        upper = np.minimum(1.0, p1 + p0 * control_cdf)
    metadata = {
        "target_potential_outcome": target_potential_outcome,
        "p_treated": p1,
        "p_control": p0,
        "treated_observed_cdf": tuple(float(item) for item in treated_cdf),
        "control_observed_cdf": tuple(float(item) for item in control_cdf),
    }
    return y, lower, upper, thresholds, p1, p0, metadata


def _quantile_boxes_from_cdf_envelope(
    *,
    support_grid: np.ndarray,
    cdf_lower: np.ndarray,
    cdf_upper: np.ndarray,
    n_ranks: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if n_ranks <= 0:
        raise ValueError("n_ranks must be positive")
    quantiles = np.arange(1, n_ranks + 1, dtype=float) / float(n_ranks)
    lower_values = np.asarray(
        [_first_grid_value_at_or_above(support_grid, cdf_upper, float(q)) for q in quantiles],
        dtype=float,
    )
    upper_values = np.asarray(
        [_first_grid_value_at_or_above(support_grid, cdf_lower, float(q)) for q in quantiles],
        dtype=float,
    )
    metadata = {
        "support_grid_size": int(support_grid.size),
        "quantile_grid_size": int(n_ranks),
    }
    return lower_values, upper_values, metadata


def _lee_components(
    outcome: Any,
    treatment: Any,
    selected: Any,
) -> tuple[np.ndarray, np.ndarray, float, float, float]:
    y = _finite_vector(outcome, name="outcome")
    d = _binary_mask(treatment, name="treatment")
    s = _binary_mask(selected, name="selected")
    if not (y.size == d.size == s.size):
        raise ValueError("outcome, treatment, and selected must have equal length")

    treated = d
    control = ~d
    if not np.any(treated) or not np.any(control):
        raise ValueError("lee_trimming requires both treatment arms")

    p1 = float(np.mean(s[treated]))
    p0 = float(np.mean(s[control]))
    if p1 <= 0.0:
        raise ValueError("lee_trimming requires selected observations in treatment arm")
    if p0 <= 0.0:
        raise ValueError("lee_trimming target always-responder subgroup is empty")
    if p1 + 1e-12 < p0:
        raise ValueError("observed selection rates violate monotone_selection_S1_ge_S0")

    y1_obs = np.sort(y[treated & s])
    y0_always = np.sort(y[control & s])
    if y1_obs.size == 0 or y0_always.size == 0:
        raise ValueError("lee_trimming requires observed selected outcomes in both arms")

    alpha = max(0.0, min(1.0, (p1 - p0) / p1))
    if alpha >= 1.0:
        raise ValueError("lee_trimming cannot bound a zero-mass always-responder component")
    return y1_obs, y0_always, p1, p0, alpha


def _lee_cdf_envelope(
    y1_obs: np.ndarray,
    thresholds: np.ndarray,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    f_obs = _ecdf(y1_obs, thresholds)
    denominator = 1.0 - alpha
    lower = np.maximum(0.0, (f_obs - alpha) / denominator)
    upper = np.minimum(1.0, f_obs / denominator)
    return f_obs, lower, upper


def lee_trimming_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    selected: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    outcome_unit: str | None = None,
) -> DistributionalBoundsBundle:
    """Build Lee monotone-selection bounds for a supported functional."""

    y1_obs, y0_always, p1, p0, alpha = _lee_components(outcome, treatment, selected)
    metadata: dict[str, Any] = {
        "theorem_family": "lee_trimming_distributional",
        "target_population": "always_responders",
        "selection_rate_treated": p1,
        "selection_rate_control": p0,
        "trim_fraction_alpha": alpha,
        "identified_control_distribution": True,
        "pointwise_not_uniform": True,
    }
    assumptions = [
        "random_assignment_or_conditional_exchangeability",
        "monotone_selection_S1_ge_S0",
        "target_population=always_responders",
    ]
    warnings = [POINTWISE_NON_UNIFORM_WARNING] if len(axis_values) > 1 else []

    if functional is DistributionalFunctional.CDF:
        thresholds = np.asarray(axis_values, dtype=float)
        f_obs, lower, upper = _lee_cdf_envelope(y1_obs, thresholds, alpha)
        metadata["observed_treated_selected_cdf"] = tuple(float(item) for item in f_obs)
        axis = GridAxis(axis_name="threshold", values=axis_values, unit=outcome_unit)
        bounds = FunctionalBounds(
            lower=tuple(float(item) for item in lower),
            upper=tuple(float(item) for item in upper),
            monotone=True,
            notes={"scale": "cdf"},
        )
        estimand_type = "lee_cdf_always_responders"
    elif functional is DistributionalFunctional.TAIL_DELTA:
        thresholds = np.asarray(axis_values, dtype=float)
        _, f1_lower, f1_upper = _lee_cdf_envelope(y1_obs, thresholds, alpha)
        f0 = _ecdf(y0_always, thresholds)
        pi0 = 1.0 - f0
        lower = 1.0 - f1_upper - pi0
        upper = 1.0 - f1_lower - pi0
        metadata["identified_control_tail_probability"] = tuple(float(item) for item in pi0)
        axis = GridAxis(axis_name="threshold", values=axis_values, unit=outcome_unit)
        bounds = FunctionalBounds(
            lower=tuple(float(item) for item in lower),
            upper=tuple(float(item) for item in upper),
            notes={"scale": "tail_probability_change"},
        )
        estimand_type = "tail_probability_change"
    elif functional is DistributionalFunctional.QUANTILE_SHIFT:
        quantiles = np.asarray(axis_values, dtype=float)
        if np.any((quantiles < 0.0) | (quantiles > 1.0)):
            raise ValueError("quantile_shift axis values must lie in [0, 1]")
        support = np.unique(np.concatenate([y1_obs, y0_always]))
        _, f1_lower, f1_upper = _lee_cdf_envelope(y1_obs, support, alpha)
        lower_values: list[float] = []
        upper_values: list[float] = []
        q0_values: list[float] = []
        for q_raw in quantiles:
            q = float(q_raw)
            q0 = _empirical_quantile(y0_always, q)
            q1_lower = _first_grid_value_at_or_above(support, f1_upper, q)
            q1_upper = _first_grid_value_at_or_above(support, f1_lower, q)
            lower_values.append(float(q1_lower - q0))
            upper_values.append(float(q1_upper - q0))
            q0_values.append(q0)
        metadata["identified_control_quantile"] = tuple(q0_values)
        axis = GridAxis(axis_name="quantile", values=axis_values, unit="probability")
        bounds = FunctionalBounds(
            lower=tuple(lower_values),
            upper=tuple(upper_values),
            notes={"scale": "quantile_shift"},
        )
        estimand_type = "quantile_shift"
    else:
        raise ValueError(f"lee_trimming does not support functional={functional.value}")

    summary = DistributionalBoundsMethodSummary(
        method="lee_trimming_distributional",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness="outer_approx",
        assumptions_used=assumptions,
        display_label="Lee monotone-selection distributional bounds",
        metadata=metadata,
    )
    return DistributionalBoundsBundle(
        estimand_type=estimand_type,
        functional=functional,
        axis=axis,
        method_summaries=[summary],
        sharpness_status="outer_approx",
        warnings=warnings,
        metadata=metadata,
    )


def _empirical_support_prob(values: Any, *, name: str) -> tuple[np.ndarray, np.ndarray]:
    vector = _finite_vector(values, name=name)
    support, counts = np.unique(vector, return_counts=True)
    probabilities = counts.astype(float) / float(vector.size)
    return support.astype(float), probabilities


def _event_probability_bounds_lp(
    y1_support: np.ndarray,
    y1_prob: np.ndarray,
    y0_support: np.ndarray,
    y0_prob: np.ndarray,
    threshold: float,
) -> tuple[float, float]:
    """Sharp empirical Makarov bounds for P(Y1 - Y0 <= threshold)."""

    from scipy.optimize import linprog

    n1 = y1_support.size
    n0 = y0_support.size
    event = (y1_support[:, None] - y0_support[None, :]) <= threshold
    objective = event.astype(float).reshape(-1)

    a_eq_rows: list[np.ndarray] = []
    b_eq: list[float] = []
    for i in range(n1):
        row = np.zeros(n1 * n0)
        row[i * n0 : (i + 1) * n0] = 1.0
        a_eq_rows.append(row)
        b_eq.append(float(y1_prob[i]))
    # Drop the final column equality; it is implied by row sums and other columns.
    for j in range(max(0, n0 - 1)):
        row = np.zeros(n1 * n0)
        row[j::n0] = 1.0
        a_eq_rows.append(row)
        b_eq.append(float(y0_prob[j]))

    a_eq = np.vstack(a_eq_rows)
    bounds = [(0.0, None)] * (n1 * n0)

    lower_result = linprog(
        objective,
        A_eq=a_eq,
        b_eq=np.asarray(b_eq, dtype=float),
        bounds=bounds,
        method="highs",
    )
    upper_result = linprog(
        -objective,
        A_eq=a_eq,
        b_eq=np.asarray(b_eq, dtype=float),
        bounds=bounds,
        method="highs",
    )
    if not lower_result.success or not upper_result.success:
        raise ValueError(
            "makarov_pointwise LP failed to solve for threshold "
            f"{threshold}: lower={lower_result.message}; upper={upper_result.message}"
        )

    lower = float(np.clip(lower_result.fun, 0.0, 1.0))
    upper = float(np.clip(-upper_result.fun, 0.0, 1.0))
    if lower > upper and lower - upper <= 1e-9:
        lower = upper
    return lower, upper


def _makarov_cdf_bounds(
    y1: Any,
    y0: Any,
    thresholds: tuple[float, ...],
) -> tuple[tuple[float, ...], tuple[float, ...], dict[str, Any]]:
    y1_support, y1_prob = _empirical_support_prob(y1, name="treated_outcome")
    y0_support, y0_prob = _empirical_support_prob(y0, name="control_outcome")
    lower_values: list[float] = []
    upper_values: list[float] = []
    for threshold in thresholds:
        lower, upper = _event_probability_bounds_lp(
            y1_support,
            y1_prob,
            y0_support,
            y0_prob,
            float(threshold),
        )
        lower_values.append(lower)
        upper_values.append(upper)
    metadata = {
        "n_treated_support": int(y1_support.size),
        "n_control_support": int(y0_support.size),
        "treated_support_min": float(y1_support[0]),
        "treated_support_max": float(y1_support[-1]),
        "control_support_min": float(y0_support[0]),
        "control_support_max": float(y0_support[-1]),
    }
    return tuple(lower_values), tuple(upper_values), metadata


def makarov_distributional_bounds(
    *,
    treated_outcome: Any,
    control_outcome: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    outcome_unit: str | None = None,
) -> DistributionalBoundsBundle:
    """Build Makarov/Frechet bounds for ITE functionals from marginal laws."""

    assumptions = [
        "known_or_identified_marginal_laws_y1_y0",
        "joint_potential_outcome_law_unidentified",
        "no_rank_invariance_or_copula_assumption",
    ]
    metadata: dict[str, Any] = {
        "theorem_family": "makarov_pointwise",
        "pointwise_not_uniform": len(axis_values) > 1,
        "copula_assumption": "none",
    }
    warnings = [POINTWISE_NON_UNIFORM_WARNING] if len(axis_values) > 1 else []
    sharpness = "sharp" if len(axis_values) == 1 else "outer_approx"

    if functional is DistributionalFunctional.ITE_CDF:
        thresholds = axis_values
        lower, upper, cdf_metadata = _makarov_cdf_bounds(
            treated_outcome,
            control_outcome,
            thresholds,
        )
        metadata.update(cdf_metadata)
        axis = GridAxis(axis_name="effect_threshold", values=thresholds, unit=outcome_unit)
        bounds = FunctionalBounds(
            lower=lower,
            upper=upper,
            monotone=True,
            notes={"scale": "ite_cdf"},
        )
        estimand_type = "ite_cdf"
    elif functional is DistributionalFunctional.ITE_TAIL_RISK:
        harm_thresholds = axis_values
        if any(item < 0.0 for item in harm_thresholds):
            raise ValueError("ite_tail_risk harm thresholds must be non-negative")
        effect_thresholds = tuple(-float(item) for item in harm_thresholds)
        lower, upper, cdf_metadata = _makarov_cdf_bounds(
            treated_outcome,
            control_outcome,
            effect_thresholds,
        )
        metadata.update(cdf_metadata)
        metadata["effect_thresholds"] = effect_thresholds
        axis = GridAxis(axis_name="harm_threshold", values=harm_thresholds, unit=outcome_unit)
        bounds = FunctionalBounds(
            lower=lower,
            upper=upper,
            notes={"scale": "ite_tail_risk"},
        )
        estimand_type = "ite_tail_risk"
    elif functional is DistributionalFunctional.QUANTILE:
        quantiles = axis_values
        if any(item < 0.0 or item > 1.0 for item in quantiles):
            raise ValueError("ite quantiles must lie in [0, 1]")
        y1_support, _ = _empirical_support_prob(treated_outcome, name="treated_outcome")
        y0_support, _ = _empirical_support_prob(control_outcome, name="control_outcome")
        effect_grid = tuple(
            float(item)
            for item in np.unique((y1_support[:, None] - y0_support[None, :]).reshape(-1))
        )
        lower_cdf, upper_cdf, cdf_metadata = _makarov_cdf_bounds(
            treated_outcome,
            control_outcome,
            effect_grid,
        )
        lower_cdf_array = np.asarray(lower_cdf, dtype=float)
        upper_cdf_array = np.asarray(upper_cdf, dtype=float)
        grid_array = np.asarray(effect_grid, dtype=float)
        lower_quantiles: list[float] = []
        upper_quantiles: list[float] = []
        for q in quantiles:
            lower_quantiles.append(_first_grid_value_at_or_above(grid_array, upper_cdf_array, q))
            upper_quantiles.append(_first_grid_value_at_or_above(grid_array, lower_cdf_array, q))
        metadata.update(cdf_metadata)
        metadata["effect_grid_size"] = len(effect_grid)
        axis = GridAxis(axis_name="quantile", values=quantiles, unit="probability")
        bounds = FunctionalBounds(
            lower=tuple(lower_quantiles),
            upper=tuple(upper_quantiles),
            notes={"scale": "ite_quantile"},
        )
        estimand_type = "ite_quantile"
    else:
        raise ValueError(f"makarov_pointwise does not support functional={functional.value}")

    summary = DistributionalBoundsMethodSummary(
        method="makarov_pointwise",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="Makarov pointwise distributional bounds",
        metadata=metadata,
    )
    return DistributionalBoundsBundle(
        estimand_type=estimand_type,
        functional=functional,
        axis=axis,
        method_summaries=[summary],
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=metadata,
    )


def _headcount_certificate(
    *,
    axis: GridAxis,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    assumptions: list[str],
    target_potential_outcome: str,
    support_domain: DistributionalSupportDomain | None,
    metadata: dict[str, Any],
    theorem_family: str = "mtr_headcount",
    assumption_class: str = "mtr",
    primal_problem_class: str = "binary_potential_outcome_box",
    dual_problem_class: str = "indicator_threshold_dual",
) -> DistributionalDualCertificate:
    pointwise_only = len(axis.values) > 1
    dual_gaps = tuple(0.0 for _ in axis.values)
    return DistributionalDualCertificate(
        theorem_family=theorem_family,
        functional=DistributionalFunctional.POVERTY_HEADCOUNT,
        axis=axis,
        assumption_class=assumption_class,
        primal_problem_class=primal_problem_class,
        dual_problem_class=dual_problem_class,
        sharpness_status="outer_approx" if pointwise_only else "sharp",
        bound_uniformity=(
            DistributionalBoundUniformity.POINTWISE_ONLY
            if pointwise_only
            else DistributionalBoundUniformity.NOT_APPLICABLE
        ),
        attainment_status="attained",
        support_domain=support_domain,
        normalization={
            "mode": "population_share",
            "target_potential_outcome": target_potential_outcome,
        },
        lower_bound_witness=DistributionalDualBoundWitness(
            bound_direction="lower",
            primal_objective_values=lower,
            dual_objective_values=lower,
            dual_gaps=dual_gaps,
            metadata={"closed_form_witness": "endpoint_allocation"},
        ),
        upper_bound_witness=DistributionalDualBoundWitness(
            bound_direction="upper",
            primal_objective_values=upper,
            dual_objective_values=upper,
            dual_gaps=dual_gaps,
            metadata={"closed_form_witness": "endpoint_allocation"},
        ),
        pointwise_not_uniform_warning=pointwise_only,
        assumptions_used=assumptions,
        metadata=metadata,
    )


def mtr_headcount_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build sharp pointwise MTR bounds for poverty headcount functionals."""

    if functional is not DistributionalFunctional.POVERTY_HEADCOUNT:
        raise ValueError(f"mtr_headcount does not support functional={functional.value}")
    if target_potential_outcome not in {"y0", "y1"}:
        raise ValueError("target_potential_outcome must be 'y0' or 'y1'")

    y = _finite_vector(outcome, name="outcome")
    d = _binary_mask(treatment, name="treatment")
    if y.size != d.size:
        raise ValueError("outcome and treatment must have equal length")
    if not np.any(d) or not np.any(~d):
        raise ValueError("mtr_headcount requires both treatment arms")

    y1_obs = y[d]
    y0_obs = y[~d]
    p1 = float(np.mean(d))
    p0 = 1.0 - p1
    lower_values: list[float] = []
    upper_values: list[float] = []
    treated_rates: list[float] = []
    control_rates: list[float] = []

    for poverty_line in axis_values:
        mu11 = _indicator_mean(y1_obs, float(poverty_line))
        mu00 = _indicator_mean(y0_obs, float(poverty_line))
        treated_rates.append(mu11)
        control_rates.append(mu00)
        if target_potential_outcome == "y1":
            lower_values.append(p1 * mu11)
            upper_values.append(p1 * mu11 + p0 * mu00)
        else:
            lower_values.append(p1 * mu11 + p0 * mu00)
            upper_values.append(p1 + p0 * mu00)

    metadata: dict[str, Any] = {
        "theorem_family": "mtr_headcount",
        "assumption_class": "mtr",
        "pointwise_not_uniform": len(axis_values) > 1,
        "target_potential_outcome": target_potential_outcome,
        "p_treated": p1,
        "p_control": p0,
        "treated_observed_headcount": tuple(treated_rates),
        "control_observed_headcount": tuple(control_rates),
    }
    assumptions = [
        "monotone_treatment_response_y1_ge_y0",
        "consistency",
        "stable_unit_treatment_value_assumption",
    ]
    warnings = [POINTWISE_NON_UNIFORM_WARNING] if len(axis_values) > 1 else []
    sharpness = "outer_approx" if len(axis_values) > 1 else "sharp"
    axis = GridAxis(axis_name="poverty_line", values=axis_values, unit=outcome_unit)
    bounds = FunctionalBounds(
        lower=tuple(lower_values),
        upper=tuple(upper_values),
        monotone=True,
        notes={"scale": "poverty_headcount"},
    )
    parameters = DistributionalFunctionalParameters(
        poverty_line=float(axis_values[0]) if len(axis_values) == 1 else None,
        poverty_lines=axis_values,
        normalization_mode="population_share",
        target_potential_outcome=target_potential_outcome,
    )
    summary = DistributionalBoundsMethodSummary(
        method="mtr_headcount",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="MTR poverty-headcount bounds",
        metadata=metadata,
    )
    support_domain = DistributionalSupportDomain(
        lower=float(np.min(y)),
        upper=float(np.max(y)),
        unit=outcome_unit,
    )
    certificate = _headcount_certificate(
        axis=axis,
        lower=tuple(lower_values),
        upper=tuple(upper_values),
        assumptions=assumptions,
        target_potential_outcome=target_potential_outcome,
        support_domain=support_domain,
        metadata=metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"poverty_headcount_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=metadata,
    )
    return bundle, certificate


def sd_headcount_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build FOSD-only v1 bounds for poverty headcount functionals."""

    if functional is not DistributionalFunctional.POVERTY_HEADCOUNT:
        raise ValueError(f"sd_headcount does not support functional={functional.value}")

    thresholds = np.asarray(axis_values, dtype=float)
    y, lower, upper, _, _p1, _p0, envelope_metadata = _fosd_pointwise_cdf_bounds(
        outcome=outcome,
        treatment=treatment,
        thresholds=thresholds,
        target_potential_outcome=target_potential_outcome,
    )
    metadata: dict[str, Any] = {
        **envelope_metadata,
        "theorem_family": "sd_headcount",
        "assumption_class": "stochastic_dominance_fosd",
        "pointwise_not_uniform": len(axis_values) > 1,
    }
    assumptions = [
        "first_order_stochastic_dominance_y1_ge_y0",
        "consistency",
        "stable_unit_treatment_value_assumption",
    ]
    warnings = [POINTWISE_NON_UNIFORM_WARNING] if len(axis_values) > 1 else []
    sharpness = "outer_approx" if len(axis_values) > 1 else "sharp"
    axis = GridAxis(axis_name="poverty_line", values=axis_values, unit=outcome_unit)
    bounds = FunctionalBounds(
        lower=tuple(float(item) for item in lower),
        upper=tuple(float(item) for item in upper),
        monotone=True,
        notes={"scale": "poverty_headcount"},
    )
    parameters = DistributionalFunctionalParameters(
        poverty_line=float(axis_values[0]) if len(axis_values) == 1 else None,
        poverty_lines=axis_values,
        normalization_mode="population_share",
        target_potential_outcome=target_potential_outcome,
    )
    summary = DistributionalBoundsMethodSummary(
        method="sd_headcount",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="FOSD poverty-headcount bounds",
        metadata=metadata,
    )
    support_domain = DistributionalSupportDomain(
        lower=float(np.min(y)),
        upper=float(np.max(y)),
        unit=outcome_unit,
    )
    certificate = _headcount_certificate(
        axis=axis,
        lower=tuple(float(item) for item in lower),
        upper=tuple(float(item) for item in upper),
        assumptions=assumptions,
        target_potential_outcome=target_potential_outcome,
        support_domain=support_domain,
        metadata=metadata,
        theorem_family="sd_headcount",
        assumption_class="stochastic_dominance_fosd",
        primal_problem_class="fosd_headcount_linear_program",
        dual_problem_class="order_cone_linear_dual",
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"poverty_headcount_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=metadata,
    )
    return bundle, certificate


def _sd_quantile_box(
    *,
    outcome: Any,
    treatment: Any,
    target_potential_outcome: str,
    support_floor: float | None,
    support_ceiling: float | None,
    outcome_unit: str | None,
) -> tuple[
    np.ndarray,
    np.ndarray,
    DistributionalSupportDomain,
    list[str],
    list[str],
    list[str],
    dict[str, Any],
    bool,
]:
    y = _nonnegative_vector(outcome, name="outcome")
    support_domain, warnings, rescue_actions, support_metadata, support_is_explicit = (
        _distributional_support_domain_from_values(
            y,
            support_floor=support_floor,
            support_ceiling=support_ceiling,
            outcome_unit=outcome_unit,
        )
    )
    support_grid = np.unique(
        np.concatenate(
            [
                y,
                np.asarray((support_domain.lower, support_domain.upper), dtype=float),
            ]
        )
    )
    _, cdf_lower, cdf_upper, support_grid, _p1, _p0, envelope_metadata = _fosd_pointwise_cdf_bounds(
        outcome=y,
        treatment=treatment,
        thresholds=support_grid,
        target_potential_outcome=target_potential_outcome,
    )
    lower_box, upper_box, quantile_metadata = _quantile_boxes_from_cdf_envelope(
        support_grid=support_grid,
        cdf_lower=cdf_lower,
        cdf_upper=cdf_upper,
        n_ranks=int(y.size),
    )
    assumptions = [
        "first_order_stochastic_dominance_y1_ge_y0",
        "consistency",
        "stable_unit_treatment_value_assumption",
    ]
    if support_floor is not None:
        assumptions.append("bounded_support_lower")
    if support_ceiling is not None:
        assumptions.append("bounded_support_upper")

    warnings = [*warnings, STOCHASTIC_DOMINANCE_OUTER_WARNING]
    rescue_actions = [*rescue_actions, "upgrade_to_uniform_distributional_certificate"]
    metadata = {
        **support_metadata,
        **envelope_metadata,
        **quantile_metadata,
        "cdf_lower_envelope": tuple(float(item) for item in cdf_lower),
        "cdf_upper_envelope": tuple(float(item) for item in cdf_upper),
        "support_grid": tuple(float(item) for item in support_grid),
        "pointwise_not_uniform": True,
    }
    return (
        lower_box,
        upper_box,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        support_is_explicit,
    )


def mtr_theil_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    support_floor: float | None = None,
    support_ceiling: float | None = None,
    mean_floor: float | None = None,
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build MTR bounds for the Theil T inequality functional."""

    if functional is not DistributionalFunctional.THEIL_T:
        raise ValueError(f"mtr_theil does not support functional={functional.value}")
    if len(axis_values) != 1:
        raise ValueError("mtr_theil expects a single scalar query")

    (
        fixed,
        free_lower,
        free_upper,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        support_is_explicit,
    ) = _mtr_counterfactual_box(
        outcome=outcome,
        treatment=treatment,
        target_potential_outcome=target_potential_outcome,
        support_floor=support_floor,
        support_ceiling=support_ceiling,
        outcome_unit=outcome_unit,
    )

    min_feasible_values = np.concatenate([fixed, free_lower])
    min_feasible_mean = float(np.mean(np.maximum(min_feasible_values, 1e-12)))
    effective_mean_floor = float(mean_floor) if mean_floor is not None else min_feasible_mean
    mean_floor_certified = True
    if mean_floor is not None and mean_floor > min_feasible_mean + 1e-12:
        mean_floor_certified = False
        warnings.append(
            "Supplied mean_floor exceeds the minimum feasible mean under the MTR box; "
            "the bound is computed on the unrestricted box and kept as an outer approximation."
        )
        rescue_actions.append("tighten_mean_floor_or_shrink_identified_set")

    objective = lambda free: _theil_index(np.concatenate([fixed, np.asarray(free, dtype=float)]))
    lower_completion, lower_value, lower_meta = _equalized_completion_search(
        lower=free_lower,
        upper=free_upper,
        objective=objective,
    )
    upper_completion, upper_value, upper_meta = _upper_extreme_completion_search(
        lower=free_lower,
        upper=free_upper,
        objective=objective,
    )

    sharpness = (
        "sharp"
        if support_is_explicit and effective_mean_floor > 0.0 and mean_floor_certified
        else "outer_approx"
    )
    axis = _scalar_axis(axis_name="functional_query", axis_value=axis_values[0], unit="query")
    parameters = DistributionalFunctionalParameters(
        mean_floor=effective_mean_floor if effective_mean_floor > 0.0 else None,
        support_floor=support_domain.lower,
        support_ceiling=support_domain.upper,
        normalization_mode="mean_normalized_entropy",
        target_potential_outcome=target_potential_outcome,
    )
    method_metadata = {
        **metadata,
        "theorem_family": "mtr_theil",
        "assumption_class": "mtr",
        "pointwise_not_uniform": False,
        "minimum_feasible_mean": min_feasible_mean,
        "lower_extremizer": {
            **lower_meta,
            "completion": tuple(float(item) for item in lower_completion),
        },
        "upper_extremizer": {
            **upper_meta,
            "completion": tuple(float(item) for item in upper_completion),
        },
    }
    bounds = FunctionalBounds(
        lower=(float(lower_value),),
        upper=(float(upper_value),),
        notes={"scale": "theil_t"},
    )
    summary = DistributionalBoundsMethodSummary(
        method="mtr_theil",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="MTR Theil-T bounds",
        metadata=method_metadata,
    )
    certificate = _build_distributional_dual_certificate(
        theorem_family="mtr_theil",
        functional=functional,
        axis=axis,
        primal_problem_class="mean_normalized_box_extremal",
        dual_problem_class="fenchel_ratio_dual"
        if sharpness == "sharp"
        else "fenchel_ratio_outer_dual",
        sharpness_status=sharpness,
        bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
        support_domain=support_domain,
        normalization={
            "mode": "mean_normalized_entropy",
            "target_potential_outcome": target_potential_outcome,
            "mean_floor": effective_mean_floor,
        },
        lower_value=float(lower_value),
        upper_value=float(upper_value),
        lower_metadata={"extremizer_family": "equalization_clip", **lower_meta},
        upper_metadata={"extremizer_family": "endpoint_threshold", **upper_meta},
        assumptions=assumptions,
        metadata=method_metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"theil_t_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=rescue_actions,
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=method_metadata,
    )
    return bundle, certificate


def sd_theil_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    support_floor: float | None = None,
    support_ceiling: float | None = None,
    mean_floor: float | None = None,
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build FOSD-only v1 outer bounds for the Theil T inequality functional."""

    if functional is not DistributionalFunctional.THEIL_T:
        raise ValueError(f"sd_theil does not support functional={functional.value}")
    if len(axis_values) != 1:
        raise ValueError("sd_theil expects a single scalar query")

    (
        lower_box,
        upper_box,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        _support_is_explicit,
    ) = _sd_quantile_box(
        outcome=outcome,
        treatment=treatment,
        target_potential_outcome=target_potential_outcome,
        support_floor=support_floor,
        support_ceiling=support_ceiling,
        outcome_unit=outcome_unit,
    )

    min_feasible_mean = float(np.mean(np.maximum(lower_box, 1e-12)))
    effective_mean_floor = float(mean_floor) if mean_floor is not None else min_feasible_mean
    mean_floor_certified = mean_floor is not None and mean_floor <= min_feasible_mean + 1e-12
    if mean_floor is None:
        warnings.append(
            "sd_theil requires an explicit mean_floor to certify sharpness; keeping the interval outer."
        )
        rescue_actions.append("provide_mean_floor")
    elif not mean_floor_certified:
        warnings.append(
            "Supplied mean_floor exceeds the minimum feasible mean under the FOSD envelope; "
            "the interval remains outer."
        )
        rescue_actions.append("tighten_mean_floor_or_relax_target")

    objective = lambda values: _theil_index(np.asarray(values, dtype=float))
    lower_completion, lower_value, lower_meta = _equalized_completion_search(
        lower=lower_box,
        upper=upper_box,
        objective=objective,
    )
    upper_completion, upper_value, upper_meta = _upper_extreme_completion_search(
        lower=lower_box,
        upper=upper_box,
        objective=objective,
    )

    sharpness = "outer_approx"
    axis = _scalar_axis(axis_name="functional_query", axis_value=axis_values[0], unit="query")
    parameters = DistributionalFunctionalParameters(
        mean_floor=effective_mean_floor if effective_mean_floor > 0.0 else None,
        support_floor=support_domain.lower,
        support_ceiling=support_domain.upper,
        normalization_mode="mean_normalized_entropy",
        target_potential_outcome=target_potential_outcome,
    )
    method_metadata = {
        **metadata,
        "theorem_family": "sd_theil",
        "assumption_class": "stochastic_dominance_fosd",
        "minimum_feasible_mean": min_feasible_mean,
        "mean_floor_certified": mean_floor_certified,
        "lower_extremizer": {
            **lower_meta,
            "completion": tuple(float(item) for item in lower_completion),
        },
        "upper_extremizer": {
            **upper_meta,
            "completion": tuple(float(item) for item in upper_completion),
        },
    }
    bounds = FunctionalBounds(
        lower=(float(lower_value),),
        upper=(float(upper_value),),
        notes={"scale": "theil_t"},
    )
    summary = DistributionalBoundsMethodSummary(
        method="sd_theil",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="FOSD Theil-T bounds",
        metadata=method_metadata,
    )
    certificate = _build_distributional_dual_certificate(
        theorem_family="sd_theil",
        functional=functional,
        axis=axis,
        assumption_class="stochastic_dominance_fosd",
        primal_problem_class="fosd_quantile_box_extremal",
        dual_problem_class="order_cone_outer_dual",
        sharpness_status=sharpness,
        bound_uniformity=DistributionalBoundUniformity.POINTWISE_ONLY,
        support_domain=support_domain,
        normalization={
            "mode": "mean_normalized_entropy",
            "target_potential_outcome": target_potential_outcome,
            "mean_floor": effective_mean_floor,
        },
        lower_value=float(lower_value),
        upper_value=float(upper_value),
        lower_metadata={"extremizer_family": "equalization_clip", **lower_meta},
        upper_metadata={"extremizer_family": "endpoint_threshold", **upper_meta},
        assumptions=assumptions,
        metadata=method_metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"theil_t_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=rescue_actions,
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=method_metadata,
    )
    return bundle, certificate


def mtr_atkinson_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    support_floor: float | None = None,
    support_ceiling: float | None = None,
    mean_floor: float | None = None,
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build MTR bounds for the Atkinson inequality functional."""

    if functional is not DistributionalFunctional.ATKINSON:
        raise ValueError(f"mtr_atkinson does not support functional={functional.value}")
    if len(axis_values) != 1:
        raise ValueError("mtr_atkinson expects a single epsilon query")

    epsilon = float(axis_values[0])
    (
        fixed,
        free_lower,
        free_upper,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        support_is_explicit,
    ) = _mtr_counterfactual_box(
        outcome=outcome,
        treatment=treatment,
        target_potential_outcome=target_potential_outcome,
        support_floor=support_floor,
        support_ceiling=support_ceiling,
        outcome_unit=outcome_unit,
    )

    min_feasible_values = np.concatenate([fixed, free_lower])
    min_feasible_mean = float(np.mean(np.maximum(min_feasible_values, 1e-12)))
    effective_mean_floor = float(mean_floor) if mean_floor is not None else min_feasible_mean
    strictly_positive_support = bool(np.min(min_feasible_values) > 0.0)
    mean_floor_certified = True
    if mean_floor is not None and mean_floor > min_feasible_mean + 1e-12:
        mean_floor_certified = False
        warnings.append(
            "Supplied mean_floor exceeds the minimum feasible mean under the MTR box; "
            "the Atkinson interval is computed on the unrestricted box and kept outer."
        )
        rescue_actions.append("tighten_mean_floor_or_shrink_identified_set")

    if epsilon >= 1.0 and not strictly_positive_support:
        warnings.append(ATKINSON_POSITIVITY_WARNING)
        rescue_actions.append("provide_positive_support_floor")

    objective = lambda free: _atkinson_index(
        np.concatenate([fixed, np.asarray(free, dtype=float)]),
        epsilon=epsilon,
    )
    lower_completion, lower_value, lower_meta = _equalized_completion_search(
        lower=free_lower,
        upper=free_upper,
        objective=objective,
    )
    upper_completion, upper_value, upper_meta = _upper_extreme_completion_search(
        lower=free_lower,
        upper=free_upper,
        objective=objective,
    )

    sharpness = (
        "sharp"
        if support_is_explicit
        and effective_mean_floor > 0.0
        and mean_floor_certified
        and (epsilon < 1.0 or strictly_positive_support)
        else "outer_approx"
    )
    axis = GridAxis(axis_name="atkinson_epsilon", values=(epsilon,), unit="aversion")
    parameters = DistributionalFunctionalParameters(
        atkinson_epsilon=epsilon,
        mean_floor=effective_mean_floor if effective_mean_floor > 0.0 else None,
        support_floor=support_domain.lower,
        support_ceiling=support_domain.upper,
        normalization_mode="equally_distributed_equivalent_income",
        target_potential_outcome=target_potential_outcome,
    )
    method_metadata = {
        **metadata,
        "theorem_family": "mtr_atkinson",
        "assumption_class": "mtr",
        "pointwise_not_uniform": False,
        "minimum_feasible_mean": min_feasible_mean,
        "atkinson_epsilon": epsilon,
        "strictly_positive_support": strictly_positive_support,
        "lower_extremizer": {
            **lower_meta,
            "completion": tuple(float(item) for item in lower_completion),
        },
        "upper_extremizer": {
            **upper_meta,
            "completion": tuple(float(item) for item in upper_completion),
        },
    }
    bounds = FunctionalBounds(
        lower=(float(lower_value),),
        upper=(float(upper_value),),
        notes={"scale": "atkinson"},
    )
    summary = DistributionalBoundsMethodSummary(
        method="mtr_atkinson",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="MTR Atkinson bounds",
        metadata=method_metadata,
    )
    certificate = _build_distributional_dual_certificate(
        theorem_family="mtr_atkinson",
        functional=functional,
        axis=axis,
        primal_problem_class="ede_box_extremal",
        dual_problem_class="power_moment_dual"
        if sharpness == "sharp"
        else "power_moment_outer_dual",
        sharpness_status=sharpness,
        bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
        support_domain=support_domain,
        normalization={
            "mode": "equally_distributed_equivalent_income",
            "target_potential_outcome": target_potential_outcome,
            "mean_floor": effective_mean_floor,
            "epsilon": epsilon,
        },
        lower_value=float(lower_value),
        upper_value=float(upper_value),
        lower_metadata={"extremizer_family": "equalization_clip", **lower_meta},
        upper_metadata={"extremizer_family": "endpoint_threshold", **upper_meta},
        assumptions=assumptions,
        metadata=method_metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"atkinson_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=rescue_actions,
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=method_metadata,
    )
    return bundle, certificate


def sd_atkinson_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    support_floor: float | None = None,
    support_ceiling: float | None = None,
    mean_floor: float | None = None,
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build FOSD-only v1 outer bounds for the Atkinson inequality functional."""

    if functional is not DistributionalFunctional.ATKINSON:
        raise ValueError(f"sd_atkinson does not support functional={functional.value}")
    if len(axis_values) != 1:
        raise ValueError("sd_atkinson expects a single epsilon query")

    epsilon = float(axis_values[0])
    (
        lower_box,
        upper_box,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        _support_is_explicit,
    ) = _sd_quantile_box(
        outcome=outcome,
        treatment=treatment,
        target_potential_outcome=target_potential_outcome,
        support_floor=support_floor,
        support_ceiling=support_ceiling,
        outcome_unit=outcome_unit,
    )

    min_feasible_mean = float(np.mean(np.maximum(lower_box, 1e-12)))
    effective_mean_floor = float(mean_floor) if mean_floor is not None else min_feasible_mean
    strictly_positive_support = bool(np.min(lower_box) > 0.0)
    mean_floor_certified = mean_floor is not None and mean_floor <= min_feasible_mean + 1e-12
    if mean_floor is None:
        warnings.append(
            "sd_atkinson requires an explicit mean_floor to certify sharpness; keeping the interval outer."
        )
        rescue_actions.append("provide_mean_floor")
    elif not mean_floor_certified:
        warnings.append(
            "Supplied mean_floor exceeds the minimum feasible mean under the FOSD envelope; "
            "the interval remains outer."
        )
        rescue_actions.append("tighten_mean_floor_or_relax_target")

    if epsilon >= 1.0 and not strictly_positive_support:
        warnings.append(ATKINSON_POSITIVITY_WARNING)
        rescue_actions.append("provide_positive_support_floor")

    objective = lambda values: _atkinson_index(np.asarray(values, dtype=float), epsilon=epsilon)
    lower_completion, lower_value, lower_meta = _equalized_completion_search(
        lower=lower_box,
        upper=upper_box,
        objective=objective,
    )
    upper_completion, upper_value, upper_meta = _upper_extreme_completion_search(
        lower=lower_box,
        upper=upper_box,
        objective=objective,
    )

    sharpness = "outer_approx"
    axis = GridAxis(axis_name="atkinson_epsilon", values=(epsilon,), unit="aversion")
    parameters = DistributionalFunctionalParameters(
        atkinson_epsilon=epsilon,
        mean_floor=effective_mean_floor if effective_mean_floor > 0.0 else None,
        support_floor=support_domain.lower,
        support_ceiling=support_domain.upper,
        normalization_mode="equally_distributed_equivalent_income",
        target_potential_outcome=target_potential_outcome,
    )
    method_metadata = {
        **metadata,
        "theorem_family": "sd_atkinson",
        "assumption_class": "stochastic_dominance_fosd",
        "minimum_feasible_mean": min_feasible_mean,
        "mean_floor_certified": mean_floor_certified,
        "atkinson_epsilon": epsilon,
        "strictly_positive_support": strictly_positive_support,
        "lower_extremizer": {
            **lower_meta,
            "completion": tuple(float(item) for item in lower_completion),
        },
        "upper_extremizer": {
            **upper_meta,
            "completion": tuple(float(item) for item in upper_completion),
        },
    }
    bounds = FunctionalBounds(
        lower=(float(lower_value),),
        upper=(float(upper_value),),
        notes={"scale": "atkinson"},
    )
    summary = DistributionalBoundsMethodSummary(
        method="sd_atkinson",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="FOSD Atkinson bounds",
        metadata=method_metadata,
    )
    certificate = _build_distributional_dual_certificate(
        theorem_family="sd_atkinson",
        functional=functional,
        axis=axis,
        assumption_class="stochastic_dominance_fosd",
        primal_problem_class="fosd_quantile_box_extremal",
        dual_problem_class="power_moment_outer_dual",
        sharpness_status=sharpness,
        bound_uniformity=DistributionalBoundUniformity.POINTWISE_ONLY,
        support_domain=support_domain,
        normalization={
            "mode": "equally_distributed_equivalent_income",
            "target_potential_outcome": target_potential_outcome,
            "mean_floor": effective_mean_floor,
            "epsilon": epsilon,
        },
        lower_value=float(lower_value),
        upper_value=float(upper_value),
        lower_metadata={"extremizer_family": "equalization_clip", **lower_meta},
        upper_metadata={"extremizer_family": "endpoint_threshold", **upper_meta},
        assumptions=assumptions,
        metadata=method_metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"atkinson_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=rescue_actions,
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=method_metadata,
    )
    return bundle, certificate


def mtr_gini_lorenz_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    support_floor: float | None = None,
    support_ceiling: float | None = None,
    mean_floor: float | None = None,
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build Lorenz-routed MTR bounds for the Gini functional."""

    del mean_floor
    if functional is not DistributionalFunctional.GINI:
        raise ValueError(f"mtr_gini_lorenz does not support functional={functional.value}")
    if len(axis_values) != 1:
        raise ValueError("mtr_gini_lorenz expects a single scalar query")

    (
        fixed,
        free_lower,
        free_upper,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        _support_is_explicit,
    ) = _mtr_counterfactual_box(
        outcome=outcome,
        treatment=treatment,
        target_potential_outcome=target_potential_outcome,
        support_floor=support_floor,
        support_ceiling=support_ceiling,
        outcome_unit=outcome_unit,
    )

    objective = lambda free: _gini_index(np.concatenate([fixed, np.asarray(free, dtype=float)]))
    lower_completion, lower_value, lower_meta = _equalized_completion_search(
        lower=free_lower,
        upper=free_upper,
        objective=objective,
    )
    upper_completion, upper_value, upper_meta = _upper_extreme_completion_search(
        lower=free_lower,
        upper=free_upper,
        objective=objective,
    )

    warnings.append(GINI_UNIFORM_CERTIFICATE_WARNING)
    rescue_actions.append("upgrade_to_uniform_lorenz_or_lifted_pairwise_certificate")
    sharpness = "outer_approx"
    axis = _scalar_axis(axis_name="functional_query", axis_value=axis_values[0], unit="query")
    parameters = DistributionalFunctionalParameters(
        support_floor=support_domain.lower,
        support_ceiling=support_domain.upper,
        normalization_mode="lorenz_area",
        target_potential_outcome=target_potential_outcome,
    )
    method_metadata = {
        **metadata,
        "theorem_family": "mtr_gini_lorenz",
        "assumption_class": "mtr",
        "pointwise_not_uniform": False,
        "lower_extremizer": {
            **lower_meta,
            "completion": tuple(float(item) for item in lower_completion),
        },
        "upper_extremizer": {
            **upper_meta,
            "completion": tuple(float(item) for item in upper_completion),
        },
    }
    bounds = FunctionalBounds(
        lower=(float(lower_value),),
        upper=(float(upper_value),),
        notes={"scale": "gini"},
    )
    summary = DistributionalBoundsMethodSummary(
        method="mtr_gini_lorenz",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="MTR Gini bounds via Lorenz route",
        metadata=method_metadata,
    )
    certificate = _build_distributional_dual_certificate(
        theorem_family="mtr_gini_lorenz",
        functional=functional,
        axis=axis,
        primal_problem_class="lorenz_box_extremal",
        dual_problem_class="lorenz_uniform_outer_dual",
        sharpness_status=sharpness,
        bound_uniformity=DistributionalBoundUniformity.UNIFORM_OUTER,
        support_domain=support_domain,
        normalization={
            "mode": "lorenz_area",
            "target_potential_outcome": target_potential_outcome,
        },
        lower_value=float(lower_value),
        upper_value=float(upper_value),
        lower_metadata={"extremizer_family": "equalization_clip", **lower_meta},
        upper_metadata={"extremizer_family": "endpoint_threshold", **upper_meta},
        assumptions=assumptions,
        metadata=method_metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"gini_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=rescue_actions,
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=method_metadata,
    )
    return bundle, certificate


def sd_gini_lorenz_distributional_bounds(
    *,
    outcome: Any,
    treatment: Any,
    functional: DistributionalFunctional,
    axis_values: tuple[float, ...],
    target_potential_outcome: str = "y1",
    support_floor: float | None = None,
    support_ceiling: float | None = None,
    mean_floor: float | None = None,
    outcome_unit: str | None = None,
) -> tuple[DistributionalBoundsBundle, DistributionalDualCertificate]:
    """Build FOSD-only v1 outer bounds for the Gini functional."""

    del mean_floor
    if functional is not DistributionalFunctional.GINI:
        raise ValueError(f"sd_gini_lorenz does not support functional={functional.value}")
    if len(axis_values) != 1:
        raise ValueError("sd_gini_lorenz expects a single scalar query")

    (
        lower_box,
        upper_box,
        support_domain,
        assumptions,
        warnings,
        rescue_actions,
        metadata,
        _support_is_explicit,
    ) = _sd_quantile_box(
        outcome=outcome,
        treatment=treatment,
        target_potential_outcome=target_potential_outcome,
        support_floor=support_floor,
        support_ceiling=support_ceiling,
        outcome_unit=outcome_unit,
    )

    objective = lambda values: _gini_index(np.asarray(values, dtype=float))
    lower_completion, lower_value, lower_meta = _equalized_completion_search(
        lower=lower_box,
        upper=upper_box,
        objective=objective,
    )
    upper_completion, upper_value, upper_meta = _upper_extreme_completion_search(
        lower=lower_box,
        upper=upper_box,
        objective=objective,
    )

    warnings.append(GINI_UNIFORM_CERTIFICATE_WARNING)
    rescue_actions.append("upgrade_to_uniform_lorenz_or_lifted_pairwise_certificate")
    sharpness = "outer_approx"
    axis = _scalar_axis(axis_name="functional_query", axis_value=axis_values[0], unit="query")
    parameters = DistributionalFunctionalParameters(
        support_floor=support_domain.lower,
        support_ceiling=support_domain.upper,
        normalization_mode="lorenz_area",
        target_potential_outcome=target_potential_outcome,
    )
    method_metadata = {
        **metadata,
        "theorem_family": "sd_gini_lorenz",
        "assumption_class": "stochastic_dominance_fosd",
        "lower_extremizer": {
            **lower_meta,
            "completion": tuple(float(item) for item in lower_completion),
        },
        "upper_extremizer": {
            **upper_meta,
            "completion": tuple(float(item) for item in upper_completion),
        },
    }
    bounds = FunctionalBounds(
        lower=(float(lower_value),),
        upper=(float(upper_value),),
        notes={"scale": "gini"},
    )
    summary = DistributionalBoundsMethodSummary(
        method="sd_gini_lorenz",
        functional=functional,
        axis=axis,
        bounds=bounds,
        sharpness=sharpness,
        assumptions_used=assumptions,
        display_label="FOSD Gini bounds via Lorenz route",
        metadata=method_metadata,
    )
    certificate = _build_distributional_dual_certificate(
        theorem_family="sd_gini_lorenz",
        functional=functional,
        axis=axis,
        assumption_class="stochastic_dominance_fosd",
        primal_problem_class="fosd_lorenz_outer_extremal",
        dual_problem_class="lorenz_pointwise_outer_dual",
        sharpness_status=sharpness,
        bound_uniformity=DistributionalBoundUniformity.POINTWISE_ONLY,
        support_domain=support_domain,
        normalization={
            "mode": "lorenz_area",
            "target_potential_outcome": target_potential_outcome,
        },
        lower_value=float(lower_value),
        upper_value=float(upper_value),
        lower_metadata={"extremizer_family": "equalization_clip", **lower_meta},
        upper_metadata={"extremizer_family": "endpoint_threshold", **upper_meta},
        assumptions=assumptions,
        metadata=method_metadata,
    )
    bundle = DistributionalBoundsBundle(
        estimand_type=f"gini_{target_potential_outcome}",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=rescue_actions,
        sharpness_status=sharpness,
        warnings=warnings,
        metadata=method_metadata,
    )
    return bundle, certificate


def _marginal_outcomes_from_state(state: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    if "treated_outcome" in state and "control_outcome" in state:
        return (
            _finite_vector(state["treated_outcome"], name="treated_outcome"),
            _finite_vector(state["control_outcome"], name="control_outcome"),
        )
    if "outcome" not in state or "treatment" not in state:
        raise ValueError(
            "makarov_pointwise requires treated_outcome/control_outcome or outcome/treatment"
        )
    outcome = _finite_vector(state["outcome"], name="outcome")
    treatment = _binary_mask(state["treatment"], name="treatment")
    if outcome.size != treatment.size:
        raise ValueError("outcome and treatment must have equal length")
    if not np.any(treatment) or not np.any(~treatment):
        raise ValueError("makarov_pointwise requires both treatment arms")
    return outcome[treatment], outcome[~treatment]


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "distributional", "partial-identification"},
)
class DistributionalBoundsEngineMethod:
    """Build distributional partial-identification bounds for supported functionals."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="distributional_bounds_engine",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "numeric"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "selected", SlotType.VECTOR, Unit("selection", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "treated_outcome",
                    SlotType.VECTOR,
                    Unit("outcome", "numeric"),
                    shape=("n_treated",),
                ),
                SlotSpec(
                    "control_outcome",
                    SlotType.VECTOR,
                    Unit("outcome", "numeric"),
                    shape=("n_control",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="theorem_family",
                default="makarov_pointwise",
                description=(
                    "'lee_trimming_distributional', 'makarov_pointwise', 'mtr_headcount', "
                    "'mtr_theil', 'mtr_atkinson', 'mtr_gini_lorenz', 'sd_headcount', "
                    "'sd_theil', 'sd_atkinson', or 'sd_gini_lorenz'."
                ),
            ),
            ParameterSpec(
                name="functional",
                default="ite_tail_risk",
                description="DistributionalFunctional value to bound.",
            ),
            ParameterSpec(
                name="axis_values",
                default=(0.0,),
                description=(
                    "Grid values: thresholds, harm thresholds, quantiles, or Atkinson epsilons."
                ),
            ),
            ParameterSpec(name="target_potential_outcome", default="y1"),
            ParameterSpec(name="support_floor", default=None),
            ParameterSpec(name="support_ceiling", default=None),
            ParameterSpec(name="mean_floor", default=None),
            ParameterSpec(name="outcome_unit", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Stage 5.2 distributional bounds engine for Lee-trimming subgroup shifts "
            "and Makarov pointwise ITE tail/quantile risk under partial identification, "
            "plus MTR and FOSD inequality bounds for poverty headcount, Theil, "
            "Atkinson, and Gini."
        ),
        tags=frozenset({"causal", "bounds", "distributional", "partial-identification"}),
        citations=(
            "Lee, D.S. (2009). Training, Wages, and Sample Selection: Estimating Sharp Bounds on Treatment Effects.",
            "Makarov, G.D. (1982). Estimates for the distribution function of a sum of two random variables.",
            "Fan, Y. & Park, S.S. (2010). Sharp Bounds on the Distribution of Treatment Effects.",
            "Firpo, S. & Ridder, G. (2019). Partial Identification of the Treatment Effect Distribution.",
            "Manski, C.F. (1997). Monotone Treatment Response. Econometrica.",
            "Fan, Y. & Zhu, Y. (2009). Partial Identification of Functionals of the Joint Distribution.",
        ),
        equations={
            "lee_cdf_lower": "max(0, (F_1obs(y)-alpha)/(1-alpha))",
            "lee_cdf_upper": "min(1, F_1obs(y)/(1-alpha))",
            "makarov_event": "min/max over couplings with fixed marginals of P(Y1-Y0 <= s)",
            "theil_t": "E[(Y/mu) log(Y/mu)]",
            "atkinson": "1 - EDE(Y; epsilon)/E[Y]",
            "gini": "1 - 2 * integral_0^1 L(p) dp",
            "fosd": "F_Y1(t) <= F_Y0(t) for all thresholds t",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy", "scipy"),
        when_to_use=(
            "Need certified distributional bounds for tail risk or quantile shifts when "
            "full counterfactual/joint distributions are not identified."
        ),
        when_not_to_use=(
            "Need a causal OT coupling itself; this method only bounds marginal or ITE "
            "functionals and keeps coupling claims separate."
        ),
        output_interpretation=(
            "Returns an ir.distributional_bounds_bundle payload with explicit assumptions "
            "and sharpness status; multi-point Makarov results are pointwise, not uniformly sharp, "
            "FOSD inequality routes are pointwise-outer by default, and Gini remains outer "
            "without a uniform Lorenz certificate."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        family = str(params.get("theorem_family", params.get("method_family", "makarov_pointwise")))
        functional = DistributionalFunctional(str(params.get("functional", "ite_tail_risk")))
        outcome_unit_raw = params.get("outcome_unit")
        outcome_unit = str(outcome_unit_raw) if outcome_unit_raw is not None else None
        target_potential_outcome = str(params.get("target_potential_outcome", "y1"))
        axis = _axis_values(
            params,
            names=(
                "axis_values",
                "thresholds",
                "quantiles",
                "harm_thresholds",
                "poverty_lines",
                "poverty_line",
                "atkinson_epsilons",
                "atkinson_epsilon",
                "epsilons",
                "epsilon",
            ),
            default=(0.0,),
        )
        certificate_payload: dict[str, Any] | None = None
        support_floor_raw = params.get("support_floor")
        support_floor = float(support_floor_raw) if support_floor_raw is not None else None
        support_ceiling_raw = params.get("support_ceiling")
        support_ceiling = float(support_ceiling_raw) if support_ceiling_raw is not None else None
        mean_floor_raw = params.get("mean_floor")
        mean_floor = float(mean_floor_raw) if mean_floor_raw is not None else None

        if family == "lee_trimming_distributional":
            if not {"outcome", "treatment", "selected"}.issubset(state):
                raise ValueError(
                    "lee_trimming_distributional requires outcome, treatment, selected"
                )
            bundle = lee_trimming_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                selected=state["selected"],
                functional=functional,
                axis_values=axis,
                outcome_unit=outcome_unit,
            )
        elif family == "mtr_headcount":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("mtr_headcount requires outcome and treatment")
            bundle, certificate = mtr_headcount_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "sd_headcount":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("sd_headcount requires outcome and treatment")
            bundle, certificate = sd_headcount_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "mtr_theil":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("mtr_theil requires outcome and treatment")
            bundle, certificate = mtr_theil_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                support_floor=support_floor,
                support_ceiling=support_ceiling,
                mean_floor=mean_floor,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "sd_theil":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("sd_theil requires outcome and treatment")
            bundle, certificate = sd_theil_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                support_floor=support_floor,
                support_ceiling=support_ceiling,
                mean_floor=mean_floor,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "mtr_atkinson":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("mtr_atkinson requires outcome and treatment")
            bundle, certificate = mtr_atkinson_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                support_floor=support_floor,
                support_ceiling=support_ceiling,
                mean_floor=mean_floor,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "sd_atkinson":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("sd_atkinson requires outcome and treatment")
            bundle, certificate = sd_atkinson_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                support_floor=support_floor,
                support_ceiling=support_ceiling,
                mean_floor=mean_floor,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "mtr_gini_lorenz":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("mtr_gini_lorenz requires outcome and treatment")
            bundle, certificate = mtr_gini_lorenz_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                support_floor=support_floor,
                support_ceiling=support_ceiling,
                mean_floor=mean_floor,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "sd_gini_lorenz":
            if not {"outcome", "treatment"}.issubset(state):
                raise ValueError("sd_gini_lorenz requires outcome and treatment")
            bundle, certificate = sd_gini_lorenz_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                functional=functional,
                axis_values=axis,
                target_potential_outcome=target_potential_outcome,
                support_floor=support_floor,
                support_ceiling=support_ceiling,
                mean_floor=mean_floor,
                outcome_unit=outcome_unit,
            )
            certificate_payload = certificate.model_dump(mode="json")
        elif family == "makarov_pointwise":
            treated_outcome, control_outcome = _marginal_outcomes_from_state(state)
            bundle = makarov_distributional_bounds(
                treated_outcome=treated_outcome,
                control_outcome=control_outcome,
                functional=functional,
                axis_values=axis,
                outcome_unit=outcome_unit,
            )
        else:
            raise ValueError(
                "theorem_family must be 'lee_trimming_distributional', "
                "'makarov_pointwise', 'mtr_headcount', 'mtr_theil', "
                "'mtr_atkinson', 'mtr_gini_lorenz', 'sd_headcount', "
                "'sd_theil', 'sd_atkinson', or 'sd_gini_lorenz'"
            )

        return {
            "result": {
                "distributional_bounds_bundle": bundle.model_dump(mode="json"),
                "distributional_dual_certificate_payload": certificate_payload,
                "functional": bundle.functional.value,
                "estimand_type": bundle.estimand_type,
                "sharpness_status": bundle.sharpness_status,
                "point_identified": bundle.point_identified,
            }
        }


__all__ = [
    "ATKINSON_POSITIVITY_WARNING",
    "EMPIRICAL_SUPPORT_FALLBACK_WARNING",
    "GINI_UNIFORM_CERTIFICATE_WARNING",
    "POINTWISE_NON_UNIFORM_WARNING",
    "STOCHASTIC_DOMINANCE_OUTER_WARNING",
    "DistributionalBoundsEngineMethod",
    "lee_trimming_distributional_bounds",
    "makarov_distributional_bounds",
    "mtr_atkinson_distributional_bounds",
    "mtr_gini_lorenz_distributional_bounds",
    "mtr_headcount_distributional_bounds",
    "mtr_theil_distributional_bounds",
    "sd_atkinson_distributional_bounds",
    "sd_gini_lorenz_distributional_bounds",
    "sd_headcount_distributional_bounds",
    "sd_theil_distributional_bounds",
]
