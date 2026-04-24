"""Causal inequality decomposition under endogenous group composition.

The estimator implements a conservative v1 of the interventional law approach
described in the Phase 3 research bundle. It targets scalar inequality
functionals whose counterfactual value is pinned down by transported moments,
namely Theil-T and generalized entropy GE(alpha).

The implementation is intentionally honest:

* point identification is attempted only when every observed group appears in
  both regime arms and the estimated overlap diagnostics clear the floor;
* near-positivity can be handled by an explicit trimmed estimand;
* hard support mismatch falls back to interval bounds plus a typed
  ``NegativeCertificate``.
"""

from __future__ import annotations

from collections.abc import Mapping
from statistics import NormalDist
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    DistributionalBoundsBundle,
    DistributionalBoundsMethodSummary,
    DistributionalFunctional,
    DistributionalFunctionalParameters,
    FunctionalBounds,
    GridAxis,
)
from polisyos.ir.analytics.endogenous_inequality import (
    CounterfactualLawEstimate,
    CounterfactualLawLabel,
    EndogenousGroupDecompositionStatus,
    EndogenousGroupInequalityDecompositionResult,
    ReferencePopulation,
    ScalarEstimandEstimate,
)
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
)

ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM = "interventional_endogenous_group_decomposition_v1"


def _output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("report", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            SlotSpec("decomposition_result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec("bounds_bundle", SlotType.SCALAR, Unit("bounds", "json")),
            SlotSpec(
                "distributional_bounds_bundle",
                SlotType.SCALAR,
                Unit("distributional_bounds", "json"),
            ),
            SlotSpec("negative_certificate", SlotType.SCALAR, Unit("negative_certificate", "json")),
        }
    )


