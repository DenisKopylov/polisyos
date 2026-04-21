"""Survey-aware semiparametric wrappers for orthogonal signals.

This module provides the compositional bridge required by Phase 1 / P1.02:

1. Take a full-data orthogonal score from the causal / econometrics layer.
2. Wrap it in a survey-aware observed-data signal
   kappa(D) + S * d(D) * (phi(W) - kappa(D)).
3. Compute design-aware uncertainty using Binder linearization or replicate
   weights when they are available.
4. Diagnose whether the available weight regime supports an efficiency claim,
   only design-consistent doubly robust inference, or requires a stronger
   selection model.
5. Expose Foundry methods for ATE, ATT, and subgroup conditional means.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

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
from polisyos.foundry.methods.catalog.causal.eif_bounds import (
    compute_eif_ate,
    compute_eif_att,
    compute_eif_subgroup_mean,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _to_1d_float(name: str, values: object, *, expected_size: int | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if expected_size is not None and arr.size != expected_size:
        raise ValueError(f"{name} must have length {expected_size}, got {arr.size}")
    if arr.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _to_1d_float_allow_nan(
    name: str,
    values: object,
    *,
    expected_size: int | None = None,
) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if expected_size is not None and arr.size != expected_size:
        raise ValueError(f"{name} must have length {expected_size}, got {arr.size}")
    if arr.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if np.any(np.isinf(arr)):
        raise ValueError(f"{name} must not contain inf values")
    return arr


def _to_2d_float(name: str, values: object, *, expected_rows: int | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if expected_rows is not None and arr.shape[0] != expected_rows:
        raise ValueError(f"{name} must have {expected_rows} rows, got {arr.shape[0]}")
    if arr.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _to_1d_labels(name: str, values: object, *, expected_size: int | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=object).reshape(-1)
    if expected_size is not None and arr.size != expected_size:
        raise ValueError(f"{name} must have length {expected_size}, got {arr.size}")
    if arr.size == 0:
        raise ValueError(f"{name} must be non-empty")
    return arr


def _extract_signal_array(values: object) -> np.ndarray:
    if hasattr(values, "scores"):
        values = values.scores  # type: ignore[attr-defined]
    return _to_1d_float("full_signal", values)


def _kish_effective_sample_size(weights: np.ndarray) -> float:
    weights = _to_1d_float("weights", weights)
    total = float(np.sum(weights))
    total_sq = float(np.sum(weights**2))
    if total <= 0.0 or total_sq <= 0.0:
        return 0.0
    return float(total**2 / total_sq)


def _weighted_mean(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    values = _to_1d_float("values", values)
    if weights is None:
        return float(np.mean(values))
    weights = _to_1d_float("weights", weights, expected_size=values.size)
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError("weights must sum to a positive value")
    return float(np.sum(weights * values) / total)


def _normal_quantile(alpha: float) -> float:
    try:
        from scipy import stats

        return float(stats.norm.ppf(1.0 - alpha / 2.0))
    except Exception:
        return 1.96


def _broadcast_augmentation(augmentation: float | np.ndarray | None, n_obs: int) -> np.ndarray:
    if augmentation is None:
        return np.zeros(n_obs, dtype=float)
    if np.isscalar(augmentation):
        return np.full(n_obs, float(augmentation), dtype=float)
    return _to_1d_float("augmentation", augmentation, expected_size=n_obs)


def _normalize_inverse_inclusion_weights(
    inverse_weights: np.ndarray,
    sampled: np.ndarray,
    normalization: Literal["hajek", "horvitz_thompson"],
    *,
    allow_zero: bool = False,
) -> np.ndarray:
    inverse_weights = _to_1d_float("inverse_weights", inverse_weights, expected_size=sampled.size)
    if allow_zero:
        if np.any(inverse_weights < 0.0):
            raise ValueError("inverse inclusion weights must be non-negative")
    elif np.any(inverse_weights <= 0.0):
        raise ValueError("inverse inclusion weights must be strictly positive")
    if normalization == "horvitz_thompson":
        return inverse_weights

    sampled_mask = sampled > 0.5
    if not np.any(sampled_mask):
        sampled_mask = np.ones(sampled.size, dtype=bool)
    scale = float(np.mean(inverse_weights[sampled_mask]))
    if scale <= 0.0:
        raise ValueError("cannot normalize inverse inclusion weights with non-positive mean")
    return inverse_weights / scale


def _aggregate_by_psu(
    values: np.ndarray,
    strata: np.ndarray | None,
    psu: np.ndarray | None,
) -> tuple[tuple[tuple[object, object], ...], np.ndarray]:
    n_obs = values.size
    if strata is None:
        strata = np.zeros(n_obs, dtype=object)
    else:
        strata = _to_1d_labels("strata", strata, expected_size=n_obs)
    if psu is None:
        psu = np.arange(n_obs, dtype=object)
    else:
        psu = _to_1d_labels("psu", psu, expected_size=n_obs)

    labels: list[tuple[object, object]] = []
    totals: list[float] = []
    for stratum in np.unique(strata):
        in_stratum = strata == stratum
        for cluster in np.unique(psu[in_stratum]):
            mask = in_stratum & (psu == cluster)
            labels.append((stratum, cluster))
            totals.append(float(np.sum(values[mask])))
    return tuple(labels), np.asarray(totals, dtype=float)


def _encode_labels(values: np.ndarray) -> np.ndarray:
    labels = _to_1d_labels("labels", values)
    _, codes = np.unique(labels.astype(str), return_inverse=True)
    centered = codes.astype(float) - float(np.mean(codes))
    scale = float(np.std(centered))
    if scale <= 1e-12:
        return np.zeros(labels.size, dtype=float)
    return centered / scale


def _fit_weighted_linear(
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    ridge: float = 1e-6,
) -> np.ndarray:
    x_aug = np.column_stack([np.ones(x.shape[0], dtype=float), x])
    w = np.maximum(weights, 1e-8)
    xtw = x_aug.T * w
    gram = xtw @ x_aug
    penalty = np.eye(gram.shape[0], dtype=float) * ridge
    penalty[0, 0] = 0.0
    rhs = xtw @ y
    try:
        return np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(x_aug * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]


def _predict_linear(x: np.ndarray, beta: np.ndarray) -> np.ndarray:
    x_aug = np.column_stack([np.ones(x.shape[0], dtype=float), x])
    return x_aug @ beta


def _fit_weighted_logistic(
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    ridge: float = 1e-4,
    max_iter: int = 100,
) -> np.ndarray:
    x_aug = np.column_stack([np.ones(x.shape[0], dtype=float), x])
    beta = np.zeros(x_aug.shape[1], dtype=float)
    penalty = np.eye(x_aug.shape[1], dtype=float) * ridge
    penalty[0, 0] = 0.0
    for _ in range(max_iter):
        eta = np.clip(x_aug @ beta, -20.0, 20.0)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.maximum(weights * p * (1.0 - p), 1e-8)
        grad = x_aug.T @ (weights * (y - p)) - penalty @ beta
        hess = x_aug.T @ (w[:, None] * x_aug) + penalty
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def _predict_logistic(x: np.ndarray, beta: np.ndarray) -> np.ndarray:
    x_aug = np.column_stack([np.ones(x.shape[0], dtype=float), x])
    eta = np.clip(x_aug @ beta, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-eta))


def _compute_observed_signal(
    full_signal: np.ndarray,
    augmentation: np.ndarray,
    sampled: np.ndarray,
    inverse_inclusion_weights: np.ndarray,
) -> np.ndarray:
    return augmentation + sampled * inverse_inclusion_weights * (full_signal - augmentation)


def _jsonify(value: object) -> object:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "__dataclass_fields__"):
        payload = {}
        for key in value.__dataclass_fields__:
            payload[key] = _jsonify(getattr(value, key))
        return payload
    if isinstance(value, Mapping):
        return {str(key): _jsonify(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonify(item) for item in value]
    if isinstance(value, list):
        return [_jsonify(item) for item in value]
    return value


def _state_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    n: int | None = None,
    allow_nan: bool = False,
) -> np.ndarray:
    if key not in state:
        raise ValueError(f"missing required state key {key!r}")
    if allow_nan:
        return _to_1d_float_allow_nan(key, state[key], expected_size=n)
    return _to_1d_float(key, state[key], expected_size=n)


def _state_optional_vector(
    state: Mapping[str, Any],
    key: str,
    *,
    n: int | None = None,
    allow_nan: bool = False,
) -> np.ndarray | None:
    if key not in state:
        return None
    return _state_vector(state, key, n=n, allow_nan=allow_nan)


def _state_matrix(state: Mapping[str, Any], key: str, *, n: int | None = None) -> np.ndarray:
    if key not in state:
        raise ValueError(f"missing required state key {key!r}")
    return _to_2d_float(key, state[key], expected_rows=n)


def _state_optional_matrix(
    state: Mapping[str, Any],
    key: str,
    *,
    n: int | None = None,
) -> np.ndarray | None:
    if key not in state:
        return None
    return _to_2d_float(key, state[key], expected_rows=n)


def _state_optional_labels(
    state: Mapping[str, Any],
    key: str,
    *,
    n: int | None = None,
) -> np.ndarray | None:
    if key not in state:
        return None
    return _to_1d_labels(key, state[key], expected_size=n)


@dataclass(frozen=True)
class SurveyDesignSpec:
    """Design metadata required for survey-aware signal adjustment."""

    weights: np.ndarray
    strata: np.ndarray | None = None
    psu: np.ndarray | None = None
    fpc: np.ndarray | None = None
    replicate_weights: np.ndarray | None = None
    provenance: str = "base"

    def __post_init__(self) -> None:
        weights = _to_1d_float("weights", self.weights)
        if np.any(weights <= 0.0):
            raise ValueError("weights must be strictly positive")
        object.__setattr__(self, "weights", weights)

        n_obs = weights.size
        if self.strata is not None:
            object.__setattr__(
                self,
                "strata",
                _to_1d_labels("strata", self.strata, expected_size=n_obs),
            )
        if self.psu is not None:
            object.__setattr__(self, "psu", _to_1d_labels("psu", self.psu, expected_size=n_obs))
        if self.fpc is not None:
            fpc = _to_1d_float("fpc", self.fpc, expected_size=n_obs)
            if np.any(fpc <= 0.0):
                raise ValueError("fpc must be strictly positive")
            object.__setattr__(self, "fpc", fpc)
        if self.replicate_weights is not None:
            rep = np.asarray(self.replicate_weights, dtype=float)
            if rep.ndim != 2:
                raise ValueError("replicate_weights must be a 2D array")
            if n_obs not in rep.shape:
                raise ValueError("replicate_weights must contain one dimension equal to n_obs")
            if rep.shape[0] != n_obs:
                rep = rep.T
            if not np.all(np.isfinite(rep)) or np.any(rep < 0.0):
                raise ValueError("replicate_weights must be finite and non-negative")
            object.__setattr__(self, "replicate_weights", rep)

    @property
    def n_obs(self) -> int:
        return int(self.weights.size)

    def min_psu_per_stratum(self) -> int | None:
        if self.strata is None or self.psu is None:
            return None
        counts = [
            int(np.unique(self.psu[self.strata == stratum]).size)
            for stratum in np.unique(self.strata)
        ]
        return min(counts) if counts else None


@dataclass(frozen=True)
class SamplingModelSpec:
    """Sampling-side metadata for observed-data signal construction."""

    inclusion_probabilities: np.ndarray | None = None
    sampled: np.ndarray | None = None
    phase1_auxiliaries: Mapping[str, np.ndarray] | None = None
    calibration_vars: tuple[str, ...] = ()
    informative_sampling_suspected: bool = False

    def __post_init__(self) -> None:
        if self.inclusion_probabilities is not None:
            inclusion = _to_1d_float("inclusion_probabilities", self.inclusion_probabilities)
            if np.any((inclusion <= 0.0) | (inclusion > 1.0)):
                raise ValueError("inclusion_probabilities must lie in (0, 1]")
            object.__setattr__(self, "inclusion_probabilities", inclusion)

        if self.sampled is not None:
            sampled = _to_1d_float("sampled", self.sampled)
            sampled = np.where(sampled > 0.0, 1.0, 0.0)
            object.__setattr__(self, "sampled", sampled)

        if self.phase1_auxiliaries is not None:
            aux: dict[str, np.ndarray] = {}
            expected_size = None
            if self.inclusion_probabilities is not None:
                expected_size = self.inclusion_probabilities.size
            elif self.sampled is not None:
                expected_size = self.sampled.size
            for key, values in self.phase1_auxiliaries.items():
                aux[key] = _to_1d_float(
                    f"phase1_auxiliaries[{key!r}]",
                    values,
                    expected_size=expected_size,
                )
                expected_size = aux[key].size
            object.__setattr__(self, "phase1_auxiliaries", aux)

    def n_obs(self) -> int | None:
        if self.inclusion_probabilities is not None:
            return int(self.inclusion_probabilities.size)
        if self.sampled is not None:
            return int(self.sampled.size)
        if self.phase1_auxiliaries:
            first = next(iter(self.phase1_auxiliaries.values()))
            return int(first.size)
        return None


@dataclass(frozen=True)
class SurveyVarianceBackend:
    """Variance backend selection for the survey wrapper."""

    method: Literal["binder", "brr", "jk1", "bootstrap"] = "binder"
    scale: float | None = None


@dataclass(frozen=True)
class LinearizedSurveyVariance:
    """Binder-style variance summary for a survey-adjusted signal."""

    variance: float
    standard_error: float
    design_effect: float
    effective_n: float
    unit_influence: np.ndarray
    psu_influence: np.ndarray
    psu_labels: tuple[tuple[object, object], ...]
    method: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplicateSurveyVariance:
    """Replicate-weight variance summary for a survey-adjusted signal."""

    variance: float
    standard_error: float
    replicate_estimates: np.ndarray
    method: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeightRegimeDiagnostic:
    """Classify whether a survey-weight regime supports an efficiency claim."""

    weight_regime: Literal["full_design", "calibrated_only", "informative_or_unsafe"]
    claim_level: Literal[
        "design_dr_efficiency_claimable",
        "design_dr_consistent_only",
        "selection_model_required",
    ]
    provenance: str
    combined_weight_ess: float
    design_effect_proxy: float
    positivity_flags: tuple[str, ...] = ()
    psu_leverage_flags: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    report: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SurveyAdjustedSignalResult:
    """Survey-adjusted signal plus design-aware inference summary."""

    estimate: float
    std_error: float
    ci: tuple[float, float]
    estimand_label: str
    observed_signal: np.ndarray
    full_signal: np.ndarray
    augmentation: np.ndarray
    inverse_inclusion_weights: np.ndarray
    design_effect: float
    effective_n: float
    weight_regime: str
    claim_level: str
    positivity_flags: tuple[str, ...]
    psu_leverage_flags: tuple[str, ...]
    influence_values_unit: np.ndarray
    influence_values_psu: np.ndarray
    psu_labels: tuple[tuple[object, object], ...]
    variance_method: str
    notes: tuple[str, ...]
    diagnostic: WeightRegimeDiagnostic


@dataclass(frozen=True)
class PSUStratifiedCrossFitSchedule:
    """Fold assignment that preserves PSU-within-strata dependence."""

    fold_ids: np.ndarray
    n_folds: int
    unit_of_independence: Literal["psu_within_strata"] = "psu_within_strata"
    fallback_used: Literal["none", "round_robin_strata", "single_psu_strata"] = "none"
    warnings: tuple[str, ...] = ()
    psu_counts_by_stratum: dict[str, int] = field(default_factory=dict)


def resolve_inverse_inclusion_weights(
    design_spec: SurveyDesignSpec,
    sampling_spec: SamplingModelSpec | None = None,
    *,
    normalization: Literal["hajek", "horvitz_thompson"] = "hajek",
) -> np.ndarray:
    """Return inverse-inclusion weights used by the observed-data signal."""
    if sampling_spec is not None and sampling_spec.inclusion_probabilities is not None:
        inverse_weights = 1.0 / _to_1d_float(
            "inclusion_probabilities",
            sampling_spec.inclusion_probabilities,
            expected_size=design_spec.n_obs,
        )
    else:
        inverse_weights = design_spec.weights.copy()

    if sampling_spec is not None and sampling_spec.sampled is not None:
        sampled = _to_1d_float("sampled", sampling_spec.sampled, expected_size=design_spec.n_obs)
    else:
        sampled = np.ones(design_spec.n_obs, dtype=float)
    sampled = np.where(sampled > 0.0, 1.0, 0.0)
    return _normalize_inverse_inclusion_weights(inverse_weights, sampled, normalization)


def combine_weights_for_estimand(
    design_weights: np.ndarray,
    *,
    estimand: Literal["generic", "ate", "att", "subgroup_mean"] = "generic",
    treatment: np.ndarray | None = None,
    propensity: np.ndarray | None = None,
    subgroup: np.ndarray | None = None,
    target_treatment: Literal[0, 1] = 1,
    clip: tuple[float, float] = (0.01, 0.99),
) -> np.ndarray:
    """Build combined design/treatment weights for diagnostics."""
    weights = _to_1d_float("design_weights", design_weights)
    if estimand == "generic":
        combined = weights.copy()
    else:
        if treatment is None or propensity is None:
            raise ValueError(f"{estimand} diagnostics require treatment and propensity")
        treatment_arr = _to_1d_float("treatment", treatment, expected_size=weights.size)
        propensity_arr = np.clip(
            _to_1d_float("propensity", propensity, expected_size=weights.size),
            clip[0],
            clip[1],
        )
        if estimand == "ate":
            combined = weights * (
                treatment_arr / propensity_arr
                + (1.0 - treatment_arr) / (1.0 - propensity_arr)
            )
        elif estimand == "att":
            combined = weights * (
                treatment_arr
                + (1.0 - treatment_arr) * propensity_arr / (1.0 - propensity_arr)
            )
        elif estimand == "subgroup_mean":
            arm = float(target_treatment)
            arm_indicator = np.where(treatment_arr > 0.5, 1.0, 0.0)
            denom = propensity_arr if arm > 0.5 else (1.0 - propensity_arr)
            combined = weights * np.where(arm_indicator == arm, 1.0 / denom, 0.0)
        else:
            raise ValueError(f"unsupported estimand: {estimand}")

    if subgroup is not None:
        subgroup_arr = _to_1d_float("subgroup", subgroup, expected_size=weights.size)
        combined = combined * subgroup_arr
    return combined


def compute_binder_linearized_variance(
    values: np.ndarray,
    *,
    strata: np.ndarray | None = None,
    psu: np.ndarray | None = None,
    analysis_weights: np.ndarray | None = None,
) -> LinearizedSurveyVariance:
    """Compute a Binder-style linearized variance on PSU sums."""
    values = _to_1d_float("values", values)
    n_obs = values.size
    if analysis_weights is None:
        analysis_weights = np.ones(n_obs, dtype=float)
    else:
        analysis_weights = _to_1d_float("analysis_weights", analysis_weights, expected_size=n_obs)
        if np.any(analysis_weights < 0.0):
            raise ValueError("analysis_weights must be non-negative")
    denominator = float(np.sum(analysis_weights))
    if denominator <= 0.0:
        raise ValueError("analysis_weights must sum to a positive value")

    estimate = float(np.sum(analysis_weights * values) / denominator)
    centered = analysis_weights * (values - estimate)

    if strata is None:
        strata = np.zeros(n_obs, dtype=object)
    else:
        strata = _to_1d_labels("strata", strata, expected_size=n_obs)
    if psu is None:
        psu = np.arange(n_obs, dtype=object)
        notes = ("psu_missing_fallback_to_unit_level",)
    else:
        psu = _to_1d_labels("psu", psu, expected_size=n_obs)
        notes = ()

    variance_numerator = 0.0
    psu_labels: list[tuple[object, object]] = []
    psu_totals: list[float] = []
    singleton_strata = 0

    for stratum in np.unique(strata):
        in_stratum = strata == stratum
        psu_ids = np.unique(psu[in_stratum])
        n_psu = int(psu_ids.size)
        stratum_totals = []
        for cluster in psu_ids:
            mask = in_stratum & (psu == cluster)
            total = float(np.sum(centered[mask]))
            stratum_totals.append(total)
            psu_labels.append((stratum, cluster))
            psu_totals.append(total / denominator)
        if n_psu < 2:
            singleton_strata += 1
            continue
        totals_arr = np.asarray(stratum_totals, dtype=float)
        totals_mean = float(np.mean(totals_arr))
        variance_numerator += float(
            n_psu / (n_psu - 1.0) * np.sum((totals_arr - totals_mean) ** 2)
        )

    variance = float(variance_numerator / (denominator**2))
    srs_numerator = float(np.sum(centered**2))
    if n_obs > 1:
        srs_variance = float((n_obs / (n_obs - 1.0)) * srs_numerator / (denominator**2))
    else:
        srs_variance = 0.0
    design_effect = float(variance / max(srs_variance, 1e-12))
    effective_n = float(n_obs / max(design_effect, 1e-12)) if n_obs > 0 else 0.0

    if singleton_strata:
        notes = (*notes, f"singleton_strata_omitted={singleton_strata}")

    unit_influence = centered / denominator
    return LinearizedSurveyVariance(
        variance=variance,
        standard_error=float(np.sqrt(max(variance, 0.0))),
        design_effect=max(design_effect, 0.0),
        effective_n=max(effective_n, 0.0),
        unit_influence=unit_influence,
        psu_influence=np.asarray(psu_totals, dtype=float),
        psu_labels=tuple(psu_labels),
        method="binder",
        notes=notes,
    )


def _default_replicate_scale(method: str, n_replicates: int) -> float:
    if n_replicates <= 1:
        return 0.0
    if method == "jk1":
        return float((n_replicates - 1.0) / n_replicates)
    if method == "bootstrap":
        return float(1.0 / (n_replicates - 1.0))
    return float(1.0 / n_replicates)


def compute_replicate_weight_variance(
    full_signal: np.ndarray,
    *,
    design_spec: SurveyDesignSpec,
    sampling_spec: SamplingModelSpec | None = None,
    augmentation: np.ndarray,
    normalization: Literal["hajek", "horvitz_thompson"] = "hajek",
    method: Literal["brr", "jk1", "bootstrap"] = "brr",
    scale: float | None = None,
    full_sample_estimate: float | None = None,
) -> ReplicateSurveyVariance:
    """Compute replicate-weight variance for the survey-adjusted signal."""
    if design_spec.replicate_weights is None:
        raise ValueError("replicate_weights are required for replicate variance")

    signal = _to_1d_float("full_signal", full_signal, expected_size=design_spec.n_obs)
    augmentation_arr = _to_1d_float("augmentation", augmentation, expected_size=design_spec.n_obs)
    if sampling_spec is not None and sampling_spec.sampled is not None:
        sampled = _to_1d_float("sampled", sampling_spec.sampled, expected_size=design_spec.n_obs)
    else:
        sampled = np.ones(design_spec.n_obs, dtype=float)
    sampled = np.where(sampled > 0.0, 1.0, 0.0)

    if full_sample_estimate is None:
        base_inverse = resolve_inverse_inclusion_weights(
            design_spec,
            sampling_spec,
            normalization=normalization,
        )
        base_observed = _compute_observed_signal(signal, augmentation_arr, sampled, base_inverse)
        full_sample_estimate = float(np.mean(base_observed))

    replicate_estimates: list[float] = []
    for replicate_idx in range(design_spec.replicate_weights.shape[1]):
        replicate_weights = design_spec.replicate_weights[:, replicate_idx]
        normalized = _normalize_inverse_inclusion_weights(
            replicate_weights,
            sampled,
            normalization,
            allow_zero=True,
        )
        observed = _compute_observed_signal(signal, augmentation_arr, sampled, normalized)
        replicate_estimates.append(float(np.mean(observed)))

    replicate_estimates_arr = np.asarray(replicate_estimates, dtype=float)
    variance_scale = (
        float(scale)
        if scale is not None
        else _default_replicate_scale(method, replicate_estimates_arr.size)
    )
    variance = float(
        variance_scale * np.sum((replicate_estimates_arr - float(full_sample_estimate)) ** 2)
    )
    notes = (f"replicate_count={replicate_estimates_arr.size}",)
    if scale is None:
        notes = (*notes, f"default_scale={variance_scale:.6g}")
    return ReplicateSurveyVariance(
        variance=variance,
        standard_error=float(np.sqrt(max(variance, 0.0))),
        replicate_estimates=replicate_estimates_arr,
        method=method,
        notes=notes,
    )


def diagnose_weight_regime(
    design_spec: SurveyDesignSpec,
    *,
    sampling_spec: SamplingModelSpec | None = None,
    estimand: Literal["generic", "ate", "att", "subgroup_mean"] = "generic",
    treatment: np.ndarray | None = None,
    propensity: np.ndarray | None = None,
    subgroup: np.ndarray | None = None,
    target_treatment: Literal[0, 1] = 1,
    influence_values: np.ndarray | None = None,
) -> WeightRegimeDiagnostic:
    """Diagnose whether the available survey regime supports an efficiency claim."""
    combined_weights = combine_weights_for_estimand(
        design_spec.weights,
        estimand=estimand,
        treatment=treatment,
        propensity=propensity,
        subgroup=subgroup,
        target_treatment=target_treatment,
    )
    ess = _kish_effective_sample_size(combined_weights)
    design_effect_proxy = (
        float(design_spec.n_obs / ess) if design_spec.n_obs > 0 and ess > 0.0 else float("inf")
    )

    provenance = str(design_spec.provenance).strip().lower()
    informative = bool(
        sampling_spec.informative_sampling_suspected if sampling_spec is not None else False
    )
    full_design_provenance = {"base", "base+nonresponse", "base_nonresponse"}
    calibrated_provenance = {
        "calibrated",
        "calibrated/raked",
        "raked",
        "replicate-only",
        "base+nonresponse+calibrated",
    }

    positivity_flags: list[str] = []
    if propensity is not None:
        propensity_arr = _to_1d_float("propensity", propensity, expected_size=design_spec.n_obs)
        if float(np.min(propensity_arr)) <= 0.02:
            positivity_flags.append("near_zero_propensity")
        if float(np.max(propensity_arr)) >= 0.98:
            positivity_flags.append("near_one_propensity")

        if treatment is not None:
            treatment_arr = _to_1d_float("treatment", treatment, expected_size=design_spec.n_obs)
            treated_combined = combined_weights[treatment_arr > 0.5]
            control_combined = combined_weights[treatment_arr <= 0.5]
            if treated_combined.size:
                treated_ess = _kish_effective_sample_size(treated_combined)
                if treated_ess < 15.0:
                    positivity_flags.append("low_treated_ess")
            else:
                treated_ess = 0.0
                positivity_flags.append("no_treated_units")
            if control_combined.size:
                control_ess = _kish_effective_sample_size(control_combined)
                if control_ess < 15.0:
                    positivity_flags.append("low_control_ess")
            else:
                control_ess = 0.0
                positivity_flags.append("no_control_units")
        else:
            treated_ess = None
            control_ess = None
    else:
        treated_ess = None
        control_ess = None

    if influence_values is not None:
        influence_arr = _to_1d_float(
            "influence_values",
            influence_values,
            expected_size=design_spec.n_obs,
        )
        psu_labels, psu_totals = _aggregate_by_psu(
            np.abs(influence_arr),
            design_spec.strata,
            design_spec.psu,
        )
    else:
        psu_labels, psu_totals = _aggregate_by_psu(
            combined_weights,
            design_spec.strata,
            design_spec.psu,
        )
    total_abs_psu = float(np.sum(np.abs(psu_totals)))
    max_psu_share = (
        float(np.max(np.abs(psu_totals)) / total_abs_psu)
        if total_abs_psu > 0.0
        else 0.0
    )

    psu_leverage_flags: list[str] = []
    if max_psu_share >= 0.5:
        psu_leverage_flags.append("extreme_psu_dominance")
    elif max_psu_share >= 0.3:
        psu_leverage_flags.append("high_psu_leverage")

    min_psu_per_stratum = design_spec.min_psu_per_stratum()
    warnings: list[str] = []
    if min_psu_per_stratum is None:
        warnings.append("strata_or_psu_missing")
    elif min_psu_per_stratum < 2:
        warnings.append("fewer_than_two_psus_in_some_strata")
    if ess < max(20.0, 0.1 * design_spec.n_obs):
        warnings.append("combined_weight_ess_low")
    if provenance in calibrated_provenance:
        warnings.append("calibrated_weights_without_full_inclusion_model")
    if not provenance:
        warnings.append("unknown_weight_provenance")

    if informative:
        weight_regime = "informative_or_unsafe"
        claim_level = "selection_model_required"
        warnings.append("informative_sampling_suspected")
    elif provenance in calibrated_provenance or min_psu_per_stratum is None:
        weight_regime = "calibrated_only"
        claim_level = "design_dr_consistent_only"
    elif provenance in full_design_provenance:
        weight_regime = "full_design"
        if (
            min_psu_per_stratum is not None
            and min_psu_per_stratum >= 2
            and not positivity_flags
            and max_psu_share < 0.3
            and ess >= max(30.0, 0.2 * design_spec.n_obs)
        ):
            claim_level = "design_dr_efficiency_claimable"
        else:
            claim_level = "design_dr_consistent_only"
    else:
        weight_regime = "calibrated_only"
        claim_level = "design_dr_consistent_only"
        warnings.append("unrecognized_provenance_treated_as_calibrated")

    report = {
        "combined_weight_ess": float(ess),
        "design_effect_proxy": float(design_effect_proxy),
        "min_psu_per_stratum": min_psu_per_stratum,
        "max_psu_leverage_share": float(max_psu_share),
        "n_psu": len(psu_labels),
        "treated_effective_n": None if treated_ess is None else float(treated_ess),
        "control_effective_n": None if control_ess is None else float(control_ess),
        "provenance": provenance,
    }
    return WeightRegimeDiagnostic(
        weight_regime=weight_regime,
        claim_level=claim_level,
        provenance=provenance or "unknown",
        combined_weight_ess=float(ess),
        design_effect_proxy=float(design_effect_proxy),
        positivity_flags=tuple(positivity_flags),
        psu_leverage_flags=tuple(psu_leverage_flags),
        warnings=tuple(warnings),
        report=report,
    )


def build_survey_adjusted_signal(
    full_signal: object,
    design_spec: SurveyDesignSpec,
    sampling_spec: SamplingModelSpec | None = None,
    *,
    augmentation: float | np.ndarray | None = None,
    estimand_label: str = "generic",
    estimand: Literal["generic", "ate", "att", "subgroup_mean"] = "generic",
    treatment: np.ndarray | None = None,
    propensity: np.ndarray | None = None,
    subgroup: np.ndarray | None = None,
    target_treatment: Literal[0, 1] = 1,
    variance_backend: SurveyVarianceBackend | None = None,
    normalization: Literal["hajek", "horvitz_thompson"] = "hajek",
    alpha: float = 0.05,
) -> SurveyAdjustedSignalResult:
    """Wrap a full-data orthogonal signal in a complex-survey adjustment."""
    signal = _extract_signal_array(full_signal)
    if signal.size != design_spec.n_obs:
        raise ValueError(
            f"full_signal length {signal.size} does not match design n_obs {design_spec.n_obs}"
        )

    if sampling_spec is not None:
        n_sampling = sampling_spec.n_obs()
        if n_sampling is not None and n_sampling != design_spec.n_obs:
            raise ValueError(
                f"sampling spec length {n_sampling} does not match design n_obs {design_spec.n_obs}"
            )
        sampled = (
            _to_1d_float("sampled", sampling_spec.sampled, expected_size=design_spec.n_obs)
            if sampling_spec.sampled is not None
            else np.ones(design_spec.n_obs, dtype=float)
        )
    else:
        sampled = np.ones(design_spec.n_obs, dtype=float)
    sampled = np.where(sampled > 0.0, 1.0, 0.0)

    inverse_inclusion = resolve_inverse_inclusion_weights(
        design_spec,
        sampling_spec,
        normalization=normalization,
    )
    augmentation_arr = _broadcast_augmentation(augmentation, design_spec.n_obs)
    observed_signal = _compute_observed_signal(signal, augmentation_arr, sampled, inverse_inclusion)

    binder_variance = compute_binder_linearized_variance(
        observed_signal,
        strata=design_spec.strata,
        psu=design_spec.psu,
    )
    estimate = float(np.mean(observed_signal))
    std_error = binder_variance.standard_error
    variance_method = binder_variance.method
    notes: list[str] = list(binder_variance.notes)

    if variance_backend is None:
        variance_backend = SurveyVarianceBackend()
    if variance_backend.method != "binder":
        if design_spec.replicate_weights is None:
            notes.append("replicate_backend_requested_without_replicates_fallback_to_binder")
        else:
            replicate_variance = compute_replicate_weight_variance(
                signal,
                design_spec=design_spec,
                sampling_spec=sampling_spec,
                augmentation=augmentation_arr,
                normalization=normalization,
                method=variance_backend.method,
                scale=variance_backend.scale,
                full_sample_estimate=estimate,
            )
            std_error = replicate_variance.standard_error
            variance_method = replicate_variance.method
            notes.extend(replicate_variance.notes)

    z_value = _normal_quantile(alpha)
    ci = (
        float(estimate - z_value * std_error),
        float(estimate + z_value * std_error),
    )

    diagnostic = diagnose_weight_regime(
        design_spec,
        sampling_spec=sampling_spec,
        estimand=estimand,
        treatment=treatment,
        propensity=propensity,
        subgroup=subgroup,
        target_treatment=target_treatment,
        influence_values=binder_variance.unit_influence,
    )
    notes = list(diagnostic.warnings) + notes

    effective_n = (
        diagnostic.combined_weight_ess
        if diagnostic.combined_weight_ess > 0.0
        else binder_variance.effective_n
    )
    return SurveyAdjustedSignalResult(
        estimate=estimate,
        std_error=std_error,
        ci=ci,
        estimand_label=estimand_label,
        observed_signal=observed_signal,
        full_signal=signal,
        augmentation=augmentation_arr,
        inverse_inclusion_weights=inverse_inclusion,
        design_effect=max(binder_variance.design_effect, diagnostic.design_effect_proxy),
        effective_n=float(effective_n),
        weight_regime=diagnostic.weight_regime,
        claim_level=diagnostic.claim_level,
        positivity_flags=diagnostic.positivity_flags,
        psu_leverage_flags=diagnostic.psu_leverage_flags,
        influence_values_unit=binder_variance.unit_influence,
        influence_values_psu=binder_variance.psu_influence,
        psu_labels=binder_variance.psu_labels,
        variance_method=variance_method,
        notes=tuple(notes),
        diagnostic=diagnostic,
    )


def build_psu_stratified_cross_fit_schedule(
    strata: np.ndarray,
    psu: np.ndarray,
    *,
    n_folds: int = 5,
    seed: int = 42,
) -> PSUStratifiedCrossFitSchedule:
    """Assign folds at the PSU-within-strata level."""
    strata_arr = _to_1d_labels("strata", strata)
    psu_arr = _to_1d_labels("psu", psu, expected_size=strata_arr.size)
    n_obs = strata_arr.size
    n_folds = max(int(n_folds), 2)
    fold_ids = np.full(n_obs, -1, dtype=int)
    rng = np.random.default_rng(seed)
    warnings: list[str] = []
    fallback_used: Literal["none", "round_robin_strata", "single_psu_strata"] = "none"
    psu_counts_by_stratum: dict[str, int] = {}

    for stratum in np.unique(strata_arr):
        in_stratum = strata_arr == stratum
        psu_ids = np.unique(psu_arr[in_stratum])
        rng.shuffle(psu_ids)
        psu_counts_by_stratum[str(stratum)] = int(psu_ids.size)
        if psu_ids.size < n_folds and fallback_used == "none":
            fallback_used = "round_robin_strata"
        if psu_ids.size < 2:
            fallback_used = "single_psu_strata"
            warnings.append(f"single_psu_stratum={stratum}")
        for offset, cluster in enumerate(psu_ids):
            fold = int(offset % n_folds)
            fold_ids[in_stratum & (psu_arr == cluster)] = fold

    if np.any(fold_ids < 0):
        raise RuntimeError("failed to assign all observations to a cross-fit fold")

    return PSUStratifiedCrossFitSchedule(
        fold_ids=fold_ids,
        n_folds=n_folds,
        fallback_used=fallback_used,
        warnings=tuple(warnings),
        psu_counts_by_stratum=psu_counts_by_stratum,
    )


def _phase1_auxiliaries_from_state(
    state: Mapping[str, Any],
    n_obs: int,
) -> Mapping[str, np.ndarray] | None:
    if "phase1_auxiliaries" in state:
        raw = state["phase1_auxiliaries"]
        if isinstance(raw, Mapping):
            return {
                str(key): _to_1d_float(f"phase1_auxiliaries[{key!r}]", value, expected_size=n_obs)
                for key, value in raw.items()
            }
    if "phase1_auxiliaries_matrix" in state:
        aux_matrix = _to_2d_float(
            "phase1_auxiliaries_matrix",
            state["phase1_auxiliaries_matrix"],
            expected_rows=n_obs,
        )
        return {f"aux_{idx}": aux_matrix[:, idx] for idx in range(aux_matrix.shape[1])}
    return None


def _build_design_feature_matrix(
    design_spec: SurveyDesignSpec,
    sampling_spec: SamplingModelSpec | None,
) -> np.ndarray | None:
    parts: list[np.ndarray] = []
    if sampling_spec is not None and sampling_spec.phase1_auxiliaries:
        for key in sorted(sampling_spec.phase1_auxiliaries):
            parts.append(
                _to_1d_float(
                    f"phase1_auxiliaries[{key!r}]",
                    sampling_spec.phase1_auxiliaries[key],
                    expected_size=design_spec.n_obs,
                )[:, None]
            )
    if design_spec.strata is not None and np.unique(design_spec.strata).size > 1:
        parts.append(_encode_labels(design_spec.strata)[:, None])
    if design_spec.psu is not None and np.unique(design_spec.psu).size > 1:
        parts.append(_encode_labels(design_spec.psu)[:, None])
    if not parts:
        return None
    return np.column_stack(parts)


def _estimate_design_augmentation(
    full_signal: np.ndarray,
    *,
    design_spec: SurveyDesignSpec,
    sampling_spec: SamplingModelSpec | None = None,
    mode: Literal["auto", "none", "mean", "phase1_linear"] = "auto",
) -> np.ndarray:
    signal = _to_1d_float("full_signal", full_signal, expected_size=design_spec.n_obs)
    if sampling_spec is not None and sampling_spec.sampled is not None:
        sampled = (
            _to_1d_float(
                "sampled",
                sampling_spec.sampled,
                expected_size=design_spec.n_obs,
            )
            > 0.5
        )
    else:
        sampled = np.ones(design_spec.n_obs, dtype=bool)
    if not np.any(sampled):
        sampled = np.ones(design_spec.n_obs, dtype=bool)

    if mode == "none":
        return np.zeros(design_spec.n_obs, dtype=float)

    constant = _weighted_mean(signal[sampled], design_spec.weights[sampled])
    if mode == "mean":
        return np.full(design_spec.n_obs, constant, dtype=float)

    features = _build_design_feature_matrix(design_spec, sampling_spec)
    if features is None:
        return np.full(design_spec.n_obs, constant, dtype=float)

    beta = _fit_weighted_linear(features[sampled], signal[sampled], design_spec.weights[sampled])
    fitted = _predict_linear(features, beta)
    return fitted.astype(float)


def _fit_cross_fitted_nuisances(
    x: np.ndarray,
    y: np.ndarray,
    treatment: np.ndarray,
    design_weights: np.ndarray,
    sampled: np.ndarray,
    *,
    strata: np.ndarray | None,
    psu: np.ndarray | None,
    n_folds: int,
    seed: int,
    min_propensity: float,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    PSUStratifiedCrossFitSchedule,
    dict[str, Any],
]:
    n_obs = x.shape[0]
    if strata is None:
        strata_arr = np.zeros(n_obs, dtype=object)
    else:
        strata_arr = _to_1d_labels("strata", strata, expected_size=n_obs)
    if psu is None:
        psu_arr = np.arange(n_obs, dtype=object)
    else:
        psu_arr = _to_1d_labels("psu", psu, expected_size=n_obs)

    schedule = build_psu_stratified_cross_fit_schedule(
        strata_arr,
        psu_arr,
        n_folds=n_folds,
        seed=seed,
    )
    fold_ids = schedule.fold_ids
    observed_outcome = (sampled > 0.5) & np.isfinite(y)
    treated_mask = treatment > 0.5
    control_mask = ~treated_mask

    global_propensity = float(
        np.clip(
            _weighted_mean(treatment, design_weights),
            min_propensity,
            1.0 - min_propensity,
        )
    )
    if np.any(observed_outcome & treated_mask):
        global_mu1 = _weighted_mean(
            y[observed_outcome & treated_mask],
            design_weights[observed_outcome & treated_mask],
        )
    else:
        global_mu1 = (
            _weighted_mean(y[observed_outcome], design_weights[observed_outcome])
            if np.any(observed_outcome)
            else 0.0
        )
    if np.any(observed_outcome & control_mask):
        global_mu0 = _weighted_mean(
            y[observed_outcome & control_mask],
            design_weights[observed_outcome & control_mask],
        )
    else:
        global_mu0 = (
            _weighted_mean(y[observed_outcome], design_weights[observed_outcome])
            if np.any(observed_outcome)
            else 0.0
        )

    propensity = np.full(n_obs, global_propensity, dtype=float)
    mu1 = np.full(n_obs, global_mu1, dtype=float)
    mu0 = np.full(n_obs, global_mu0, dtype=float)
    warnings: list[str] = list(schedule.warnings)

    for fold in np.unique(fold_ids):
        test_mask = fold_ids == fold
        train_mask = ~test_mask

        train_propensity = train_mask
        if np.sum(train_propensity) < 2 or np.unique(treatment[train_propensity]).size < 2:
            warnings.append(f"propensity_constant_fold={int(fold)}")
            propensity[test_mask] = global_propensity
        else:
            beta_e = _fit_weighted_logistic(
                x[train_propensity],
                treatment[train_propensity],
                design_weights[train_propensity],
            )
            propensity[test_mask] = _predict_logistic(x[test_mask], beta_e)

        train_treated = train_mask & observed_outcome & treated_mask
        if np.sum(train_treated) < 2:
            warnings.append(f"mu1_constant_fold={int(fold)}")
            mu1[test_mask] = global_mu1
        else:
            beta_mu1 = _fit_weighted_linear(
                x[train_treated],
                y[train_treated],
                design_weights[train_treated],
            )
            mu1[test_mask] = _predict_linear(x[test_mask], beta_mu1)

        train_control = train_mask & observed_outcome & control_mask
        if np.sum(train_control) < 2:
            warnings.append(f"mu0_constant_fold={int(fold)}")
            mu0[test_mask] = global_mu0
        else:
            beta_mu0 = _fit_weighted_linear(
                x[train_control],
                y[train_control],
                design_weights[train_control],
            )
            mu0[test_mask] = _predict_linear(x[test_mask], beta_mu0)

    propensity = np.clip(propensity, min_propensity, 1.0 - min_propensity)
    y_filled = np.asarray(y, dtype=float).copy()
    factual_prediction = np.where(treated_mask, mu1, mu0)
    missing_mask = ~np.isfinite(y_filled)
    y_filled[missing_mask] = factual_prediction[missing_mask]

    nuisance_summary = {
        "source": "cross_fit_weighted_linear_logistic",
        "cross_fit_folds": int(schedule.n_folds),
        "schedule_fallback": schedule.fallback_used,
        "schedule_warnings": list(schedule.warnings),
        "warnings": sorted(set(warnings)),
        "propensity_min": float(np.min(propensity)),
        "propensity_max": float(np.max(propensity)),
        "mu1_mean": float(np.mean(mu1)),
        "mu0_mean": float(np.mean(mu0)),
    }
    return propensity, mu1, mu0, y_filled, schedule, nuisance_summary


def _resolve_sampling_spec(state: Mapping[str, Any], n_obs: int) -> SamplingModelSpec:
    sampled = _state_optional_vector(state, "sampled", n=n_obs)
    if sampled is None:
        outcome = _state_optional_vector(state, "Y", n=n_obs, allow_nan=True)
        if outcome is not None and np.any(~np.isfinite(outcome)):
            sampled = np.where(np.isfinite(outcome), 1.0, 0.0)
    inclusion_probabilities = _state_optional_vector(state, "inclusion_probabilities", n=n_obs)
    phase1_auxiliaries = _phase1_auxiliaries_from_state(state, n_obs)
    calibration_vars = tuple(str(item) for item in state.get("calibration_vars", ()))
    informative_sampling_suspected = bool(state.get("informative_sampling_suspected", False))
    return SamplingModelSpec(
        inclusion_probabilities=inclusion_probabilities,
        sampled=sampled,
        phase1_auxiliaries=phase1_auxiliaries,
        calibration_vars=calibration_vars,
        informative_sampling_suspected=informative_sampling_suspected,
    )


def _resolve_design_spec(state: Mapping[str, Any], n_obs: int, provenance: str) -> SurveyDesignSpec:
    weights = _state_optional_vector(state, "weights", n=n_obs)
    if weights is None:
        weights = _state_vector(state, "base_weights", n=n_obs)
    strata = _state_optional_labels(state, "strata", n=n_obs)
    psu = _state_optional_labels(state, "psu", n=n_obs)
    if psu is None:
        psu = _state_optional_labels(state, "clusters", n=n_obs)
    fpc = _state_optional_vector(state, "fpc", n=n_obs)
    replicate_weights = _state_optional_matrix(state, "replicate_weights", n=n_obs)
    return SurveyDesignSpec(
        weights=weights,
        strata=strata,
        psu=psu,
        fpc=fpc,
        replicate_weights=replicate_weights,
        provenance=provenance,
    )


def _build_semiparametric_payload(
    result: SurveyAdjustedSignalResult,
    *,
    schedule: PSUStratifiedCrossFitSchedule,
    nuisance_summary: Mapping[str, Any],
    propensity: np.ndarray,
    mu1: np.ndarray,
    mu0: np.ndarray,
    sampled: np.ndarray,
    recommended_estimand: str | None = None,
) -> dict[str, Any]:
    payload = {
        "estimate": float(result.estimate),
        "std_error": float(result.std_error),
        "ci": [float(result.ci[0]), float(result.ci[1])],
        "estimand_label": result.estimand_label,
        "design_effect": float(result.design_effect),
        "effective_n": float(result.effective_n),
        "weight_regime": result.weight_regime,
        "claim_level": result.claim_level,
        "positivity_flags": list(result.positivity_flags),
        "psu_leverage_flags": list(result.psu_leverage_flags),
        "variance_method": result.variance_method,
        "notes": list(result.notes),
        "influence_values_unit": result.influence_values_unit.tolist(),
        "influence_values_psu": result.influence_values_psu.tolist(),
        "psu_labels": [[str(label[0]), str(label[1])] for label in result.psu_labels],
        "observed_signal": result.observed_signal.tolist(),
        "full_signal": result.full_signal.tolist(),
        "augmentation": result.augmentation.tolist(),
        "inverse_inclusion_weights": result.inverse_inclusion_weights.tolist(),
        "diagnostic": _jsonify(result.diagnostic),
        "cross_fit_schedule": _jsonify(schedule),
        "nuisance_summary": _jsonify(nuisance_summary),
        "nuisance_predictions": {
            "propensity": propensity.tolist(),
            "mu1": mu1.tolist(),
            "mu0": mu0.tolist(),
        },
        "sampled": sampled.tolist(),
    }
    if recommended_estimand is not None:
        payload["recommended_estimand"] = recommended_estimand
    return payload


def _run_survey_semiparametric_method(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    estimand: Literal["ate", "att", "subgroup_mean"],
) -> dict[str, Any]:
    x = _state_matrix(state, "X")
    n_obs = x.shape[0]
    y = _state_vector(state, "Y", n=n_obs, allow_nan=True)
    treatment = _state_vector(state, "treatment", n=n_obs)
    if np.any((treatment < 0.0) | (treatment > 1.0)):
        raise ValueError("treatment must lie in [0, 1]")

    provenance = str(params.get("provenance", state.get("provenance", "base")))
    design_spec = _resolve_design_spec(state, n_obs, provenance)
    sampling_spec = _resolve_sampling_spec(state, n_obs)
    sampled = (
        sampling_spec.sampled.copy()
        if sampling_spec.sampled is not None
        else np.ones(n_obs, dtype=float)
    )
    observed_mask = (sampled > 0.5) & np.isfinite(y)
    if np.any(sampled > 0.5) and not np.any(observed_mask):
        raise ValueError("At least one sampled observation must have an observed outcome")

    prefit_propensity = _state_optional_vector(state, "propensity", n=n_obs)
    prefit_mu1 = _state_optional_vector(state, "mu1", n=n_obs)
    prefit_mu0 = _state_optional_vector(state, "mu0", n=n_obs)

    min_propensity = max(float(params.get("min_propensity", 1e-3)), 1e-6)
    n_folds = max(2, int(params.get("crossfit_folds", 5)))
    seed = int(params.get("seed", params.get("__seed__", 42)))
    normalization = str(params.get("normalization", "hajek"))
    if normalization not in {"hajek", "horvitz_thompson"}:
        raise ValueError("normalization must be 'hajek' or 'horvitz_thompson'")
    alpha = float(params.get("alpha", 0.05))
    augmentation_mode = str(params.get("augmentation_mode", "auto"))
    if augmentation_mode not in {"auto", "none", "mean", "phase1_linear"}:
        raise ValueError("augmentation_mode must be one of auto, none, mean, phase1_linear")

    if prefit_propensity is not None and prefit_mu1 is not None and prefit_mu0 is not None:
        propensity = np.clip(prefit_propensity, min_propensity, 1.0 - min_propensity)
        mu1 = prefit_mu1
        mu0 = prefit_mu0
        factual_prediction = np.where(treatment > 0.5, mu1, mu0)
        y_filled = np.asarray(y, dtype=float).copy()
        y_filled[~np.isfinite(y_filled)] = factual_prediction[~np.isfinite(y_filled)]
        schedule = build_psu_stratified_cross_fit_schedule(
            design_spec.strata
            if design_spec.strata is not None
            else np.zeros(n_obs, dtype=object),
            design_spec.psu if design_spec.psu is not None else np.arange(n_obs, dtype=object),
            n_folds=n_folds,
            seed=seed,
        )
        nuisance_summary = {
            "source": "prefit_external",
            "cross_fit_folds": int(schedule.n_folds),
            "schedule_fallback": schedule.fallback_used,
            "schedule_warnings": list(schedule.warnings),
            "propensity_min": float(np.min(propensity)),
            "propensity_max": float(np.max(propensity)),
            "mu1_mean": float(np.mean(mu1)),
            "mu0_mean": float(np.mean(mu0)),
        }
    else:
        propensity, mu1, mu0, y_filled, schedule, nuisance_summary = _fit_cross_fitted_nuisances(
            x,
            y,
            treatment,
            design_spec.weights,
            sampled,
            strata=design_spec.strata,
            psu=design_spec.psu,
            n_folds=n_folds,
            seed=seed,
            min_propensity=min_propensity,
        )

    if estimand == "ate":
        full_signal = compute_eif_ate(
            y_filled,
            treatment,
            propensity,
            mu1,
            mu0,
            min_propensity=min_propensity,
        )
        subgroup_mask = None
        target_treatment = 1
        estimand_label = "ate"
    elif estimand == "att":
        full_signal = compute_eif_att(
            y_filled,
            treatment,
            propensity,
            mu1,
            mu0,
            min_propensity=min_propensity,
        )
        subgroup_mask = None
        target_treatment = 1
        estimand_label = "att"
    else:
        subgroup = _to_1d_labels("subgroup", state["subgroup"], expected_size=n_obs)
        target_subgroup = params.get("target_group", params.get("target_subgroup", 1))
        target_treatment = int(params.get("target_treatment", 1))
        subgroup_mask = (subgroup == target_subgroup).astype(float)
        full_signal = compute_eif_subgroup_mean(
            y_filled,
            treatment,
            propensity,
            mu1,
            mu0,
            subgroup,
            target_treatment=target_treatment,
            target_group=target_subgroup,
            min_propensity=min_propensity,
        )
        estimand_label = f"subgroup_mean[a={target_treatment},b={target_subgroup}]"

    augmentation = _estimate_design_augmentation(
        full_signal.scores,
        design_spec=design_spec,
        sampling_spec=sampling_spec,
        mode=augmentation_mode,  # type: ignore[arg-type]
    )

    requested_variance_method = str(params.get("variance_method", "auto"))
    if requested_variance_method == "auto":
        actual_variance_method = "brr" if design_spec.replicate_weights is not None else "binder"
    else:
        actual_variance_method = requested_variance_method
    if actual_variance_method not in {"binder", "brr", "jk1", "bootstrap"}:
        raise ValueError("variance_method must be auto, binder, brr, jk1, or bootstrap")
    replicate_scale = params.get("replicate_scale")
    variance_backend = SurveyVarianceBackend(
        method=actual_variance_method,  # type: ignore[arg-type]
        scale=None if replicate_scale is None else float(replicate_scale),
    )

    adjusted = build_survey_adjusted_signal(
        full_signal,
        design_spec,
        sampling_spec,
        augmentation=augmentation,
        estimand_label=estimand_label,
        estimand=estimand,
        treatment=treatment,
        propensity=propensity,
        subgroup=subgroup_mask,
        target_treatment=target_treatment,  # type: ignore[arg-type]
        variance_backend=variance_backend,
        normalization=normalization,  # type: ignore[arg-type]
        alpha=alpha,
    )

    recommended_estimand = None
    if (
        estimand == "ate"
        and adjusted.claim_level != "design_dr_efficiency_claimable"
        and adjusted.positivity_flags
    ):
        recommended_estimand = "overlap"

    return {
        "result": _build_semiparametric_payload(
            adjusted,
            schedule=schedule,
            nuisance_summary=nuisance_summary,
            propensity=propensity,
            mu1=mu1,
            mu0=mu0,
            sampled=sampled,
            recommended_estimand=recommended_estimand,
        )
    }


def _semiparametric_input_slots(
    *,
    include_subgroup: bool = False,
) -> frozenset[SlotSpec]:
    slots = {
        SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
        SlotSpec("Y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
        SlotSpec("weights", SlotType.VECTOR, Unit("weight", "mass"), shape=("n_obs",)),
    }
    if include_subgroup:
        slots.add(
            SlotSpec(
                "subgroup",
                SlotType.VECTOR,
                Unit("subgroup", "label"),
                shape=("n_obs",),
            )
        )
    return frozenset(slots)


def _semiparametric_parameters() -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec(name="crossfit_folds", default=5),
        ParameterSpec(name="seed", default=42),
        ParameterSpec(name="min_propensity", default=1e-3),
        ParameterSpec(name="normalization", default="hajek"),
        ParameterSpec(name="augmentation_mode", default="auto"),
        ParameterSpec(name="variance_method", default="auto"),
        ParameterSpec(name="replicate_scale", default=None),
        ParameterSpec(name="alpha", default=0.05),
        ParameterSpec(name="provenance", default="base"),
        ParameterSpec(name="target_treatment", default=1),
        ParameterSpec(name="target_group", default=1),
    )


@foundry_method(
    namespace="survey.semiparametric",
    version="1.0.0",
    tags={"survey", "semiparametric", "aipw", "ate", "design-aware"},
)
class SurveySemiparametricATEEstimator:
    """Design-aware semiparametric ATE with survey-consistent diagnostics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ate",
        namespace="",
        version="0.0.0",
        input_slots=_semiparametric_input_slots(),
        output_slots=_result_slot(),
        parameters=_semiparametric_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Survey-aware doubly robust ATE estimation via a full-data EIF wrapped "
            "by design adjustment and Binder or replicate-weight variance."
        ),
        tags=frozenset({"survey", "semiparametric", "ate", "doubly-robust", "aipw"}),
        citations=(
            (
                "Hahn, J. (1998). On the role of the propensity score in efficient "
                "semiparametric estimation of average treatment effects."
            ),
            (
                "Binder, D. (1983). On the variances of asymptotically normal "
                "estimators from complex surveys."
            ),
            (
                "Rudolph, K.E. et al. (2024). TMLE of population treatment effects "
                "from survey subsamples."
            ),
        ),
        equations={
            "full_eif": "phi_F = m1(X) - m0(X) + A(Y-m1)/e - (1-A)(Y-m0)/(1-e)",
            "observed_signal": "phi_obs = kappa(D) + S d(D) {phi_F - kappa(D)}",
            "binder": "Var_hat = sum_h n_h/(n_h-1) sum_c (T_hc - Tbar_h)^2 / N^2",
        },
        when_to_use=(
            "Population ATE from stratified or clustered survey data where design "
            "weights, treatment, and covariates are observed."
        ),
        when_not_to_use=(
            "Severe overlap failures, clearly informative sampling beyond observed "
            "design variables, or missing outcomes that require an explicit nonresponse model."
        ),
        output_interpretation=(
            "result.claim_level states whether the design-weight regime supports an "
            "efficiency claim or only design-consistent doubly robust inference."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_survey_semiparametric_method(state, params, estimand="ate")


@foundry_method(
    namespace="survey.semiparametric",
    version="1.0.0",
    tags={"survey", "semiparametric", "att", "design-aware"},
)
class SurveySemiparametricATTEstimator:
    """Design-aware semiparametric ATT with survey-consistent diagnostics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="att",
        namespace="",
        version="0.0.0",
        input_slots=_semiparametric_input_slots(),
        output_slots=_result_slot(),
        parameters=_semiparametric_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Survey-aware doubly robust ATT estimation using the Hahn ATT EIF, "
            "design-side adjustment, and Binder or replicate-weight variance."
        ),
        tags=frozenset({"survey", "semiparametric", "att", "doubly-robust"}),
        citations=(
            (
                "Hahn, J. (1998). On the role of the propensity score in efficient "
                "semiparametric estimation of average treatment effects."
            ),
            (
                "Liang, W. & Wu, C. (2024). Weighted average treatment effects for "
                "probability survey samples."
            ),
            (
                "Binder, D. (1983). On the variances of asymptotically normal "
                "estimators from complex surveys."
            ),
        ),
        equations={
            "full_eif": "phi_F = A/p {Y-m0(X)} - (1-A)/p * e(X)/(1-e(X)) * {Y-m0(X)}",
            "observed_signal": "phi_obs = kappa(D) + S d(D) {phi_F - kappa(D)}",
        },
        when_to_use=(
            "Population ATT under complex survey weighting when treated and control "
            "units both have adequate overlap in the weighted target population."
        ),
        output_interpretation=(
            "estimate is the survey-weighted ATT; diagnostics summarize whether the "
            "weight regime remains claimable or only design-consistent."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_survey_semiparametric_method(state, params, estimand="att")


@foundry_method(
    namespace="survey.semiparametric",
    version="1.0.0",
    tags={"survey", "semiparametric", "subgroup", "conditional-mean", "design-aware"},
)
class SurveySemiparametricSubgroupMeanEstimator:
    """Design-aware semiparametric subgroup potential-outcome mean."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="subgroup_mean",
        namespace="",
        version="0.0.0",
        input_slots=_semiparametric_input_slots(include_subgroup=True),
        output_slots=_result_slot(),
        parameters=_semiparametric_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Survey-aware semiparametric estimation of E[Y^a | B=b] using a "
            "full-data subgroup EIF plus design adjustment and weight-regime diagnostics."
        ),
        tags=frozenset({"survey", "semiparametric", "subgroup_mean", "conditional-mean"}),
        citations=(
            "Benkeser, D. et al. Doubly robust nonparametric inference on treatment effects.",
            (
                "Binder, D. (1983). On the variances of asymptotically normal "
                "estimators from complex surveys."
            ),
            "Rose, S. & van der Laan, M. (2011). TMLE for two-stage sampling designs.",
        ),
        equations={
            "full_eif": "phi_F = 1(B=b)/P(B=b) * [1(A=a)(Y-m_a)/P(A=a|X) + m_a(X)]",
            "observed_signal": "phi_obs = kappa(D) + S d(D) {phi_F - kappa(D)}",
        },
        when_to_use=(
            "Subgroup treatment-specific mean estimation when the subgroup is "
            "discrete and sufficiently represented in the weighted population."
        ),
        output_interpretation=(
            "estimate targets E[Y^a | B=b] for the requested arm and subgroup label."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        return _run_survey_semiparametric_method(state, params, estimand="subgroup_mean")


__all__ = [
    "LinearizedSurveyVariance",
    "PSUStratifiedCrossFitSchedule",
    "ReplicateSurveyVariance",
    "SamplingModelSpec",
    "SurveyAdjustedSignalResult",
    "SurveyDesignSpec",
    "SurveySemiparametricATEEstimator",
    "SurveySemiparametricATTEstimator",
    "SurveySemiparametricSubgroupMeanEstimator",
    "SurveyVarianceBackend",
    "WeightRegimeDiagnostic",
    "build_psu_stratified_cross_fit_schedule",
    "build_survey_adjusted_signal",
    "combine_weights_for_estimand",
    "compute_binder_linearized_variance",
    "compute_replicate_weight_variance",
    "diagnose_weight_regime",
    "resolve_inverse_inclusion_weights",
]
