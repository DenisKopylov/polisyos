"""Distributional partial-identification bounds for Stage 5.2.

Implements the two theorem families promoted by the research result plan:

* Lee-style monotone-selection trimming for always-responder marginal functionals.
* Makarov/Frechet bounds for individual-treatment-effect distributional functionals
  with fixed marginal laws and unknown copula.
"""
from __future__ import annotations

import math
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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
    DistributionalFunctional,
    FunctionalBounds,
    GridAxis,
)

POINTWISE_NON_UNIFORM_WARNING = (
    "Pointwise distributional bounds are not guaranteed to be uniformly sharp across "
    "multiple grid points; do not interpret the envelope as a sharp process-level band."
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
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("selected", SlotType.VECTOR, Unit("selection", "binary"), shape=("n_obs",)),
                SlotSpec("treated_outcome", SlotType.VECTOR, Unit("outcome", "numeric"), shape=("n_treated",)),
                SlotSpec("control_outcome", SlotType.VECTOR, Unit("outcome", "numeric"), shape=("n_control",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="theorem_family",
                default="makarov_pointwise",
                description="'lee_trimming_distributional' or 'makarov_pointwise'.",
            ),
            ParameterSpec(
                name="functional",
                default="ite_tail_risk",
                description="DistributionalFunctional value to bound.",
            ),
            ParameterSpec(
                name="axis_values",
                default=(0.0,),
                description="Grid values: thresholds, harm thresholds, or quantiles.",
            ),
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
            "and Makarov pointwise ITE tail/quantile risk under partial identification."
        ),
        tags=frozenset({"causal", "bounds", "distributional", "partial-identification"}),
        citations=(
            "Lee, D.S. (2009). Training, Wages, and Sample Selection: Estimating Sharp Bounds on Treatment Effects.",
            "Makarov, G.D. (1982). Estimates for the distribution function of a sum of two random variables.",
            "Fan, Y. & Park, S.S. (2010). Sharp Bounds on the Distribution of Treatment Effects.",
            "Firpo, S. & Ridder, G. (2019). Partial Identification of the Treatment Effect Distribution.",
        ),
        equations={
            "lee_cdf_lower": "max(0, (F_1obs(y)-alpha)/(1-alpha))",
            "lee_cdf_upper": "min(1, F_1obs(y)/(1-alpha))",
            "makarov_event": "min/max over couplings with fixed marginals of P(Y1-Y0 <= s)",
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
            "and sharpness status; multi-point Makarov results are pointwise, not uniformly sharp."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        family = str(params.get("theorem_family", params.get("method_family", "makarov_pointwise")))
        functional = DistributionalFunctional(str(params.get("functional", "ite_tail_risk")))
        outcome_unit_raw = params.get("outcome_unit")
        outcome_unit = str(outcome_unit_raw) if outcome_unit_raw is not None else None
        axis = _axis_values(
            params,
            names=("axis_values", "thresholds", "quantiles", "harm_thresholds"),
            default=(0.0,),
        )

        if family == "lee_trimming_distributional":
            if not {"outcome", "treatment", "selected"}.issubset(state):
                raise ValueError("lee_trimming_distributional requires outcome, treatment, selected")
            bundle = lee_trimming_distributional_bounds(
                outcome=state["outcome"],
                treatment=state["treatment"],
                selected=state["selected"],
                functional=functional,
                axis_values=axis,
                outcome_unit=outcome_unit,
            )
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
                "theorem_family must be 'lee_trimming_distributional' or 'makarov_pointwise'"
            )

        return {
            "result": {
                "distributional_bounds_bundle": bundle.model_dump(mode="json"),
                "functional": bundle.functional.value,
                "estimand_type": bundle.estimand_type,
                "sharpness_status": bundle.sharpness_status,
                "point_identified": bundle.point_identified,
            }
        }


__all__ = [
    "DistributionalBoundsEngineMethod",
    "POINTWISE_NON_UNIFORM_WARNING",
    "lee_trimming_distributional_bounds",
    "makarov_distributional_bounds",
]