def _to_numeric_vector(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D vector")
    if arr.size == 0:
        raise ValueError(f"{name} must not be empty")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _to_group_vector(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        raise ValueError("group must be a 1D vector")
    if arr.size == 0:
        raise ValueError("group must not be empty")
    return arr


def _to_matrix(value: Any, *, name: str, n_obs: int) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if arr.shape[0] != n_obs:
        raise ValueError(f"{name} must have {n_obs} rows")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _encode_groups(group: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
    labels = tuple(str(item) for item in np.unique(group))
    mapping = {label: idx for idx, label in enumerate(labels)}
    encoded = np.asarray([mapping[str(item)] for item in group], dtype=int)
    return encoded, labels


def _fit_scaler(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(X, axis=0) if X.size else np.zeros(X.shape[1], dtype=float)
    std = np.std(X, axis=0) if X.size else np.ones(X.shape[1], dtype=float)
    std = np.where(std <= 1.0e-8, 1.0, std)
    return mean, std


def _apply_scaler(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    if X.size == 0:
        return X.astype(float)
    return (X - mean) / std


def _augment_intercept(X: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(X.shape[0], dtype=float), X])


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def _fit_binary_logit(
    X: np.ndarray,
    y: np.ndarray,
    *,
    ridge: float = 1.0e-4,
    max_iter: int = 80,
) -> tuple[str, np.ndarray | float]:
    y = np.asarray(y, dtype=float)
    positives = float(np.sum(y))
    if positives <= 0.0:
        return "constant", 0.0
    if positives >= float(y.size):
        return "constant", 1.0
    X_aug = _augment_intercept(X)
    beta = np.zeros(X_aug.shape[1], dtype=float)
    penalty = ridge * np.eye(X_aug.shape[1], dtype=float)
    penalty[0, 0] = 0.0
    for _ in range(max_iter):
        p = _sigmoid(X_aug @ beta)
        weights = np.maximum(p * (1.0 - p), 1.0e-6)
        grad = X_aug.T @ (y - p) - penalty @ beta
        hessian = X_aug.T @ (weights[:, None] * X_aug) + penalty
        try:
            step = np.linalg.solve(hessian, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, grad, rcond=None)[0]
        beta = beta + step
        if float(np.max(np.abs(step))) < 1.0e-8:
            break
    return "linear", beta


def _predict_binary_logit(X: np.ndarray, model: tuple[str, np.ndarray | float]) -> np.ndarray:
    kind, payload = model
    if kind == "constant":
        return np.full(X.shape[0], float(payload), dtype=float)
    beta = np.asarray(payload, dtype=float)
    return _sigmoid(_augment_intercept(X) @ beta)


def _fit_group_probability_models(
    X: np.ndarray,
    group: np.ndarray,
    *,
    n_groups: int,
) -> tuple[tuple[tuple[str, np.ndarray | float], ...], np.ndarray]:
    frequencies = np.bincount(group, minlength=n_groups).astype(float)
    frequencies = frequencies / max(float(np.sum(frequencies)), 1.0)
    models: list[tuple[str, np.ndarray | float]] = []
    for group_id in range(n_groups):
        target = (group == group_id).astype(float)
        models.append(_fit_binary_logit(X, target))
    return tuple(models), frequencies


def _predict_group_probabilities(
    X: np.ndarray,
    models: tuple[tuple[str, np.ndarray | float], ...],
    frequencies: np.ndarray,
) -> np.ndarray:
    raw = np.column_stack([_predict_binary_logit(X, model) for model in models]).astype(float)
    raw = np.clip(raw, 0.0, 1.0)
    row_sums = np.sum(raw, axis=1, keepdims=True)
    fallback = np.broadcast_to(frequencies.reshape(1, -1), raw.shape)
    safe = np.where(row_sums > 1.0e-10, raw / row_sums, fallback)
    safe = np.clip(safe, 0.0, 1.0)
    safe_sums = np.sum(safe, axis=1, keepdims=True)
    return np.where(safe_sums > 1.0e-10, safe / safe_sums, fallback)


def _fit_linear_regression(
    X: np.ndarray,
    y: np.ndarray,
    *,
    ridge: float = 1.0e-6,
) -> tuple[str, np.ndarray | float]:
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return "constant", 0.0
    if X.shape[0] <= X.shape[1] + 1:
        return "constant", float(np.mean(y))
    X_aug = _augment_intercept(X)
    gram = X_aug.T @ X_aug
    ridge_matrix = ridge * np.eye(gram.shape[0], dtype=float)
    ridge_matrix[0, 0] = 0.0
    rhs = X_aug.T @ y
    try:
        beta = np.linalg.solve(gram + ridge_matrix, rhs)
    except np.linalg.LinAlgError:
        beta = np.linalg.lstsq(gram + ridge_matrix, rhs, rcond=None)[0]
    return "linear", beta


def _predict_linear_regression(X: np.ndarray, model: tuple[str, np.ndarray | float]) -> np.ndarray:
    kind, payload = model
    if kind == "constant":
        return np.full(X.shape[0], float(payload), dtype=float)
    beta = np.asarray(payload, dtype=float)
    return _augment_intercept(X) @ beta


def _fit_group_outcome_models(
    X: np.ndarray,
    outcome: np.ndarray,
    group: np.ndarray,
    *,
    n_groups: int,
) -> tuple[tuple[tuple[str, np.ndarray | float], ...], np.ndarray]:
    models: list[tuple[str, np.ndarray | float]] = []
    available = np.zeros(n_groups, dtype=bool)
    for group_id in range(n_groups):
        mask = group == group_id
        available[group_id] = bool(np.any(mask))
        models.append(_fit_linear_regression(X[mask], outcome[mask]))
    return tuple(models), available


def _predict_group_outcomes(
    X: np.ndarray,
    models: tuple[tuple[str, np.ndarray | float], ...],
) -> np.ndarray:
    return np.column_stack([_predict_linear_regression(X, model) for model in models]).astype(float)


def _z_value(confidence_level: float) -> float:
    return float(NormalDist().inv_cdf(0.5 + 0.5 * confidence_level))


def _confidence_interval(
    point_estimate: float,
    standard_error: float | None,
    *,
    confidence_level: float,
) -> tuple[float, float]:
    if standard_error is None or standard_error <= 0.0:
        return (float(point_estimate), float(point_estimate))
    z_value = _z_value(confidence_level)
    half_width = z_value * float(standard_error)
    return (float(point_estimate - half_width), float(point_estimate + half_width))


def _resolve_functional(
    params: Mapping[str, Any],
) -> tuple[DistributionalFunctional, float | None]:
    raw = str(params.get("functional", DistributionalFunctional.THEIL_T.value))
    if raw == DistributionalFunctional.THEIL_T.value:
        return DistributionalFunctional.THEIL_T, None
    if raw == DistributionalFunctional.GENERALIZED_ENTROPY.value:
        alpha = float(params.get("alpha", 1.0))
        return DistributionalFunctional.GENERALIZED_ENTROPY, alpha
    raise ValueError("functional must be 'theil_t' or 'generalized_entropy'")


def _shifted_outcome(outcome: np.ndarray, *, epsilon: float) -> np.ndarray:
    if np.any(outcome < 0.0):
        raise ValueError("outcome must be non-negative for inequality decomposition")
    return np.maximum(outcome, 0.0) + epsilon


def _transformed_outcome(
    shifted_outcome: np.ndarray,
    *,
    functional: DistributionalFunctional,
    alpha: float | None,
) -> np.ndarray:
    if functional is DistributionalFunctional.THEIL_T:
        return shifted_outcome * np.log(shifted_outcome)
    alpha_value = 1.0 if alpha is None else float(alpha)
    if abs(alpha_value) < 1.0e-12:
        return np.log(shifted_outcome)
    if abs(alpha_value - 1.0) < 1.0e-12:
        return shifted_outcome * np.log(shifted_outcome)
    return shifted_outcome**alpha_value


def _inequality_from_moments(
    mean_estimate: float,
    transformed_moment_estimate: float,
    *,
    functional: DistributionalFunctional,
    alpha: float | None,
) -> float:
    mu = max(float(mean_estimate), 1.0e-12)
    transformed = float(transformed_moment_estimate)
    if functional is DistributionalFunctional.THEIL_T:
        return float(transformed / mu - np.log(mu))
    alpha_value = 1.0 if alpha is None else float(alpha)
    if abs(alpha_value) < 1.0e-12:
        return float(np.log(mu) - transformed)
    if abs(alpha_value - 1.0) < 1.0e-12:
        return float(transformed / mu - np.log(mu))
    return float((transformed / (mu**alpha_value) - 1.0) / (alpha_value * (alpha_value - 1.0)))


def _inequality_gradient(
    mean_estimate: float,
    transformed_moment_estimate: float,
    *,
    functional: DistributionalFunctional,
    alpha: float | None,
) -> tuple[float, float]:
    mu = max(float(mean_estimate), 1.0e-12)
    transformed = float(transformed_moment_estimate)
    if functional is DistributionalFunctional.THEIL_T:
        return (
            float(-(transformed / (mu**2)) - (1.0 / mu)),
            float(1.0 / mu),
        )
    alpha_value = 1.0 if alpha is None else float(alpha)
    if abs(alpha_value) < 1.0e-12:
        return (float(1.0 / mu), -1.0)
    if abs(alpha_value - 1.0) < 1.0e-12:
        return (
            float(-(transformed / (mu**2)) - (1.0 / mu)),
            float(1.0 / mu),
        )
    return (
        float(-(transformed * (mu ** (-alpha_value - 1.0))) / (alpha_value - 1.0)),
        float((mu ** (-alpha_value)) / (alpha_value * (alpha_value - 1.0))),
    )


def _transformed_interval(
    lower: float,
    upper: float,
    *,
    functional: DistributionalFunctional,
    alpha: float | None,
) -> tuple[float, float]:
    if functional is DistributionalFunctional.THEIL_T:
        candidates = [lower * np.log(lower), upper * np.log(upper)]
        minimizer = float(np.exp(-1.0))
        if lower <= minimizer <= upper:
            candidates.append(-1.0 / np.e)
        return (float(min(candidates)), float(max(candidates)))
    alpha_value = 1.0 if alpha is None else float(alpha)
    if abs(alpha_value) < 1.0e-12:
        return (float(np.log(lower)), float(np.log(upper)))
    first = float(lower**alpha_value)
    second = float(upper**alpha_value)
    return (min(first, second), max(first, second))


def _law_interval_from_support(
    support: tuple[float, float],
    *,
    functional: DistributionalFunctional,
    alpha: float | None,
) -> tuple[float, float]:
    lower, upper = support
    transformed_lower, transformed_upper = _transformed_interval(
        lower,
        upper,
        functional=functional,
        alpha=alpha,
    )
    candidates = []
    for mean_candidate in (lower, upper):
        for transformed_candidate in (transformed_lower, transformed_upper):
            value = _inequality_from_moments(
                mean_candidate,
                transformed_candidate,
                functional=functional,
                alpha=alpha,
            )
            if np.isfinite(value):
                candidates.append(float(value))
    if not candidates:
        return (float("-inf"), float("inf"))
    return (float(min(candidates)), float(max(candidates)))


def _effect_interval(
    positive_interval: tuple[float, float],
    negative_interval: tuple[float, float],
) -> tuple[float, float]:
    return (
        float(positive_interval[0] - negative_interval[1]),
        float(positive_interval[1] - negative_interval[0]),
    )


def _add_intervals(
    first: tuple[float, float],
    second: tuple[float, float],
    *,
    scale: float = 1.0,
) -> tuple[float, float]:
    return (
        float(scale * (first[0] + second[0])),
        float(scale * (first[1] + second[1])),
    )


def _decomposition_bounds_bundle(
    *,
    functional: DistributionalFunctional,
    parameters: DistributionalFunctionalParameters,
    effect_intervals: Mapping[str, tuple[float, float]],
    law_intervals: Mapping[CounterfactualLawLabel, tuple[float, float]],
    support_mismatch: bool,
) -> DistributionalBoundsBundle:
    effect_order = (
        "total",
        "compositional",
        "structural",
        "shapley_compositional",
        "shapley_structural",
    )
    axis = GridAxis(
        axis_name="decomposition_effect",
        values=tuple(float(index) for index, _ in enumerate(effect_order)),
        unit="effect_index",
    )
    lower = tuple(float(effect_intervals[name][0]) for name in effect_order)
    upper = tuple(float(effect_intervals[name][1]) for name in effect_order)
    summary = DistributionalBoundsMethodSummary(
        method="support_interval_arithmetic",
        functional=functional,
        axis=axis,
        bounds=FunctionalBounds(
            lower=lower,
            upper=upper,
            notes={"effect_order": list(effect_order)},
        ),
        sharpness="outer_approx",
        assumptions_used=[
            "bounded_outcome_support",
            "interval_arithmetic_over_counterfactual_law_support",
        ],
        display_label="Endogenous-group inequality decomposition bounds",
        metadata={
            "theorem_family": ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            "support_mismatch": bool(support_mismatch),
            "law_intervals": {law.value: list(interval) for law, interval in law_intervals.items()},
        },
    )
    return DistributionalBoundsBundle(
        estimand_type="endogenous_group_inequality_decomposition",
        functional=functional,
        axis=axis,
        functional_parameters=parameters,
        method_summaries=[summary],
        rescue_actions=[
            "trim_to_overlap",
            "report_interval_bounds",
            "strengthen_support_or_mediator_exchangeability_design",
        ],
        warnings=[
            "Point decomposition is not identified on the requested support; use bounds or trim."
        ],
        metadata={
            "theorem_family": ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            "effect_order": list(effect_order),
        },
    )


def _effect_estimate(
    point_estimate: float,
    influence: np.ndarray,
    *,
    confidence_level: float,
    formula: str,
) -> ScalarEstimandEstimate:
    standard_error = (
        float(np.std(influence, ddof=1) / np.sqrt(influence.shape[0]))
        if influence.shape[0] > 1
        else 0.0
    )
    return ScalarEstimandEstimate(
        point_estimate=float(point_estimate),
        standard_error=max(0.0, standard_error),
        confidence_interval=_confidence_interval(
            float(point_estimate),
            max(0.0, standard_error),
            confidence_level=confidence_level,
        ),
        estimand_formula=formula,
    )


def _law_estimate(
    *,
    law: CounterfactualLawLabel,
    mean_score: np.ndarray,
    transformed_score: np.ndarray,
    functional: DistributionalFunctional,
    alpha: float | None,
    confidence_level: float,
    metadata: dict[str, Any] | None = None,
) -> tuple[CounterfactualLawEstimate, np.ndarray]:
    mean_estimate = float(np.mean(mean_score))
    transformed_estimate = float(np.mean(transformed_score))
    inequality_estimate = _inequality_from_moments(
        mean_estimate,
        transformed_estimate,
        functional=functional,
        alpha=alpha,
    )
    grad_mu, grad_transformed = _inequality_gradient(
        mean_estimate,
        transformed_estimate,
        functional=functional,
        alpha=alpha,
    )
    centered_mean = mean_score - mean_estimate
    centered_transformed = transformed_score - transformed_estimate
    influence = grad_mu * centered_mean + grad_transformed * centered_transformed
    standard_error = (
        float(np.std(influence, ddof=1) / np.sqrt(influence.shape[0]))
        if influence.shape[0] > 1
        else 0.0
    )
    estimate = CounterfactualLawEstimate(
        law=law,
        structure_from=int(law.value[2]),
        composition_from=int(law.value[3]),
        mean_estimate=mean_estimate,
        transformed_moment_estimate=transformed_estimate,
        inequality_estimate=inequality_estimate,
        standard_error=max(0.0, standard_error),
        confidence_interval=_confidence_interval(
            inequality_estimate,
            max(0.0, standard_error),
            confidence_level=confidence_level,
        ),
        metadata=dict(metadata or {}),
    )
    return estimate, influence


def _assumption_cards(
    *,
    trimmed: bool,
) -> tuple[CausalAssumptionCard, ...]:
    positivity_description = (
        "Overlap was restricted to the retained support region where the cross-fitted "
        "propensity and group-composition scores stayed above the configured floor."
        if trimmed
        else "Each required (D, G, X) configuration lies on observed support with positive probability."
    )
    return (
        CausalAssumptionCard(
            scope="estimation",
            status="identified_needed",
            theorem_family=ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            assumption_type="regime_exchangeability",
            description="(Y_{d,g}, G_d) is conditionally exchangeable with D given X.",
            testable=False,
        ),
        CausalAssumptionCard(
            scope="estimation",
            status="identified_needed",
            theorem_family=ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            assumption_type="mediator_exchangeability",
            description="Y_{d,g} is conditionally exchangeable with G given (D=d, X).",
            testable=False,
        ),
        CausalAssumptionCard(
            scope="estimation",
            status="identified_needed",
            theorem_family=ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            assumption_type="positivity",
            description=positivity_description,
            testable=True,
        ),
        CausalAssumptionCard(
            scope="estimation",
            status="identified_needed",
            theorem_family=ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            assumption_type="reference_population",
            description="Effects are standardized to the pooled observed covariate law Q_X.",
            testable=True,
        ),
    )


def _bounded_result(
    *,
    shifted_outcome: np.ndarray,
    treatment: np.ndarray,
    functional: DistributionalFunctional,
    alpha: float | None,
    overlap_fraction: float,
    retained_fraction: float,
    blocking_type: BlockingType,
    blocking_description: str,
    support_mismatch: bool,
) -> EndogenousGroupInequalityDecompositionResult:
    support_by_regime: dict[int, tuple[float, float]] = {}
    for regime in (0, 1):
        regime_values = shifted_outcome[treatment == regime]
        support_by_regime[regime] = (
            float(np.min(regime_values)),
            float(np.max(regime_values)),
        )
    law_intervals = {
        CounterfactualLawLabel.F_00: _law_interval_from_support(
            support_by_regime[0],
            functional=functional,
            alpha=alpha,
        ),
        CounterfactualLawLabel.F_01: _law_interval_from_support(
            support_by_regime[0],
            functional=functional,
            alpha=alpha,
        ),
        CounterfactualLawLabel.F_10: _law_interval_from_support(
            support_by_regime[1],
            functional=functional,
            alpha=alpha,
        ),
        CounterfactualLawLabel.F_11: _law_interval_from_support(
            support_by_regime[1],
            functional=functional,
            alpha=alpha,
        ),
    }
    total_interval = _effect_interval(
        law_intervals[CounterfactualLawLabel.F_11],
        law_intervals[CounterfactualLawLabel.F_00],
    )
    compositional_interval = _effect_interval(
        law_intervals[CounterfactualLawLabel.F_11],
        law_intervals[CounterfactualLawLabel.F_10],
    )
    structural_interval = _effect_interval(
        law_intervals[CounterfactualLawLabel.F_10],
        law_intervals[CounterfactualLawLabel.F_00],
    )
    shapley_compositional_interval = _add_intervals(
        _effect_interval(
            law_intervals[CounterfactualLawLabel.F_11],
            law_intervals[CounterfactualLawLabel.F_10],
        ),
        _effect_interval(
            law_intervals[CounterfactualLawLabel.F_01],
            law_intervals[CounterfactualLawLabel.F_00],
        ),
        scale=0.5,
    )
    shapley_structural_interval = _add_intervals(
        _effect_interval(
            law_intervals[CounterfactualLawLabel.F_11],
            law_intervals[CounterfactualLawLabel.F_01],
        ),
        _effect_interval(
            law_intervals[CounterfactualLawLabel.F_10],
            law_intervals[CounterfactualLawLabel.F_00],
        ),
        scale=0.5,
    )
    effect_intervals = {
        "total": total_interval,
        "compositional": compositional_interval,
        "structural": structural_interval,
        "shapley_compositional": shapley_compositional_interval,
        "shapley_structural": shapley_structural_interval,
    }

    partial_bounds = PartialIdentificationResult(
        method=BoundMethod.TRANSPORT_BOUNDS,
        lower_bound=float(compositional_interval[0]),
        upper_bound=float(compositional_interval[1]),
        confidence=1.0,
        assumptions_used=[
            "bounded_outcome_support",
            "interval_arithmetic_over_counterfactual_law_support",
        ],
        bounds_type="manski",
        display_label="Compositional effect bounds under support/overlap failure",
        solver_metadata={
            "theorem_family": ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
            "effect_intervals": {
                name: list(interval) for name, interval in effect_intervals.items()
            },
            "law_intervals": {law.value: list(interval) for law, interval in law_intervals.items()},
        },
    )
    negative_certificate = NegativeCertificate(
        blocking_type=blocking_type,
        blocking_description=blocking_description,
        technical_detail=(
            "The interventional law F^{d,d'} requires conditional laws Y|D=d,G=g,X=x "
            "for cells that are absent or numerically unsupported on the observed support."
        ),
        partial_bounds=partial_bounds,
        quantitative_diagnostics={
            "overlap_fraction": float(overlap_fraction),
            "retained_fraction": float(retained_fraction),
            "support_mismatch": bool(support_mismatch),
            "effect_intervals": {
                name: list(interval) for name, interval in effect_intervals.items()
            },
        },
        constructive_message=(
            "Either restrict the target estimand to an overlap-trimmed subpopulation, "
            "or report interval bounds instead of a point decomposition."
        ),
    )
    parameters = DistributionalFunctionalParameters(
        mean_floor=float(np.min(shifted_outcome)),
        generalized_entropy_alpha=alpha
        if functional is DistributionalFunctional.GENERALIZED_ENTROPY
        else None,
    )
    distributional_bounds_bundle = _decomposition_bounds_bundle(
        functional=functional,
        parameters=parameters,
        effect_intervals=effect_intervals,
        law_intervals=law_intervals,
        support_mismatch=support_mismatch,
    )
    return EndogenousGroupInequalityDecompositionResult(
        functional=functional,
        functional_parameters=parameters,
        reference_population=ReferencePopulation.POOLED_OBSERVED_X,
        status=EndogenousGroupDecompositionStatus.BOUNDED,
        overlap_fraction=float(overlap_fraction),
        retained_fraction=float(retained_fraction),
        assumption_cards=_assumption_cards(trimmed=False),
        bounds_bundle=negative_certificate.bounds_bundle,
        distributional_bounds_bundle=distributional_bounds_bundle,
        negative_certificate=negative_certificate,
        metadata={
            "support_mismatch": bool(support_mismatch),
            "effect_intervals": {
                name: list(interval) for name, interval in effect_intervals.items()
            },
        },
    )


@foundry_method(
    namespace="causal.distributional",
    version="1.0.0",
    tags={"causal", "distributional", "inequality", "theil", "generalized_entropy"},
)
class EndogenousGroupInequalityDecompositionEstimator:
    """Estimate causal inequality decomposition when group membership is endogenous."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="endogenous_group_decomposition",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec("group", SlotType.VECTOR, Unit("group", "label"), shape=("n_obs",)),
                SlotSpec(
                    "covariates",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_obs", "n_features"),
                ),
            }
        ),
        output_slots=_output_slots(),
        parameters=(
            ParameterSpec("functional", default=DistributionalFunctional.THEIL_T.value),
            ParameterSpec("alpha", default=1.0),
            ParameterSpec("n_folds", default=3, bounds=(2, 8)),
            ParameterSpec("min_propensity", default=0.05, bounds=(1.0e-4, 0.49)),
            ParameterSpec("min_group_probability", default=0.02, bounds=(1.0e-5, 0.49)),
            ParameterSpec("min_retained_fraction", default=0.6, bounds=(0.05, 1.0)),
            ParameterSpec("trim_to_overlap", default=False),
            ParameterSpec("y_epsilon", default=1.0e-6, bounds=(1.0e-12, None)),
            ParameterSpec("confidence_level", default=0.95, bounds=(0.8, 0.99)),
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
            "Interventional decomposition of inequality under endogenous group composition "
            "using cross-fitted transported moments."
        ),
        tags=frozenset(
            {
                "causal",
                "distributional",
                "inequality",
                "theil",
                "generalized_entropy",
                "mediation",
            }
        ),
        citations=(
            "Chernozhukov, V., Fernandez-Val, I. & Melly, B. (2013). Inference on counterfactual distributions.",
            "Tchetgen Tchetgen, E.J. & Shpitser, I. (2012). Semiparametric theory for causal mediation analysis.",
        ),
        equations={
            "transported_moment": ("theta_{d,d'} = E[sum_g m_d(g, X) e_{d'}(g | X)]"),
            "theil": "T(F) = E[Y log Y] / E[Y] - log(E[Y])",
            "decomposition": ("Delta_tot = (T_11 - T_10) + (T_10 - T_00)"),
        },
        assumptions={
            "regime_exchangeability": "(Y_{d,g}, G_d) is conditionally exchangeable with D given X.",
            "mediator_exchangeability": "Y_{d,g} is conditionally exchangeable with G given (D=d, X).",
            "positivity": "Required (D, G, X) configurations must be observed with positive probability.",
            "reference_population": "Effects are standardized to the pooled observed covariate law Q_X.",
        },
        when_to_use=(
            "When the analyst needs structural-versus-compositional decomposition of "
            "Theil-T or GE(alpha) and group membership is policy-sensitive or post-treatment."
        ),
        when_not_to_use=(
            "Do not use observed within/between Theil differences as a causal decomposition. "
            "This estimator also refuses point claims under hard support mismatch."
        ),
        typical_min_obs=160,
        output_interpretation=(
            "report.point_estimate is the total inequality effect; decomposition_result "
            "contains total, compositional, structural, and Shapley summaries."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        functional: DistributionalFunctional
        alpha: float | None
        try:
            outcome = _to_numeric_vector(state.get("outcome"), name="outcome")
            treatment = _to_numeric_vector(state.get("treatment"), name="treatment")
            group_raw = _to_group_vector(state.get("group"))
            covariates = _to_matrix(
                state.get("covariates"), name="covariates", n_obs=outcome.shape[0]
            )
            if treatment.shape[0] != outcome.shape[0] or group_raw.shape[0] != outcome.shape[0]:
                raise ValueError("outcome, treatment, and group must have the same length")
            if not np.all(np.isin(treatment, (0.0, 1.0))):
                raise ValueError("treatment must be binary")
            if int(np.sum(treatment == 0.0)) < 20 or int(np.sum(treatment == 1.0)) < 20:
                raise ValueError("need at least 20 observations in each treatment arm")
            functional, alpha = _resolve_functional(params)
            confidence_level = float(params.get("confidence_level", 0.95))
            epsilon = float(params.get("y_epsilon", 1.0e-6))
            shifted_outcome = _shifted_outcome(outcome, epsilon=epsilon)
            transformed_outcome = _transformed_outcome(
                shifted_outcome,
                functional=functional,
                alpha=alpha,
            )
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="endogenous_group_inequality_decomposition",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(
                    EndogenousGroupInequalityDecompositionEstimator.metadata.assumptions
                ),
            )
            return wrap_causal_output(
                report,
                warnings=[str(exc)],
                extras={
                    "decomposition_result": None,
                    "bounds_bundle": None,
                    "distributional_bounds_bundle": None,
                    "negative_certificate": None,
                },
            )

        group, group_labels = _encode_groups(group_raw)
        n_obs = outcome.shape[0]
        n_groups = len(group_labels)
        support_counts = np.zeros((2, n_groups), dtype=int)
        for regime in (0, 1):
            regime_mask = treatment.astype(int) == regime
            support_counts[regime] = np.bincount(group[regime_mask], minlength=n_groups)
        support_mismatch = bool(np.any(np.min(support_counts, axis=0) == 0))

        min_propensity = float(params.get("min_propensity", 0.05))
        min_group_probability = float(params.get("min_group_probability", 0.02))
        min_retained_fraction = float(params.get("min_retained_fraction", 0.6))
        trim_to_overlap = bool(params.get("trim_to_overlap", False))
        n_folds = int(params.get("n_folds", 3))
        if n_folds < 2:
            n_folds = 2
        n_folds = min(n_folds, max(2, n_obs))

        if support_mismatch:
            bounded = _bounded_result(
                shifted_outcome=shifted_outcome,
                treatment=treatment.astype(int),
                functional=functional,
                alpha=alpha,
                overlap_fraction=0.0,
                retained_fraction=0.0,
                blocking_type=BlockingType.SUPPORT_MISMATCH,
                blocking_description=(
                    "At least one observed group is absent in one regime arm, so "
                    "the transported conditional law cannot be evaluated on common support."
                ),
                support_mismatch=True,
            )
            report = build_failure_report(
                method=CausalMethod.ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason="support mismatch across (D, G) cells",
                estimand="endogenous_group_inequality_decomposition",
                sample_size=n_obs,
                n_treated=int(np.sum(treatment == 1.0)),
                n_control=int(np.sum(treatment == 0.0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(
                    EndogenousGroupInequalityDecompositionEstimator.metadata.assumptions
                ),
                metadata={
                    "functional": functional.value,
                    "group_labels": list(group_labels),
                    "support_counts": support_counts.tolist(),
                },
            )
            return wrap_causal_output(
                report,
                warnings=["support mismatch forced interval bounds"],
                extras={
                    "decomposition_result": bounded.model_dump(mode="json"),
                    "bounds_bundle": (
                        bounded.bounds_bundle.model_dump(mode="json")
                        if bounded.bounds_bundle is not None
                        else None
                    ),
                    "distributional_bounds_bundle": (
                        bounded.distributional_bounds_bundle.model_dump(mode="json")
                        if bounded.distributional_bounds_bundle is not None
                        else None
                    ),
                    "negative_certificate": (
                        bounded.negative_certificate.model_dump(mode="json")
                        if bounded.negative_certificate is not None
                        else None
                    ),
                },
            )

        law_scores: dict[CounterfactualLawLabel, dict[str, np.ndarray]] = {
            label: {
                "mean": np.zeros(n_obs, dtype=float),
                "transformed": np.zeros(n_obs, dtype=float),
            }
            for label in CounterfactualLawLabel
        }
        pi_hat = np.zeros(n_obs, dtype=float)
        e0_actual = np.zeros(n_obs, dtype=float)
        e1_actual = np.zeros(n_obs, dtype=float)

        seed = int(params.get("seed", params.get("__seed__", 0)))
        rng = np.random.default_rng(seed)
        fold_ids = np.array_split(rng.permutation(n_obs), n_folds)

        try:
            for eval_idx in fold_ids:
                train_mask = np.ones(n_obs, dtype=bool)
                train_mask[eval_idx] = False
                eval_mask = ~train_mask
                X_train = covariates[train_mask]
                X_eval = covariates[eval_mask]
                mean_train, std_train = _fit_scaler(X_train)
                X_train_scaled = _apply_scaler(X_train, mean_train, std_train)
                X_eval_scaled = _apply_scaler(X_eval, mean_train, std_train)

                treatment_train = treatment[train_mask]
                group_train = group[train_mask]
                shifted_train = shifted_outcome[train_mask]
                transformed_train = transformed_outcome[train_mask]

                treatment_model = _fit_binary_logit(X_train_scaled, treatment_train)
                propensity_eval = _predict_binary_logit(X_eval_scaled, treatment_model)
                propensity_eval = np.clip(propensity_eval, 1.0e-6, 1.0 - 1.0e-6)
                pi_hat[eval_mask] = propensity_eval

                group_probability_eval: dict[int, np.ndarray] = {}
                mean_outcome_eval: dict[int, np.ndarray] = {}
                transformed_outcome_eval: dict[int, np.ndarray] = {}

                for regime in (0, 1):
                    regime_mask = treatment_train.astype(int) == regime
                    if int(np.sum(regime_mask)) < 10:
                        raise ValueError(
                            "each cross-fit training fold needs support in both regimes"
                        )
                    regime_X = X_train_scaled[regime_mask]
                    regime_group = group_train[regime_mask]
                    regime_shifted = shifted_train[regime_mask]
                    regime_transformed = transformed_train[regime_mask]

                    probability_models, frequencies = _fit_group_probability_models(
                        regime_X,
                        regime_group,
                        n_groups=n_groups,
                    )
                    group_probability_eval[regime] = _predict_group_probabilities(
                        X_eval_scaled,
                        probability_models,
                        frequencies,
                    )
                    mean_models, _ = _fit_group_outcome_models(
                        regime_X,
                        regime_shifted,
                        regime_group,
                        n_groups=n_groups,
                    )
                    transformed_models, _ = _fit_group_outcome_models(
                        regime_X,
                        regime_transformed,
                        regime_group,
                        n_groups=n_groups,
                    )
                    mean_outcome_eval[regime] = _predict_group_outcomes(
                        X_eval_scaled,
                        mean_models,
                    )
                    transformed_outcome_eval[regime] = _predict_group_outcomes(
                        X_eval_scaled,
                        transformed_models,
                    )

                treatment_eval = treatment[eval_mask].astype(int)
                group_eval = group[eval_mask]
                shifted_eval = shifted_outcome[eval_mask]
                transformed_eval_values = transformed_outcome[eval_mask]
                pi_d_eval = {
                    1: propensity_eval,
                    0: 1.0 - propensity_eval,
                }

                e0_actual[eval_mask] = group_probability_eval[0][
                    np.arange(eval_idx.size), group_eval
                ]
                e1_actual[eval_mask] = group_probability_eval[1][
                    np.arange(eval_idx.size), group_eval
                ]

                law_map = {
                    CounterfactualLawLabel.F_00: (0, 0),
                    CounterfactualLawLabel.F_10: (1, 0),
                    CounterfactualLawLabel.F_11: (1, 1),
                    CounterfactualLawLabel.F_01: (0, 1),
                }
                for law_label, (structure_from, composition_from) in law_map.items():
                    composition_prob = group_probability_eval[composition_from]
                    mean_pred = mean_outcome_eval[structure_from]
                    transformed_pred = transformed_outcome_eval[structure_from]
                    pi_eval = pi_d_eval[structure_from]
                    actual_group_prob = group_probability_eval[structure_from][
                        np.arange(eval_idx.size),
                        group_eval,
                    ]
                    composition_actual_prob = composition_prob[
                        np.arange(eval_idx.size),
                        group_eval,
                    ]
                    base_mean = np.sum(composition_prob * mean_pred, axis=1)
                    base_transformed = np.sum(composition_prob * transformed_pred, axis=1)
                    augmentation_weight = np.zeros(eval_idx.size, dtype=float)
                    regime_matches = treatment_eval == structure_from
                    if np.any(regime_matches):
                        augmentation_weight[regime_matches] = composition_actual_prob[
                            regime_matches
                        ] / (
                            np.maximum(pi_eval[regime_matches], 1.0e-6)
                            * np.maximum(actual_group_prob[regime_matches], 1.0e-6)
                        )
                    mean_score = base_mean + augmentation_weight * (
                        shifted_eval - mean_pred[np.arange(eval_idx.size), group_eval]
                    )
                    transformed_score = base_transformed + augmentation_weight * (
                        transformed_eval_values
                        - transformed_pred[np.arange(eval_idx.size), group_eval]
                    )
                    law_scores[law_label]["mean"][eval_mask] = mean_score
                    law_scores[law_label]["transformed"][eval_mask] = transformed_score
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=str(exc),
                estimand="endogenous_group_inequality_decomposition",
                sample_size=n_obs,
                n_treated=int(np.sum(treatment == 1.0)),
                n_control=int(np.sum(treatment == 0.0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(
                    EndogenousGroupInequalityDecompositionEstimator.metadata.assumptions
                ),
            )
            return wrap_causal_output(
                report,
                warnings=[str(exc)],
                extras={
                    "decomposition_result": None,
                    "bounds_bundle": None,
                    "distributional_bounds_bundle": None,
                    "negative_certificate": None,
                },
            )

        overlap_mask = (
            (np.minimum(pi_hat, 1.0 - pi_hat) >= min_propensity)
            & (e0_actual >= min_group_probability)
            & (e1_actual >= min_group_probability)
        )
        overlap_fraction = float(np.mean(overlap_mask))
        retained_mask = overlap_mask if trim_to_overlap else np.ones(n_obs, dtype=bool)
        retained_fraction = float(np.mean(retained_mask))

        if (not trim_to_overlap and overlap_fraction < 1.0 - 1.0e-12) or (
            trim_to_overlap and retained_fraction < min_retained_fraction
        ):
            bounded = _bounded_result(
                shifted_outcome=shifted_outcome,
                treatment=treatment.astype(int),
                functional=functional,
                alpha=alpha,
                overlap_fraction=overlap_fraction,
                retained_fraction=retained_fraction,
                blocking_type=BlockingType.POSITIVITY_VIOLATION,
                blocking_description=(
                    "The estimated propensity or group-composition scores violate the configured "
                    "positivity floor on part of the observed support."
                ),
                support_mismatch=False,
            )
            report = build_failure_report(
                method=CausalMethod.ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason="positivity floor failed for the requested estimand",
                estimand="endogenous_group_inequality_decomposition",
                sample_size=n_obs,
                n_treated=int(np.sum(treatment == 1.0)),
                n_control=int(np.sum(treatment == 0.0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(
                    EndogenousGroupInequalityDecompositionEstimator.metadata.assumptions
                ),
                metadata={
                    "functional": functional.value,
                    "overlap_fraction": overlap_fraction,
                    "retained_fraction": retained_fraction,
                    "group_labels": list(group_labels),
                },
            )
            return wrap_causal_output(
                report,
                warnings=["positivity failure forced interval bounds"],
                extras={
                    "decomposition_result": bounded.model_dump(mode="json"),
                    "bounds_bundle": (
                        bounded.bounds_bundle.model_dump(mode="json")
                        if bounded.bounds_bundle is not None
                        else None
                    ),
                    "distributional_bounds_bundle": (
                        bounded.distributional_bounds_bundle.model_dump(mode="json")
                        if bounded.distributional_bounds_bundle is not None
                        else None
                    ),
                    "negative_certificate": (
                        bounded.negative_certificate.model_dump(mode="json")
                        if bounded.negative_certificate is not None
                        else None
                    ),
                },
            )

        law_estimates: dict[CounterfactualLawLabel, CounterfactualLawEstimate] = {}
        law_influence: dict[CounterfactualLawLabel, np.ndarray] = {}
        retained_scores = {
            law_label: {key: values[retained_mask] for key, values in score_map.items()}
            for law_label, score_map in law_scores.items()
        }
        for law_label in CounterfactualLawLabel:
            estimate, influence = _law_estimate(
                law=law_label,
                mean_score=retained_scores[law_label]["mean"],
                transformed_score=retained_scores[law_label]["transformed"],
                functional=functional,
                alpha=alpha,
                confidence_level=confidence_level,
                metadata={
                    "n_obs": int(np.sum(retained_mask)),
                    "overlap_fraction": overlap_fraction,
                },
            )
            law_estimates[law_label] = estimate
            law_influence[law_label] = influence

        total_effect = _effect_estimate(
            law_estimates[CounterfactualLawLabel.F_11].inequality_estimate
            - law_estimates[CounterfactualLawLabel.F_00].inequality_estimate,
            law_influence[CounterfactualLawLabel.F_11] - law_influence[CounterfactualLawLabel.F_00],
            confidence_level=confidence_level,
            formula="T(F_11) - T(F_00)",
        )
        compositional_effect = _effect_estimate(
            law_estimates[CounterfactualLawLabel.F_11].inequality_estimate
            - law_estimates[CounterfactualLawLabel.F_10].inequality_estimate,
            law_influence[CounterfactualLawLabel.F_11] - law_influence[CounterfactualLawLabel.F_10],
            confidence_level=confidence_level,
            formula="T(F_11) - T(F_10)",
        )
        structural_effect = _effect_estimate(
            law_estimates[CounterfactualLawLabel.F_10].inequality_estimate
            - law_estimates[CounterfactualLawLabel.F_00].inequality_estimate,
            law_influence[CounterfactualLawLabel.F_10] - law_influence[CounterfactualLawLabel.F_00],
            confidence_level=confidence_level,
            formula="T(F_10) - T(F_00)",
        )
        shapley_compositional_effect = _effect_estimate(
            0.5
            * (
                law_estimates[CounterfactualLawLabel.F_11].inequality_estimate
                - law_estimates[CounterfactualLawLabel.F_10].inequality_estimate
                + law_estimates[CounterfactualLawLabel.F_01].inequality_estimate
                - law_estimates[CounterfactualLawLabel.F_00].inequality_estimate
            ),
            0.5
            * (
                law_influence[CounterfactualLawLabel.F_11]
                - law_influence[CounterfactualLawLabel.F_10]
                + law_influence[CounterfactualLawLabel.F_01]
                - law_influence[CounterfactualLawLabel.F_00]
            ),
            confidence_level=confidence_level,
            formula="0.5 * ((T(F_11)-T(F_10)) + (T(F_01)-T(F_00)))",
        )
        shapley_structural_effect = _effect_estimate(
            0.5
            * (
                law_estimates[CounterfactualLawLabel.F_11].inequality_estimate
                - law_estimates[CounterfactualLawLabel.F_01].inequality_estimate
                + law_estimates[CounterfactualLawLabel.F_10].inequality_estimate
                - law_estimates[CounterfactualLawLabel.F_00].inequality_estimate
            ),
            0.5
            * (
                law_influence[CounterfactualLawLabel.F_11]
                - law_influence[CounterfactualLawLabel.F_01]
                + law_influence[CounterfactualLawLabel.F_10]
                - law_influence[CounterfactualLawLabel.F_00]
            ),
            confidence_level=confidence_level,
            formula="0.5 * ((T(F_11)-T(F_01)) + (T(F_10)-T(F_00)))",
        )

        result = EndogenousGroupInequalityDecompositionResult(
            functional=functional,
            functional_parameters=DistributionalFunctionalParameters(
                mean_floor=float(np.min(shifted_outcome)),
                generalized_entropy_alpha=alpha
                if functional is DistributionalFunctional.GENERALIZED_ENTROPY
                else None,
            ),
            reference_population=(
                ReferencePopulation.OVERLAP_TRIMMED_POOLED_X
                if trim_to_overlap and overlap_fraction < 1.0 - 1.0e-12
                else ReferencePopulation.POOLED_OBSERVED_X
            ),
            status=(
                EndogenousGroupDecompositionStatus.TRIMMED
                if trim_to_overlap and overlap_fraction < 1.0 - 1.0e-12
                else EndogenousGroupDecompositionStatus.IDENTIFIED
            ),
            laws=tuple(law_estimates[label] for label in CounterfactualLawLabel),
            total_effect=total_effect,
            compositional_effect=compositional_effect,
            structural_effect=structural_effect,
            shapley_compositional_effect=shapley_compositional_effect,
            shapley_structural_effect=shapley_structural_effect,
            overlap_fraction=overlap_fraction,
            retained_fraction=retained_fraction,
            assumption_cards=_assumption_cards(
                trimmed=bool(trim_to_overlap and overlap_fraction < 1.0 - 1.0e-12)
            ),
            metadata={
                "group_labels": list(group_labels),
                "support_counts": support_counts.tolist(),
                "mean_floor": float(np.min(shifted_outcome)),
            },
        )

        warnings: list[str] = []
        if result.status is EndogenousGroupDecompositionStatus.TRIMMED:
            warnings.append("result is identified only on the retained overlap-trimmed support")

        report = build_success_report(
            method=CausalMethod.ENDOGENOUS_GROUP_INEQUALITY_DECOMPOSITION,
            estimand="endogenous_group_inequality_decomposition",
            point_estimate=total_effect.point_estimate,
            confidence_interval=total_effect.confidence_interval
            or (
                total_effect.point_estimate,
                total_effect.point_estimate,
            ),
            inference_method="cross_fitted_transported_moments",
            sample_size=int(np.sum(retained_mask)),
            n_treated=int(np.sum(treatment[retained_mask] == 1.0)),
            n_control=int(np.sum(treatment[retained_mask] == 0.0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(EndogenousGroupInequalityDecompositionEstimator.metadata.assumptions),
            standard_error=total_effect.standard_error,
            method_params={
                "functional": functional.value,
                "alpha": alpha,
                "n_folds": n_folds,
                "min_propensity": min_propensity,
                "min_group_probability": min_group_probability,
                "trim_to_overlap": trim_to_overlap,
            },
            metadata={
                "theorem_family": ENDOGENOUS_GROUP_DECOMPOSITION_THEOREM,
                "functional": functional.value,
                "alpha": alpha,
                "overlap_fraction": overlap_fraction,
                "retained_fraction": retained_fraction,
                "group_labels": list(group_labels),
                "compositional_effect": compositional_effect.point_estimate,
                "structural_effect": structural_effect.point_estimate,
                "shapley_compositional_effect": shapley_compositional_effect.point_estimate,
                "shapley_structural_effect": shapley_structural_effect.point_estimate,
            },
        )
        return wrap_causal_output(
            report,
            warnings=warnings,
            extras={
                "decomposition_result": result.model_dump(mode="json"),
                "bounds_bundle": None,
                "distributional_bounds_bundle": None,
                "negative_certificate": None,
            },
        )


__all__ = ["EndogenousGroupInequalityDecompositionEstimator"]
