"""stochastic_policies — stochastic policy evaluators.

Implements policy value estimators for point-treatment settings under standard
exchangeability and positivity.

Supported policy inputs
-----------------------
1. Explicit per-observation treated probabilities via ``policy_probabilities``.
2. Incremental propensity-score interventions on the odds scale:
   ``incremental_odds(delta=...)``.
3. Deterministic ``treat_all`` / ``control_all`` policy expressions.
4. Continuous-policy plug-in estimation from:
   - ``policy_grid`` + ``policy_density``
   - ``policy_samples``
   - parsable Gaussian policies such as ``normal(mean=0, sd=1)``.

The doubly robust estimators intentionally focus on the practically important
binary-policy case. Generic continuous-treatment stochastic policies are
handled via a g-formula / plug-in estimator in the same namespace so the
execution layer can still target ``E_pi[Y]`` instead of only a dose-response
surface.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from statistics import NormalDist
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
from polisyos.foundry.methods.catalog.causal.treatment_effects import _logistic_propensity

_INCREMENTAL_POLICY_PATTERNS = (
    re.compile(
        r"incremental(?:_odds)?\s*\(\s*(?:delta\s*=\s*)?([-+]?[0-9]*\.?[0-9]+)\s*\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"odds(?:_shift)?\s*\(\s*(?:delta\s*=\s*)?([-+]?[0-9]*\.?[0-9]+)\s*\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"incremental(?:_odds)?\s*:\s*([-+]?[0-9]*\.?[0-9]+)",
        re.IGNORECASE,
    ),
)
_GAUSSIAN_POLICY_PATTERNS = (
    re.compile(
        r"(?:normal|gaussian|n)\s*\(\s*(?:mean|mu)\s*=\s*"
        r"([-+]?[0-9]*\.?[0-9]+)\s*,\s*(?:sd|sigma|std)\s*=\s*"
        r"([-+]?[0-9]*\.?[0-9]+)\s*\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:normal|gaussian|n)\s*\(\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*"
        r"([-+]?[0-9]*\.?[0-9]+)\s*\)",
        re.IGNORECASE,
    ),
)
_DETERMINISTIC_TREAT_ALL = {
    "1",
    "do(1)",
    "treat_all",
    "always_treat",
    "always_treated",
}
_DETERMINISTIC_CONTROL_ALL = {
    "0",
    "do(0)",
    "control_all",
    "always_control",
    "never_treat",
}


def _result_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec(
                "policy_weights", SlotType.VECTOR, Unit("weight", "importance"), shape=("n_obs",)
            ),
        }
    )


def _policy_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")
            ),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }
    )


def _general_policy_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")
            ),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "value"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }
    )


def _normal_quantile(confidence_level: float) -> float:
    confidence_level = float(np.clip(confidence_level, 1e-6, 1.0 - 1e-6))
    return float(NormalDist().inv_cdf(0.5 + confidence_level / 2.0))


def _extract_policy_inputs(
    state: Mapping[str, Any],
    *,
    binary_only: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_key = "X" if "X" in state else "covariates"
    if x_key not in state:
        raise ValueError("policy estimators require either 'X' or 'covariates' in state")
    X = np.asarray(state[x_key], dtype=float)
    T = np.asarray(state["treatment"], dtype=float).reshape(-1)
    Y = np.asarray(state["outcome"], dtype=float).reshape(-1)
    if X.ndim == 1:
        X = X[:, None]
    if X.ndim != 2:
        raise ValueError("covariates/X must be a 2D array")
    if T.shape[0] != X.shape[0] or Y.shape[0] != X.shape[0]:
        raise ValueError("X, treatment, and outcome must have matching first dimension")
    if binary_only and not np.isin(T, [0.0, 1.0]).all():
        raise ValueError(
            "causal.stochastic.policy_* currently supports binary treatment only; "
            "use causal.stochastic.policy_plugin or continuous-treatment estimators "
            "for continuous or multi-valued exposure."
        )
    return X, T, Y


def _fit_linear_outcome_predictions(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    feat_all = np.column_stack([np.ones(len(X)), X])

    def _fit_for_group(mask: np.ndarray) -> np.ndarray:
        if int(np.sum(mask)) < feat_all.shape[1]:
            beta, *_ = np.linalg.lstsq(feat_all, Y, rcond=None)
            return beta
        beta, *_ = np.linalg.lstsq(feat_all[mask], Y[mask], rcond=None)
        return beta

    beta0 = _fit_for_group(T <= 0.5)
    beta1 = _fit_for_group(T > 0.5)
    mu0 = feat_all @ beta0
    mu1 = feat_all @ beta1
    return np.asarray(mu0, dtype=float), np.asarray(mu1, dtype=float)


def _parse_incremental_delta(policy_expr: str | None) -> float | None:
    if not policy_expr:
        return None
    for pattern in _INCREMENTAL_POLICY_PATTERNS:
        match = pattern.search(policy_expr)
        if match is not None:
            return float(match.group(1))
    return None


def _parse_gaussian_policy_expr(policy_expr: str | None) -> tuple[float, float] | None:
    if not policy_expr:
        return None
    for pattern in _GAUSSIAN_POLICY_PATTERNS:
        match = pattern.search(policy_expr)
        if match is not None:
            mean = float(match.group(1))
            sd = float(match.group(2))
            if sd <= 0.0:
                raise ValueError("Gaussian stochastic policy must have sd > 0")
            return mean, sd
    return None


def _policy_family_from_expr(policy_expr: str | None) -> str | None:
    expr = str(policy_expr or "").strip().lower()
    if not expr:
        return None
    if expr in _DETERMINISTIC_TREAT_ALL:
        return "treat_all"
    if expr in _DETERMINISTIC_CONTROL_ALL:
        return "control_all"
    if _parse_incremental_delta(expr) is not None:
        return "incremental_odds"
    if _parse_gaussian_policy_expr(expr) is not None:
        return "gaussian"
    return None


def _resolve_policy_probabilities(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    propensity: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    n = propensity.shape[0]
    if "policy_probabilities" in state:
        raw = np.asarray(state["policy_probabilities"], dtype=float)
        if raw.ndim == 1:
            if raw.shape[0] != n:
                raise ValueError("policy_probabilities length must equal n_obs")
            p1 = raw
        elif raw.ndim == 2 and raw.shape == (n, 2):
            p1 = raw[:, 1]
        else:
            raise ValueError("policy_probabilities must have shape (n,) or (n, 2)")
        return np.clip(p1, 0.0, 1.0), {
            "policy_family": "explicit_probabilities",
            "policy_source": "state.policy_probabilities",
        }

    policy_expr = str(params.get("policy_expr", "") or "").strip()
    family = _policy_family_from_expr(policy_expr)
    if family == "treat_all":
        return np.ones(n, dtype=float), {
            "policy_family": family,
            "policy_source": "params.policy_expr",
        }
    if family == "control_all":
        return np.zeros(n, dtype=float), {
            "policy_family": family,
            "policy_source": "params.policy_expr",
        }
    incremental_delta = params.get("incremental_delta", None)
    if incremental_delta is None:
        incremental_delta = _parse_incremental_delta(policy_expr)
    if incremental_delta is not None:
        delta = float(incremental_delta)
        if delta <= 0.0:
            raise ValueError("incremental odds delta must be strictly positive")
        numer = delta * propensity
        p1 = numer / np.clip((1.0 - propensity) + numer, 1e-12, None)
        return np.clip(p1, 0.0, 1.0), {
            "policy_family": "incremental_odds",
            "policy_source": "params.policy_expr",
            "incremental_delta": delta,
        }

    raise ValueError(
        "Unsupported stochastic policy specification. Provide per-row "
        "'policy_probabilities' or use policy_expr in {'treat_all', "
        "'control_all', 'incremental_odds(delta=...)'}."
    )


def _policy_weights(
    treatment: np.ndarray,
    propensity: np.ndarray,
    policy_prob_treated: np.ndarray,
    *,
    min_weight: float,
    max_weight: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    raw = np.where(
        treatment > 0.5,
        policy_prob_treated / np.clip(propensity, 1e-6, 1.0),
        (1.0 - policy_prob_treated) / np.clip(1.0 - propensity, 1e-6, 1.0),
    )
    clipped = np.clip(raw, min_weight, max_weight)
    n_clipped = int(np.sum(np.abs(raw - clipped) > 1e-12))
    return raw, clipped, n_clipped


def _effect_summary_from_scores(
    scores: np.ndarray,
    *,
    confidence_level: float,
) -> tuple[float, float, float, float, float, float]:
    point = float(np.mean(scores))
    eif = np.asarray(scores - point, dtype=float)
    if eif.size > 1:
        se = float(np.std(eif, ddof=1) / np.sqrt(eif.size))
        eif_sd = float(np.std(eif, ddof=1))
    else:
        se = 0.0
        eif_sd = 0.0
    z = _normal_quantile(confidence_level)
    return point, se, point - z * se, point + z * se, float(np.mean(eif)), eif_sd


def _normal_pdf(x: np.ndarray, mean: np.ndarray, sd: float) -> np.ndarray:
    z = (x - mean) / max(sd, 1e-12)
    return np.exp(-0.5 * z**2) / max(sd * np.sqrt(2.0 * np.pi), 1e-12)


def _fit_continuous_outcome_surface(
    X: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
) -> np.ndarray:
    features = np.column_stack([np.ones(len(X)), treatment, treatment**2, X])
    beta, *_ = np.linalg.lstsq(features, outcome, rcond=None)
    return np.asarray(beta, dtype=float)


def _predict_continuous_outcome_surface(
    beta: np.ndarray,
    X: np.ndarray,
    policy_values: np.ndarray | float,
) -> np.ndarray:
    policy_arr = np.asarray(policy_values, dtype=float)
    base = beta[0] + X @ beta[3:]
    if policy_arr.ndim == 0:
        return base + beta[1] * policy_arr + beta[2] * policy_arr**2
    if policy_arr.ndim == 1:
        if policy_arr.shape[0] == X.shape[0]:
            return base + beta[1] * policy_arr + beta[2] * policy_arr**2
        return base[:, None] + beta[1] * policy_arr[None, :] + beta[2] * (policy_arr[None, :] ** 2)
    if policy_arr.ndim == 2:
        return base[:, None] + beta[1] * policy_arr + beta[2] * (policy_arr**2)
    raise ValueError("policy_values must be scalar, vector, or matrix")


def _fit_gaussian_treatment_density(
    X: np.ndarray,
    treatment: np.ndarray,
) -> tuple[np.ndarray, float]:
    features = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(features, treatment, rcond=None)
    residual = treatment - features @ beta
    sigma = float(max(np.std(residual, ddof=1), 1e-6))
    return np.asarray(beta, dtype=float), sigma


def _predict_gaussian_treatment_density(
    beta: np.ndarray,
    sigma: float,
    X: np.ndarray,
    policy_values: np.ndarray | float,
) -> np.ndarray:
    features = np.column_stack([np.ones(len(X)), X])
    mean = features @ beta
    values = np.asarray(policy_values, dtype=float)
    if values.ndim == 0:
        return _normal_pdf(np.full(len(X), float(values)), mean, sigma)
    if values.ndim == 1:
        if values.shape[0] == X.shape[0]:
            return _normal_pdf(values, mean, sigma)
        tiled_mean = np.broadcast_to(mean[:, None], (len(X), values.shape[0]))
        return _normal_pdf(np.broadcast_to(values[None, :], tiled_mean.shape), tiled_mean, sigma)
    if values.ndim == 2:
        tiled_mean = np.broadcast_to(mean[:, None], values.shape)
        return _normal_pdf(values, tiled_mean, sigma)
    raise ValueError("policy_values must be scalar, vector, or matrix")


def _normalize_policy_density(
    density: np.ndarray,
) -> np.ndarray:
    if density.ndim == 1:
        total = float(np.sum(np.clip(density, 0.0, None)))
        return np.clip(density, 0.0, None) / max(total, 1e-12)
    clipped = np.clip(density, 0.0, None)
    totals = np.sum(clipped, axis=1, keepdims=True)
    return clipped / np.clip(totals, 1e-12, None)


def _resolve_continuous_policy(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    treatment: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any], np.ndarray | None]:
    n = treatment.shape[0]
    if "policy_samples" in state:
        raw = np.asarray(state["policy_samples"], dtype=float)
        if raw.ndim == 1:
            samples = np.broadcast_to(raw[None, :], (n, raw.shape[0]))
        elif raw.ndim == 2 and raw.shape[0] == n:
            samples = raw
        else:
            raise ValueError("policy_samples must have shape (n_draws,) or (n_obs, n_draws)")
        return (
            samples,
            {
                "policy_family": "sampled_policy",
                "policy_source": "state.policy_samples",
                "n_integration_points": int(samples.shape[1]),
            },
            None,
        )

    policy_expr = str(params.get("policy_expr", "") or "").strip()
    if "policy_grid" in state and "policy_density" in state:
        grid = np.asarray(state["policy_grid"], dtype=float).reshape(-1)
        density_raw = np.asarray(state["policy_density"], dtype=float)
        if density_raw.ndim == 1:
            if density_raw.shape[0] != grid.shape[0]:
                raise ValueError("policy_density and policy_grid must have matching length")
            density = np.broadcast_to(density_raw[None, :], (n, grid.shape[0]))
        elif density_raw.ndim == 2 and density_raw.shape == (n, grid.shape[0]):
            density = density_raw
        else:
            raise ValueError("policy_density must have shape (n_grid,) or (n_obs, n_grid)")
        normalized = _normalize_policy_density(density)
        density_at_observed = np.asarray(
            [np.interp(treatment[i], grid, normalized[i], left=0.0, right=0.0) for i in range(n)],
            dtype=float,
        )
        return (
            normalized,
            {
                "policy_family": "explicit_density_grid",
                "policy_source": "state.policy_density",
                "n_integration_points": int(grid.shape[0]),
                "policy_grid_min": float(np.min(grid)),
                "policy_grid_max": float(np.max(grid)),
                "policy_grid": grid.tolist(),
            },
            density_at_observed,
        )

    gaussian_policy = _parse_gaussian_policy_expr(policy_expr)
    if gaussian_policy is not None:
        mean, sd = gaussian_policy
        n_grid = int(params.get("policy_integration_points", 51))
        grid = np.linspace(mean - 4.0 * sd, mean + 4.0 * sd, max(n_grid, 11))
        density = _normalize_policy_density(_normal_pdf(grid, np.full_like(grid, mean), sd))
        density_at_observed = _normal_pdf(treatment, np.full_like(treatment, mean), sd)
        return (
            np.broadcast_to(density[None, :], (n, grid.shape[0])),
            {
                "policy_family": "gaussian",
                "policy_source": "params.policy_expr",
                "policy_mean": mean,
                "policy_sd": sd,
                "n_integration_points": int(grid.shape[0]),
                "policy_grid": grid.tolist(),
            },
            density_at_observed,
        )

    raise ValueError(
        "Unsupported stochastic policy specification for continuous treatment. "
        "Provide policy_samples, policy_grid + policy_density, or a parsable "
        "Gaussian policy_expr such as normal(mean=0, sd=1)."
    )


def _result_payload(
    *,
    estimator_name: str,
    policy_prob_treated: np.ndarray,
    clipped_weights: np.ndarray,
    raw_weights: np.ndarray,
    n_clipped: int,
    policy_meta: Mapping[str, Any],
    policy_value: float,
    se: float,
    ci_lower: float,
    ci_upper: float,
    eif_mean: float,
    eif_sd: float,
    observed_outcome_mean: float,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    n = int(policy_prob_treated.shape[0])
    weight_sum = float(np.sum(clipped_weights))
    ess = float(weight_sum**2 / max(float(np.sum(clipped_weights**2)), 1e-12))
    result: dict[str, Any] = {
        "policy_value": policy_value,
        "standard_error": se,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "interval_method": "normal_eif",
        "eif_mean": eif_mean,
        "eif_standard_deviation": eif_sd,
        "policy_gain_vs_observed": float(policy_value - observed_outcome_mean),
        "observed_outcome_mean": observed_outcome_mean,
        "n_obs": n,
        "method": estimator_name,
        "policy_treated_mean": float(np.mean(policy_prob_treated)),
        "n_clipped": n_clipped,
        "n_trimmed": n_clipped,
        "effective_sample_size": ess,
        "ess_fraction": float(ess / max(n, 1)),
        "max_policy_weight": float(np.max(clipped_weights)),
        "p99_policy_weight": float(np.percentile(clipped_weights, 99)),
        "raw_max_policy_weight": float(np.max(raw_weights)),
        "policy_metadata": dict(policy_meta),
    }
    if extra:
        result.update(extra)
    return {
        "result": result,
        "policy_weights": clipped_weights.tolist(),
    }


def _plugin_result_payload(
    *,
    policy_scores: np.ndarray,
    confidence_level: float,
    policy_meta: Mapping[str, Any],
    observed_outcome_mean: float,
    policy_treatment_mean: float | None,
    clipped_weights: np.ndarray | None,
    raw_weights: np.ndarray | None,
    n_clipped: int,
) -> dict[str, Any]:
    point, se, ci_lower, ci_upper, _, _ = _effect_summary_from_scores(
        policy_scores,
        confidence_level=confidence_level,
    )
    result: dict[str, Any] = {
        "policy_value": point,
        "standard_error": se,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "interval_method": "normal_plugin",
        "policy_gain_vs_observed": float(point - observed_outcome_mean),
        "observed_outcome_mean": float(observed_outcome_mean),
        "n_obs": int(policy_scores.shape[0]),
        "method": "policy_g_formula_plugin",
        "policy_metadata": dict(policy_meta),
        "n_clipped": n_clipped,
        "n_trimmed": n_clipped,
    }
    if policy_treatment_mean is not None:
        result["policy_treatment_mean"] = float(policy_treatment_mean)
    if clipped_weights is not None and raw_weights is not None and clipped_weights.size > 0:
        weight_sum = float(np.sum(clipped_weights))
        ess = float(weight_sum**2 / max(float(np.sum(clipped_weights**2)), 1e-12))
        result.update(
            {
                "effective_sample_size": ess,
                "ess_fraction": float(ess / max(clipped_weights.size, 1)),
                "max_policy_weight": float(np.max(clipped_weights)),
                "p99_policy_weight": float(np.percentile(clipped_weights, 99)),
                "raw_max_policy_weight": float(np.max(raw_weights)),
                "policy_weights_available": True,
            }
        )
        policy_weights = clipped_weights.tolist()
    else:
        result["policy_weights_available"] = False
        policy_weights = []
    return {
        "result": result,
        "policy_weights": policy_weights,
    }


@foundry_method(
    namespace="causal.stochastic",
    version="1.0.0",
    tags={"causal", "stochastic", "policy", "plugin", "g-formula"},
)
class PolicyPluginEstimator:
    """Generic stochastic-policy plug-in / g-formula estimator."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="policy_plugin",
        namespace="",
        version="0.0.0",
        input_slots=_general_policy_slots(),
        output_slots=_result_slots(),
        parameters=(
            ParameterSpec(name="policy_expr", default=None),
            ParameterSpec(name="policy_integration_points", default=51),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="min_policy_weight", default=0.0),
            ParameterSpec(name="max_policy_weight", default=100.0),
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
            "Plug-in g-formula estimator for stochastic policies. Supports continuous "
            "policy mixtures via sampled policies, explicit policy density grids, or "
            "parsable Gaussian policy expressions."
        ),
        tags=frozenset({"causal", "stochastic", "policy", "plugin", "g-formula"}),
        citations=(
            "Díaz, I. & van der Laan, M.J. (2012). Population intervention causal effects based on stochastic interventions.",
        ),
        equations={
            "policy_value": "Ψ(π) = E[∫ μ(a, W) g_π(a | W) da]",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Generic soft-policy evaluation when the runtime can materialize the target "
            "policy as samples or a density grid, or when a parsable Gaussian policy is sufficient."
        ),
        when_not_to_use=(
            "Binary-treatment policy learning where dedicated doubly robust policy-AIPW/TMLE "
            "estimators are available."
        ),
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.policy_overlap@1.0.0",),
        typical_min_obs=100,
        output_interpretation=(
            "policy_value is the estimated mean outcome under the target stochastic policy."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X, T, Y = _extract_policy_inputs(state, binary_only=False)
        confidence_level = float(params.get("confidence_level", 0.95))
        min_weight = float(params.get("min_policy_weight", 0.0))
        max_weight = float(params.get("max_policy_weight", 100.0))

        beta_mu = _fit_continuous_outcome_surface(X, T, Y)
        policy_support, policy_meta, density_at_observed = _resolve_continuous_policy(
            state,
            params,
            T,
        )
        n_clipped = 0
        clipped_weights: np.ndarray | None = None
        raw_weights: np.ndarray | None = None

        if policy_meta["policy_family"] == "sampled_policy":
            policy_scores = np.mean(
                _predict_continuous_outcome_surface(beta_mu, X, policy_support),
                axis=1,
            )
            policy_treatment_mean = float(np.mean(policy_support))
        else:
            grid = np.asarray(policy_meta["policy_grid"], dtype=float)
            mu_grid = _predict_continuous_outcome_surface(
                beta_mu,
                X,
                np.broadcast_to(grid[None, :], (len(X), grid.shape[0])),
            )
            policy_density = np.asarray(policy_support, dtype=float)
            policy_scores = np.sum(mu_grid * policy_density, axis=1)
            policy_treatment_mean = float(np.mean(np.sum(policy_density * grid[None, :], axis=1)))

            if density_at_observed is not None:
                beta_g, sigma_g = _fit_gaussian_treatment_density(X, T)
                observed_density = _predict_gaussian_treatment_density(beta_g, sigma_g, X, T)
                raw_weights = density_at_observed / np.clip(observed_density, 1e-6, None)
                clipped_weights = np.clip(raw_weights, min_weight, max_weight)
                n_clipped = int(np.sum(np.abs(raw_weights - clipped_weights) > 1e-12))

        return _plugin_result_payload(
            policy_scores=np.asarray(policy_scores, dtype=float),
            confidence_level=confidence_level,
            policy_meta=policy_meta,
            observed_outcome_mean=float(np.mean(Y)),
            policy_treatment_mean=policy_treatment_mean,
            clipped_weights=clipped_weights,
            raw_weights=raw_weights,
            n_clipped=n_clipped,
        )


@foundry_method(
    namespace="causal.stochastic",
    version="1.0.0",
    tags={"causal", "stochastic", "policy", "aipw", "doubly-robust"},
)
class PolicyAIPWEstimator:
    """Binary-treatment stochastic policy AIPW / one-step estimator."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="policy_aipw",
        namespace="",
        version="0.0.0",
        input_slots=_policy_slots(),
        output_slots=_result_slots(),
        parameters=(
            ParameterSpec(name="policy_expr", default=None),
            ParameterSpec(name="incremental_delta", default=None),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="min_propensity", default=0.01),
            ParameterSpec(name="min_policy_weight", default=0.0),
            ParameterSpec(name="max_policy_weight", default=100.0),
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
            "AIPW / one-step estimator for binary stochastic policies. Supports explicit "
            "policy probabilities and incremental propensity-score interventions."
        ),
        tags=frozenset({"causal", "stochastic", "policy", "aipw", "doubly-robust"}),
        citations=(
            "Díaz, I. & van der Laan, M.J. (2012). Population intervention causal effects based on stochastic interventions.",
            "Kennedy, E.H. (2019). Nonparametric causal effects based on incremental propensity score interventions.",
        ),
        equations={
            "policy_value": "Ψ(π) = E[m_π(W) + π(A|W)/g(A|W) · (Y - Q(A,W))]",
            "incremental_binary": "π_δ(W) = δ e(W) / ((1-e(W)) + δ e(W))",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Binary treatment, point-treatment policy evaluation, and overlap that is adequate "
            "for importance weighting."
        ),
        when_not_to_use=(
            "Continuous or multi-valued treatment without a discrete policy representation."
        ),
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.policy_overlap@1.0.0",),
        typical_min_obs=100,
        output_interpretation=(
            "policy_value is the estimated mean outcome under the target policy."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X, T, Y = _extract_policy_inputs(state, binary_only=True)
        min_propensity = float(params.get("min_propensity", 0.01))
        min_weight = float(params.get("min_policy_weight", 0.0))
        max_weight = float(params.get("max_policy_weight", 100.0))
        confidence_level = float(params.get("confidence_level", 0.95))

        propensity = np.clip(_logistic_propensity(X, T), min_propensity, 1.0 - min_propensity)
        mu0, mu1 = _fit_linear_outcome_predictions(X, T, Y)
        policy_prob_treated, policy_meta = _resolve_policy_probabilities(state, params, propensity)
        raw_weights, clipped_weights, n_clipped = _policy_weights(
            T,
            propensity,
            policy_prob_treated,
            min_weight=min_weight,
            max_weight=max_weight,
        )

        q_obs = np.where(T > 0.5, mu1, mu0)
        m_pi = policy_prob_treated * mu1 + (1.0 - policy_prob_treated) * mu0
        scores = m_pi + clipped_weights * (Y - q_obs)
        point, se, ci_lower, ci_upper, eif_mean, eif_sd = _effect_summary_from_scores(
            scores,
            confidence_level=confidence_level,
        )
        return _result_payload(
            estimator_name="binary_policy_aipw",
            policy_prob_treated=policy_prob_treated,
            clipped_weights=clipped_weights,
            raw_weights=raw_weights,
            n_clipped=n_clipped,
            policy_meta=policy_meta,
            policy_value=point,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            eif_mean=eif_mean,
            eif_sd=eif_sd,
            observed_outcome_mean=float(np.mean(Y)),
        )


@foundry_method(
    namespace="causal.stochastic",
    version="1.0.0",
    tags={"causal", "stochastic", "policy", "tmle", "targeted-learning"},
)
class PolicyTMLEEstimator:
    """Binary-treatment stochastic policy TMLE estimator."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="policy_tmle",
        namespace="",
        version="0.0.0",
        input_slots=_policy_slots(),
        output_slots=_result_slots(),
        parameters=(
            ParameterSpec(name="policy_expr", default=None),
            ParameterSpec(name="incremental_delta", default=None),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="min_propensity", default=0.01),
            ParameterSpec(name="min_policy_weight", default=0.0),
            ParameterSpec(name="max_policy_weight", default=100.0),
            ParameterSpec(name="targeting_step_limit", default=5.0),
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
            "TMLE for binary stochastic policy evaluation using the policy clever covariate "
            "π(A|W)/g(A|W)."
        ),
        tags=frozenset({"causal", "stochastic", "policy", "tmle", "efficient"}),
        citations=(
            "Díaz, I. & van der Laan, M.J. (2012). Population intervention causal effects based on stochastic interventions.",
            "van der Laan, M.J. & Rose, S. (2011). Targeted Learning.",
        ),
        equations={
            "clever_covariate": "H(A,W) = π(A|W) / g(A|W)",
            "targeted_value": "Ψ̂_TMLE = n^-1 Σ_i [π_i Q_1^*(W_i) + (1-π_i) Q_0^*(W_i)]",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Binary-treatment stochastic policies with enough data for targeted updates.",
        when_not_to_use="Continuous treatment without a discretized policy representation.",
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.policy_overlap@1.0.0",),
        typical_min_obs=150,
        output_interpretation="policy_value is the targeted plug-in estimate under the target policy.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X, T, Y = _extract_policy_inputs(state, binary_only=True)
        min_propensity = float(params.get("min_propensity", 0.01))
        min_weight = float(params.get("min_policy_weight", 0.0))
        max_weight = float(params.get("max_policy_weight", 100.0))
        confidence_level = float(params.get("confidence_level", 0.95))
        targeting_step_limit = float(params.get("targeting_step_limit", 5.0))

        propensity = np.clip(_logistic_propensity(X, T), min_propensity, 1.0 - min_propensity)
        mu0, mu1 = _fit_linear_outcome_predictions(X, T, Y)
        policy_prob_treated, policy_meta = _resolve_policy_probabilities(state, params, propensity)
        raw_weights, clipped_weights, n_clipped = _policy_weights(
            T,
            propensity,
            policy_prob_treated,
            min_weight=min_weight,
            max_weight=max_weight,
        )

        q_obs = np.where(T > 0.5, mu1, mu0)
        residual = Y - q_obs
        denom = max(float(np.sum(clipped_weights**2)), 1e-12)
        raw_epsilon = float(np.sum(clipped_weights * residual) / denom)
        epsilon = float(np.clip(raw_epsilon, -targeting_step_limit, targeting_step_limit))

        q1_star = mu1 + epsilon * (policy_prob_treated / np.clip(propensity, 1e-6, 1.0))
        q0_star = mu0 + epsilon * (
            (1.0 - policy_prob_treated) / np.clip(1.0 - propensity, 1e-6, 1.0)
        )
        q_obs_star = np.where(T > 0.5, q1_star, q0_star)
        m_pi_star = policy_prob_treated * q1_star + (1.0 - policy_prob_treated) * q0_star
        scores = m_pi_star + clipped_weights * (Y - q_obs_star)
        point, se, ci_lower, ci_upper, eif_mean, eif_sd = _effect_summary_from_scores(
            scores,
            confidence_level=confidence_level,
        )

        return _result_payload(
            estimator_name="binary_policy_tmle",
            policy_prob_treated=policy_prob_treated,
            clipped_weights=clipped_weights,
            raw_weights=raw_weights,
            n_clipped=n_clipped,
            policy_meta=policy_meta,
            policy_value=point,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            eif_mean=eif_mean,
            eif_sd=eif_sd,
            observed_outcome_mean=float(np.mean(Y)),
            extra={
                "targeting_summary": {
                    "raw_epsilon": raw_epsilon,
                    "epsilon": epsilon,
                    "epsilon_limit": targeting_step_limit,
                    "n_iterations": 1,
                    "converged": bool(abs(epsilon) < 1e-8),
                }
            },
        )


__all__ = [
    "PolicyAIPWEstimator",
    "PolicyPluginEstimator",
    "PolicyTMLEEstimator",
]
