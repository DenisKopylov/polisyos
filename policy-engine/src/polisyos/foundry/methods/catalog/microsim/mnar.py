"""MNAR sensitivity bounds for income imputation in microsimulation pipelines."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from .advanced import ImputationModelEstimator
from .protocols import (
    ImputationResult,
    MNARIncomeAssumptionVector,
    MNARIncomeBoundsDiagnostics,
    MNARIncomeBoundsInterval,
    MNARIncomeBoundsProvenance,
    MNARIncomeBoundsResult,
    MNARIncomeBoundsTarget,
    SurveyMicroData,
)

_ALL_GROUP = "__all__"
_ALL_MISSING = "all_missing"
_DEFAULT_GAMMA_RANGE = (-1.0, 1.0)
_DEFAULT_DELTA_RANGE = (-5000.0, 5000.0)
_DEFAULT_LAMBDA_RANGE = (0.9, 1.1)


def _survey_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0.0:
        return float(np.mean(values)) if values.size else 0.0
    return float(np.sum(values * weights) / total)


def _weighted_std(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    mean = _weighted_mean(values, weights)
    total = float(np.sum(weights))
    if total <= 0.0:
        return float(np.std(values))
    variance = float(np.sum(weights * np.square(values - mean)) / total)
    return float(math.sqrt(max(variance, 0.0)))


def _effective_sample_size(weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    squared = float(np.sum(np.square(weights)))
    if total <= 0.0 or squared <= 0.0:
        return 0.0
    return float((total * total) / squared)


def _normal_cdf(values: np.ndarray) -> np.ndarray:
    scaled = np.asarray(values, dtype=float) / math.sqrt(2.0)
    erf = np.vectorize(math.erf, otypes=[float])(scaled)
    return 0.5 * (1.0 + erf)


def _response_ratio(values: np.ndarray) -> np.ndarray:
    probs = np.clip(_normal_cdf(values), 1e-12, 1.0 - 1e-12)
    return (1.0 - probs) / probs


def _coerce_interval(
    raw: Any,
    *,
    default: tuple[float, float],
    name: str,
) -> tuple[float, float]:
    if raw is None:
        return default
    values = np.asarray(raw, dtype=float).reshape(-1)
    if values.size != 2:
        raise ValueError(f"{name} must be a 2-element interval")
    lower = float(values[0])
    upper = float(values[1])
    if lower > upper:
        raise ValueError(f"{name} must be ordered")
    return (lower, upper)


def _coerce_grid(
    explicit: Any,
    *,
    default_interval: tuple[float, float],
    n_points: int,
    name: str,
) -> np.ndarray:
    if explicit is not None:
        values = np.asarray(explicit, dtype=float).reshape(-1)
        if values.size == 0:
            raise ValueError(f"{name} grid must be non-empty")
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} grid must be finite")
        return np.unique(np.sort(values.astype(float)))
    lower, upper = default_interval
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ValueError(f"{name} interval must be finite")
    if n_points <= 1 or math.isclose(lower, upper):
        return np.asarray([lower], dtype=float)
    return np.linspace(lower, upper, int(max(n_points, 2)), dtype=float)


def _resolve_component_grid(
    label: str,
    *,
    common_grid: np.ndarray,
    overrides: Any,
    default_interval: tuple[float, float],
    n_points: int,
    name: str,
) -> np.ndarray:
    if isinstance(overrides, Mapping) and label in overrides:
        raw = overrides[label]
        if isinstance(raw, Mapping):
            if "grid" in raw:
                return _coerce_grid(
                    raw["grid"], default_interval=default_interval, n_points=n_points, name=name
                )
            interval = _coerce_interval(
                raw.get("range"), default=default_interval, name=f"{name}_range"
            )
            return _coerce_grid(None, default_interval=interval, n_points=n_points, name=name)
        values = np.asarray(raw, dtype=float).reshape(-1)
        if values.size == 2:
            interval = (float(values[0]), float(values[1]))
            if interval[0] > interval[1]:
                raise ValueError(f"{name} override for '{label}' must be ordered")
            return _coerce_grid(None, default_interval=interval, n_points=n_points, name=name)
        return _coerce_grid(values, default_interval=default_interval, n_points=n_points, name=name)
    return common_grid


def _resolve_reference_value(
    label: str,
    *,
    common_reference: Any,
    overrides: Any,
    default_value: float,
    interval: tuple[float, float] | None = None,
) -> float:
    if isinstance(overrides, Mapping) and label in overrides:
        raw = overrides[label]
        if isinstance(raw, Mapping):
            if "value" in raw:
                raw = raw["value"]
            elif "reference" in raw:
                raw = raw["reference"]
        value = float(raw)
    elif common_reference is not None:
        value = float(common_reference)
    else:
        value = float(default_value)
    if interval is not None:
        value = min(max(value, interval[0]), interval[1])
    return value


def _coerce_group_labels(raw: Any, *, n_obs: int) -> np.ndarray:
    if raw is None:
        return np.full(n_obs, _ALL_GROUP, dtype=object)
    labels = np.asarray(raw, dtype=object).reshape(-1)
    if labels.size != n_obs:
        raise ValueError("group_labels must align with the number of observations")
    normalized = [
        _ALL_GROUP if item is None or not str(item).strip() else str(item).strip()
        for item in labels
    ]
    return np.asarray(normalized, dtype=object)


def _coerce_missingness_types(raw: Any, *, missing_mask: np.ndarray) -> np.ndarray:
    n_obs = int(missing_mask.size)
    labels = np.full(n_obs, "", dtype=object)
    if raw is None:
        labels[missing_mask] = _ALL_MISSING
        return labels
    values = np.asarray(raw, dtype=object).reshape(-1)
    if values.size == n_obs:
        normalized = [
            "" if item is None or not str(item).strip() else str(item).strip() for item in values
        ]
        labels = np.asarray(normalized, dtype=object)
        labels[~missing_mask] = ""
        if np.any(labels[missing_mask] == ""):
            raise ValueError("missingness_types must be specified for each missing income")
        return labels
    if values.size == int(np.sum(missing_mask)):
        normalized = [
            _ALL_MISSING if item is None or not str(item).strip() else str(item).strip()
            for item in values
        ]
        labels[missing_mask] = np.asarray(normalized, dtype=object)
        return labels
    raise ValueError(
        "missingness_types must align with either n_obs or the number of missing incomes"
    )


def _coerce_string_tuple(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        value = raw.strip()
        return (value,) if value else ()
    values = np.asarray(raw, dtype=object).reshape(-1)
    normalized = [str(item).strip() for item in values if str(item).strip()]
    return tuple(normalized)


def _coerce_equivalence_scale(raw: Any, *, n_obs: int) -> tuple[np.ndarray, str | None]:
    if raw is None:
        return np.ones(n_obs, dtype=float), None
    values = np.asarray(raw, dtype=float).reshape(-1)
    if values.size == 1:
        scalar = float(values[0])
        if not math.isfinite(scalar) or scalar <= 0.0:
            raise ValueError("equivalence_scale must be strictly positive")
        return np.full(n_obs, scalar, dtype=float), "scalar_param_or_metadata"
    if values.size != n_obs:
        raise ValueError("equivalence_scale must be a scalar or align with n_obs")
    if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
        raise ValueError("equivalence_scale must be finite and strictly positive")
    return values.astype(float), "vector_param_or_metadata"


def _resolve_support_bounds(
    income: np.ndarray,
    observed_mask: np.ndarray,
    *,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[tuple[float, float], list[str], str]:
    warnings: list[str] = []
    lower = params.get("support_lower", metadata.get("income_support_lower"))
    upper = params.get("support_upper", metadata.get("income_support_upper"))
    if lower is not None and upper is not None:
        interval = _coerce_interval((lower, upper), default=(0.0, 0.0), name="support_bounds")
        return interval, warnings, "user_or_metadata"
    observed = income[observed_mask]
    if observed.size == 0:
        raise ValueError(
            "support_lower and support_upper are required when all market_income values are missing"
        )
    inferred_lower = float(min(np.nanmin(observed), 0.0))
    inferred_upper = float(np.nanmax(observed))
    if lower is None:
        lower = inferred_lower
        warnings.append("support_lower_defaulted_from_observed_income")
    if upper is None:
        upper = inferred_upper
        warnings.append("support_upper_defaulted_from_observed_income")
    interval = _coerce_interval((lower, upper), default=(0.0, 0.0), name="support_bounds")
    return interval, warnings, "observed_income_default"


def _transform_income(
    income: np.ndarray,
    *,
    scale: str,
    equivalence_scale: np.ndarray,
) -> np.ndarray:
    raw = np.asarray(income, dtype=float)
    if scale == "raw_income":
        return raw
    if scale == "log_income":
        return np.log1p(np.clip(raw, 0.0, None))
    if scale == "equivalized_income":
        return raw / equivalence_scale
    raise ValueError("unsupported target_scale")


def _target_support_arrays(
    support_bounds: tuple[float, float],
    *,
    n_obs: int,
    scale: str,
    equivalence_scale: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    lower, upper = support_bounds
    lower_arr = np.full(n_obs, lower, dtype=float)
    upper_arr = np.full(n_obs, upper, dtype=float)
    return (
        _transform_income(lower_arr, scale=scale, equivalence_scale=equivalence_scale),
        _transform_income(upper_arr, scale=scale, equivalence_scale=equivalence_scale),
    )


def _score_values(
    raw_income: np.ndarray,
    target_income: np.ndarray,
    weights: np.ndarray,
    score_name: str,
    *,
    equivalence_scale: np.ndarray,
) -> np.ndarray:
    if score_name == "standardized_raw_income":
        transformed = np.asarray(raw_income, dtype=float)
    elif score_name == "standardized_log_income":
        transformed = np.log1p(np.clip(np.asarray(raw_income, dtype=float), 0.0, None))
    elif score_name == "standardized_equivalized_income":
        transformed = np.asarray(raw_income, dtype=float) / equivalence_scale
    elif score_name == "standardized_target_income":
        transformed = np.asarray(target_income, dtype=float)
    else:
        raise ValueError(
            "income_score must be one of {'standardized_raw_income', 'standardized_log_income', "
            "'standardized_equivalized_income', 'standardized_target_income'}"
        )
    std = _weighted_std(transformed, weights)
    if std <= 1e-12:
        return np.zeros_like(transformed, dtype=float)
    mean = _weighted_mean(transformed, weights)
    return (transformed - mean) / std


def _selection_logit_curve(
    observed_target_income: np.ndarray,
    observed_weights: np.ndarray,
    score_values: np.ndarray,
    gamma_grid: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    curve = np.zeros_like(gamma_grid, dtype=float)
    effective_sample_sizes = np.zeros_like(gamma_grid, dtype=float)
    for idx, gamma in enumerate(gamma_grid):
        tilt = np.exp(np.clip(-float(gamma) * score_values, -60.0, 60.0))
        donor_weights = observed_weights * tilt
        curve[idx] = _weighted_mean(observed_target_income, donor_weights)
        effective_sample_sizes[idx] = _effective_sample_size(donor_weights)
    return curve, effective_sample_sizes


def _solve_probit_alpha(
    score_values: np.ndarray,
    observed_weights: np.ndarray,
    response_rate: float,
    gamma: float,
) -> tuple[float, bool]:
    if response_rate <= 0.0 or response_rate >= 1.0:
        return 0.0, True
    target = (1.0 - response_rate) / response_rate

    def objective(alpha: float) -> float:
        ratio = _response_ratio(alpha + float(gamma) * score_values)
        return _weighted_mean(ratio, observed_weights) - target

    lower = -12.0
    upper = 12.0
    f_lower = objective(lower)
    f_upper = objective(upper)
    for _ in range(12):
        if f_lower >= 0.0 and f_upper <= 0.0:
            break
        lower *= 1.5
        upper *= 1.5
        f_lower = objective(lower)
        f_upper = objective(upper)
    else:
        if abs(f_lower) < abs(f_upper):
            return lower, False
        return upper, False

    for _ in range(80):
        midpoint = 0.5 * (lower + upper)
        f_mid = objective(midpoint)
        if abs(f_mid) <= 1e-8:
            return midpoint, True
        if f_mid > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return 0.5 * (lower + upper), False


def _selection_probit_curve(
    observed_target_income: np.ndarray,
    observed_weights: np.ndarray,
    score_values: np.ndarray,
    gamma_grid: np.ndarray,
    response_rate: float,
) -> tuple[np.ndarray, np.ndarray, bool, np.ndarray]:
    curve = np.zeros_like(gamma_grid, dtype=float)
    solved_alpha = np.zeros_like(gamma_grid, dtype=float)
    effective_sample_sizes = np.zeros_like(gamma_grid, dtype=float)
    converged = True
    for idx, gamma in enumerate(gamma_grid):
        alpha, solved = _solve_probit_alpha(
            score_values, observed_weights, response_rate, float(gamma)
        )
        solved_alpha[idx] = alpha
        converged &= solved
        ratio = _response_ratio(alpha + float(gamma) * score_values)
        donor_weights = observed_weights * ratio
        curve[idx] = _weighted_mean(observed_target_income, donor_weights)
        effective_sample_sizes[idx] = _effective_sample_size(donor_weights)
    return curve, solved_alpha, converged, effective_sample_sizes


def _pattern_mixture_surface(
    observed_target_income: np.ndarray,
    observed_weights: np.ndarray,
    delta_grid: np.ndarray,
    lambda_grid: np.ndarray,
    *,
    missing_support_lower: np.ndarray,
    missing_support_upper: np.ndarray,
    missing_weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    donor_weight_total = float(np.sum(observed_weights))
    if donor_weight_total <= 0.0:
        donor_weight_norm = np.full(
            observed_target_income.size, 1.0 / max(observed_target_income.size, 1), dtype=float
        )
    else:
        donor_weight_norm = observed_weights / donor_weight_total

    base = (
        delta_grid[:, None, None]
        + lambda_grid[None, :, None]
        * np.asarray(observed_target_income, dtype=float)[None, None, :]
    )
    surface = np.zeros((delta_grid.size, lambda_grid.size), dtype=float)
    clipped_share = np.zeros_like(surface)
    missing_weight_total = float(np.sum(missing_weights))
    if missing_weight_total <= 0.0:
        return surface, clipped_share
    missing_weight_norm = missing_weights / missing_weight_total

    for lower, upper, weight in zip(
        missing_support_lower.tolist(), missing_support_upper.tolist(), missing_weight_norm.tolist()
    ):
        clipped = np.clip(base, float(lower), float(upper))
        indicator = ((base < float(lower)) | (base > float(upper))).astype(float)
        surface += float(weight) * np.tensordot(clipped, donor_weight_norm, axes=([2], [0]))
        clipped_share += float(weight) * np.tensordot(indicator, donor_weight_norm, axes=([2], [0]))
    return surface, clipped_share


def _curve_monotonicity(curve: np.ndarray) -> str | None:
    if curve.size <= 1:
        return None
    diffs = np.diff(np.asarray(curve, dtype=float))
    tolerance = 1e-9
    if np.all(np.abs(diffs) <= tolerance):
        return "flat"
    if np.all(diffs <= tolerance):
        return "nonincreasing"
    if np.all(diffs >= -tolerance):
        return "nondecreasing"
    return "nonmonotone"


def _back_transform_rule(target_scale: str) -> str | None:
    if target_scale == "raw_income":
        return "identity"
    if target_scale == "log_income":
        return "no_exact_inverse_for_mean_log_income"
    if target_scale == "equivalized_income":
        return "multiply_by_equivalence_scale_at_unit_level"
    return None


def _taxonomy_entries(
    *,
    mechanism_class: str,
    lambda_interval: tuple[float, float] | None,
    missingness_types: np.ndarray,
    missing_mask: np.ndarray,
    external_anchors: tuple[str, ...],
) -> tuple[str, ...]:
    entries: list[str] = []
    if mechanism_class == "selection.logit":
        entries.append("mnar.selection.logit_income")
    elif mechanism_class == "selection.probit":
        entries.append("mnar.selection.probit_income")
    elif mechanism_class == "pattern_mixture.locscale":
        if (
            lambda_interval is not None
            and math.isclose(lambda_interval[0], 1.0)
            and math.isclose(lambda_interval[1], 1.0)
        ):
            entries.append("mnar.pattern_mixture.delta")
        else:
            entries.append("mnar.pattern_mixture.locscale")
    elif mechanism_class == "support_only":
        entries.append("mnar.support_only")

    observed_missingness_types = {
        str(label)
        for label in missingness_types[missing_mask].tolist()
        if str(label) and str(label) != _ALL_MISSING
    }
    if {"refusal", "dont_know"}.issubset(observed_missingness_types):
        entries.append("mnar.refusal_vs_dk_split")
    if external_anchors:
        entries.append("mnar.external_anchor_admin")
    return tuple(entries)


def _build_envelope(
    *,
    lower: float,
    upper: float,
    point_estimate: float,
    mechanism_class: str,
    target_scale: str,
) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=float(point_estimate),
        confidence_interval=(float(lower), float(upper)),
        confidence_level=None,
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.ANALYTICAL,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        metadata={
            "mechanism_class": mechanism_class,
            "estimand": "weighted_mean_income",
            "scale": target_scale,
        },
    )


@foundry_method(
    namespace="microsim.imputation",
    version="1.0.0",
    tags={"microsim", "imputation", "survey", "uncertainty"},
)
class MNARIncomeBoundsEstimator:
    """Compute MNAR sensitivity bounds while preserving the existing microsim imputation contract."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mnar_income_bounds",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("imputation", "json"),
                    contract_id=ImputationResult.contract_id,
                ),
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="mechanism_class", default="selection.logit"),
            ParameterSpec(name="target_scale", default="raw_income"),
            ParameterSpec(name="income_score", default="standardized_raw_income"),
            ParameterSpec(name="equivalence_scale", default=None),
            ParameterSpec(name="group_labels", default=None),
            ParameterSpec(name="missingness_types", default=None),
            ParameterSpec(name="external_anchors", default=None),
            ParameterSpec(name="additional_restrictions", default=None),
            ParameterSpec(name="support_lower", default=None),
            ParameterSpec(name="support_upper", default=None),
            ParameterSpec(name="gamma_range", default=_DEFAULT_GAMMA_RANGE),
            ParameterSpec(name="gamma_grid", default=None),
            ParameterSpec(name="gamma_overrides", default=None),
            ParameterSpec(name="reference_gamma", default=None),
            ParameterSpec(name="reference_gamma_overrides", default=None),
            ParameterSpec(name="delta_range", default=_DEFAULT_DELTA_RANGE),
            ParameterSpec(name="delta_grid", default=None),
            ParameterSpec(name="delta_overrides", default=None),
            ParameterSpec(name="reference_delta", default=None),
            ParameterSpec(name="reference_delta_overrides", default=None),
            ParameterSpec(name="lambda_range", default=_DEFAULT_LAMBDA_RANGE),
            ParameterSpec(name="lambda_grid", default=None),
            ParameterSpec(name="lambda_overrides", default=None),
            ParameterSpec(name="reference_lambda", default=None),
            ParameterSpec(name="reference_lambda_overrides", default=None),
            ParameterSpec(name="n_gamma_points", default=21),
            ParameterSpec(name="n_delta_points", default=11),
            ParameterSpec(name="n_lambda_points", default=11),
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
            "MNAR sensitivity bounds for survey income imputation using support-only, "
            "selection-model, and pattern-mixture scenarios."
        ),
        tags=frozenset({"microsim", "imputation", "survey", "uncertainty", "bounds"}),
        citations=(
            "Rubin, D. (1987). Multiple Imputation for Nonresponse in Surveys. Wiley.",
            "Little, R. (1993). Pattern-Mixture Models for Multivariate Incomplete Data.",
            "Diggle, P. & Kenward, M. (1994). Informative Drop-Out in Longitudinal Data Analysis.",
            "Manski, C. (1990). Nonparametric bounds on treatment effects.",
        ),
        when_to_use=(
            "Income item nonresponse when analysts need deterministic sensitivity intervals "
            "instead of a single MAR point repair."
        ),
        when_not_to_use=(
            "When a fully justified recoverability or external-anchor strategy is available "
            "and should replace sensitivity-only analysis."
        ),
        output_interpretation=(
            "Imputed_market_income remains a reference completed dataset; "
            "metadata['mnar_bounds'] carries the admissible MNAR envelope."
        ),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurveyMicroData:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return SurveyMicroData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurveyMicroData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state if isinstance(state, SurveyMicroData) else SurveyMicroData.model_validate(state)
        )
        income = np.asarray(data.market_income, dtype=float)
        weights = np.asarray(data.weights, dtype=float)
        observed_mask = np.isfinite(income)
        missing_mask = ~observed_mask
        metadata = dict(data.metadata)
        mechanism_class = str(params.get("mechanism_class", "selection.logit"))
        if mechanism_class not in {
            "selection.logit",
            "selection.probit",
            "pattern_mixture.locscale",
            "support_only",
        }:
            raise ValueError("unsupported mechanism_class")

        support_bounds, warnings, support_source = _resolve_support_bounds(
            income,
            observed_mask,
            params=params,
            metadata=metadata,
        )
        support_lower, support_upper = support_bounds
        target_scale = str(
            params.get(
                "target_scale",
                params.get("scale", metadata.get("mnar_target_scale", "raw_income")),
            )
        )
        if target_scale not in {"raw_income", "log_income", "equivalized_income"}:
            raise ValueError(
                "target_scale must be one of {'raw_income', 'log_income', 'equivalized_income'}"
            )
        score_name = str(
            params.get("income_score", metadata.get("mnar_income_score", "standardized_raw_income"))
        )
        equivalence_scale, equivalence_scale_source = _coerce_equivalence_scale(
            params.get("equivalence_scale", metadata.get("equivalence_scale")),
            n_obs=int(income.size),
        )
        if (
            target_scale == "equivalized_income"
            or score_name == "standardized_equivalized_income"
            or (score_name == "standardized_target_income" and target_scale == "equivalized_income")
        ) and equivalence_scale_source is None:
            warnings.append("equivalence_scale_defaulted_to_one")
        if (
            target_scale == "log_income" or score_name == "standardized_log_income"
        ) and support_lower < 0.0:
            warnings.append("log_scale_support_lower_clipped_to_zero")
        if np.any(observed_mask & (income < 0.0)) and (
            target_scale == "log_income" or score_name == "standardized_log_income"
        ):
            warnings.append("negative_income_clipped_for_log_scale")

        analysis_income = _transform_income(
            income,
            scale=target_scale,
            equivalence_scale=equivalence_scale,
        )
        target_support_lower_arr, target_support_upper_arr = _target_support_arrays(
            support_bounds,
            n_obs=int(income.size),
            scale=target_scale,
            equivalence_scale=equivalence_scale,
        )
        target_support_summary = (
            float(np.min(target_support_lower_arr)),
            float(np.max(target_support_upper_arr)),
        )
        external_anchors = _coerce_string_tuple(
            params.get("external_anchors")
            if params.get("external_anchors") is not None
            else metadata.get("external_anchors")
        )
        additional_restrictions = _coerce_string_tuple(
            params.get("additional_restrictions")
            if params.get("additional_restrictions") is not None
            else metadata.get("mnar_additional_restrictions")
        )

        if np.any(observed_mask):
            baseline_payload = ImputationModelEstimator.pure_step(data, params)
            baseline_result = baseline_payload["result"]
            baseline_imputed = np.asarray(baseline_result.imputed_market_income, dtype=float)
            baseline_strategy = str(baseline_result.metadata.get("strategy", "baseline"))
            baseline_rmse = baseline_result.rmse_train
        else:
            baseline_strategy = "support_reference_fallback"
            baseline_rmse = None
            baseline_imputed = np.asarray(income, dtype=float).copy()
            baseline_imputed[missing_mask] = 0.5 * (support_lower + support_upper)

        completed_income = np.asarray(income, dtype=float).copy()
        if np.any(missing_mask):
            clipped = np.clip(baseline_imputed[missing_mask], support_lower, support_upper)
            completed_income[missing_mask] = clipped
            clipped_indicator = (baseline_imputed[missing_mask] < support_lower) | (
                baseline_imputed[missing_mask] > support_upper
            )
            clipped_share = (
                float(
                    np.sum(weights[missing_mask] * clipped_indicator)
                    / max(np.sum(weights[missing_mask]), 1e-12)
                )
                if np.any(missing_mask)
                else 0.0
            )
        else:
            clipped_share = 0.0

        total_weight = float(np.sum(weights))
        total_missing_weight = float(np.sum(weights[missing_mask]))
        weighted_response_rate = float(np.sum(weights[observed_mask]) / max(total_weight, 1e-12))
        missing_weight_share = 1.0 - weighted_response_rate
        if np.any(observed_mask):
            observed_mean = _weighted_mean(analysis_income[observed_mask], weights[observed_mask])
        else:
            midpoint = 0.5 * (target_support_lower_arr + target_support_upper_arr)
            observed_mean = _weighted_mean(midpoint, weights)
            warnings.append("no_observed_income_reference_mean_defaulted_to_support_midpoint")

        fixed_observed_total = (
            float(
                np.sum(weights[observed_mask] * analysis_income[observed_mask])
                / max(total_weight, 1e-12)
            )
            if np.any(observed_mask)
            else 0.0
        )
        manski_lower = fixed_observed_total + float(
            np.sum(weights[missing_mask] * target_support_lower_arr[missing_mask])
            / max(total_weight, 1e-12)
        )
        manski_upper = fixed_observed_total + float(
            np.sum(weights[missing_mask] * target_support_upper_arr[missing_mask])
            / max(total_weight, 1e-12)
        )
        support_reference = float(
            np.clip(observed_mean, target_support_summary[0], target_support_summary[1])
        )

        group_labels = _coerce_group_labels(
            params.get("group_labels", metadata.get("mnar_strata_labels")),
            n_obs=int(income.size),
        )
        missingness_types = _coerce_missingness_types(
            params.get("missingness_types", metadata.get("missingness_types")),
            missing_mask=missing_mask,
        )
        taxonomy_entries = _taxonomy_entries(
            mechanism_class=mechanism_class,
            lambda_interval=None,
            missingness_types=missingness_types,
            missing_mask=missing_mask,
            external_anchors=external_anchors,
        )
        target_payload = MNARIncomeBoundsTarget(
            scale=target_scale,
            back_transform_rule=_back_transform_rule(target_scale),
            equivalence_scale_source=(
                equivalence_scale_source
                if target_scale == "equivalized_income" and equivalence_scale_source is not None
                else ("implicit_unity" if target_scale == "equivalized_income" else None)
            ),
        )

        if not np.any(missing_mask):
            bounds_payload = MNARIncomeBoundsResult(
                target=target_payload,
                assumption_vector=MNARIncomeAssumptionVector(
                    mechanism_class=mechanism_class,
                    income_score=None if mechanism_class == "support_only" else score_name,
                    gamma_range=None,
                    delta_range=None,
                    lambda_range=None,
                    support_bounds=target_support_summary,
                    external_anchors=external_anchors,
                    taxonomy_entries=taxonomy_entries,
                    additional_restrictions=additional_restrictions,
                ),
                bounds=MNARIncomeBoundsInterval(
                    lower=fixed_observed_total,
                    upper=fixed_observed_total,
                    reference_value=fixed_observed_total,
                    grid_argmin=None,
                    grid_argmax=None,
                    manski_outer_bound={"lower": manski_lower, "upper": manski_upper},
                ),
                diagnostics=MNARIncomeBoundsDiagnostics(
                    response_rate=weighted_response_rate,
                    missing_share=missing_weight_share,
                    weight_dispersion=float(np.std(weights) / max(np.mean(weights), 1e-12)),
                    effective_sample_size=_effective_sample_size(weights),
                    share_clipped_to_support=0.0,
                    alpha_solver_converged=None,
                    selection_weight_effective_sample_size_min=None,
                    selection_curve_monotonicity=None,
                    tail_amplification=None,
                    mi_monte_carlo_error=None,
                    notes={
                        "baseline_strategy": baseline_strategy,
                        "support_bounds_source": support_source,
                        "raw_support_bounds": [support_lower, support_upper],
                        "target_support_bounds_summary": list(target_support_summary),
                        "target_scale": target_scale,
                        "equivalence_scale_source": (
                            equivalence_scale_source
                            if equivalence_scale_source is not None
                            else "implicit_unity"
                        ),
                    },
                ),
                provenance=MNARIncomeBoundsProvenance(
                    method="microsim.imputation.mnar_income_bounds@1.0.0",
                    timestamp_utc=datetime.now(UTC).isoformat(),
                ),
                warnings=tuple(warnings),
            )
            result = ImputationResult(
                imputed_market_income=completed_income,
                missing_share=0.0,
                rmse_train=baseline_rmse,
                metadata={
                    "strategy": baseline_strategy,
                    "mnar_bounds": bounds_payload.model_dump(mode="json"),
                },
            )
            envelope = _build_envelope(
                lower=fixed_observed_total,
                upper=fixed_observed_total,
                point_estimate=fixed_observed_total,
                mechanism_class=mechanism_class,
                target_scale=target_scale,
            )
            return {
                "result": result,
                "market_income": completed_income,
                "uncertainty_envelope": envelope,
            }

        gamma_interval = _coerce_interval(
            params.get("gamma_range"),
            default=_DEFAULT_GAMMA_RANGE,
            name="gamma_range",
        )
        gamma_grid = _coerce_grid(
            params.get("gamma_grid"),
            default_interval=gamma_interval,
            n_points=int(params.get("n_gamma_points", 21)),
            name="gamma",
        )
        gamma_overrides = params.get("gamma_overrides", {})
        reference_gamma = _resolve_reference_value(
            _ALL_MISSING,
            common_reference=params.get("reference_gamma"),
            overrides=params.get("reference_gamma_overrides", {}),
            default_value=0.0,
            interval=gamma_interval,
        )

        delta_interval = _coerce_interval(
            params.get("delta_range"),
            default=_DEFAULT_DELTA_RANGE,
            name="delta_range",
        )
        lambda_interval = _coerce_interval(
            params.get("lambda_range"),
            default=_DEFAULT_LAMBDA_RANGE,
            name="lambda_range",
        )
        delta_grid = _coerce_grid(
            params.get("delta_grid"),
            default_interval=delta_interval,
            n_points=int(params.get("n_delta_points", 11)),
            name="delta",
        )
        lambda_grid = _coerce_grid(
            params.get("lambda_grid"),
            default_interval=lambda_interval,
            n_points=int(params.get("n_lambda_points", 11)),
            name="lambda",
        )
        delta_overrides = params.get("delta_overrides", {})
        lambda_overrides = params.get("lambda_overrides", {})
        taxonomy_entries = _taxonomy_entries(
            mechanism_class=mechanism_class,
            lambda_interval=lambda_interval
            if mechanism_class == "pattern_mixture.locscale"
            else None,
            missingness_types=missingness_types,
            missing_mask=missing_mask,
            external_anchors=external_anchors,
        )

        uses_component_specific_parameters = False
        if (
            mechanism_class.startswith("selection")
            and isinstance(gamma_overrides, Mapping)
            and gamma_overrides
        ):
            uses_component_specific_parameters = True
        if mechanism_class == "pattern_mixture.locscale" and (
            (isinstance(delta_overrides, Mapping) and delta_overrides)
            or (isinstance(lambda_overrides, Mapping) and lambda_overrides)
        ):
            uses_component_specific_parameters = True

        shared_selection_curves: list[np.ndarray] = []
        shared_pattern_surfaces: list[np.ndarray] = []
        shared_reference_total = 0.0
        independent_lower_total = 0.0
        independent_upper_total = 0.0
        independent_reference_total = 0.0
        interval_lower_total = 0.0
        interval_upper_total = 0.0
        interval_reference_total = 0.0
        alpha_solver_converged = True if mechanism_class == "selection.probit" else None
        selection_effective_sample_size_min: float | None = None
        selection_curve_monotonicity: str | None = None
        tail_amplification: float | None = None
        pattern_reference_clip_share = 0.0
        pattern_max_clip_share = 0.0
        strata_payloads: list[dict[str, Any]] = []

        for group_label in sorted({str(item) for item in group_labels.tolist()}):
            stratum_mask = group_labels == group_label
            stratum_weights = weights[stratum_mask]
            stratum_total_weight = float(np.sum(stratum_weights))
            if stratum_total_weight <= 0.0:
                continue
            stratum_observed_mask = observed_mask & stratum_mask
            stratum_missing_mask = missing_mask & stratum_mask
            stratum_response_rate = float(
                np.sum(weights[stratum_observed_mask]) / max(stratum_total_weight, 1e-12)
            )
            stratum_payload: dict[str, Any] = {
                "label": group_label,
                "weight_share": stratum_total_weight / max(total_weight, 1e-12),
                "response_rate": stratum_response_rate,
                "respondent_mean": None,
                "respondent_std": None,
                "missing_components": [],
            }

            if np.any(stratum_observed_mask):
                stratum_observed_income = income[stratum_observed_mask]
                stratum_observed_target = analysis_income[stratum_observed_mask]
                stratum_observed_weights = weights[stratum_observed_mask]
                stratum_observed_equivalence = equivalence_scale[stratum_observed_mask]
                respondent_mean = _weighted_mean(stratum_observed_target, stratum_observed_weights)
                respondent_std = _weighted_std(stratum_observed_target, stratum_observed_weights)
                stratum_payload["respondent_mean"] = respondent_mean
                stratum_payload["respondent_std"] = respondent_std
            else:
                stratum_observed_income = np.asarray([], dtype=float)
                stratum_observed_target = np.asarray([], dtype=float)
                stratum_observed_weights = np.asarray([], dtype=float)
                stratum_observed_equivalence = np.asarray([], dtype=float)
                respondent_mean = None
                respondent_std = None

            component_labels = sorted(
                {
                    str(item)
                    for item in missingness_types[stratum_missing_mask].tolist()
                    if str(item)
                }
            )
            if not component_labels and np.any(stratum_missing_mask):
                component_labels = [_ALL_MISSING]

            for component_label in component_labels:
                component_mask = stratum_missing_mask & (missingness_types == component_label)
                component_weight = float(np.sum(weights[component_mask]))
                if component_weight <= 0.0:
                    continue
                component_share = component_weight / max(total_weight, 1e-12)
                component_missing_share = component_weight / max(total_missing_weight, 1e-12)
                component_support_lower = target_support_lower_arr[component_mask]
                component_support_upper = target_support_upper_arr[component_mask]
                component_support_midpoint = 0.5 * (
                    component_support_lower + component_support_upper
                )
                component_support_lower_mean = _weighted_mean(
                    component_support_lower, weights[component_mask]
                )
                component_support_upper_mean = _weighted_mean(
                    component_support_upper, weights[component_mask]
                )
                component_entry: dict[str, Any] = {
                    "label": component_label,
                    "weight_share": component_share,
                    "support_bounds": [component_support_lower_mean, component_support_upper_mean],
                }

                if mechanism_class == "support_only" or not np.any(stratum_observed_mask):
                    lower_mu0 = component_support_lower_mean
                    upper_mu0 = component_support_upper_mean
                    reference_seed = (
                        respondent_mean
                        if respondent_mean is not None
                        else _weighted_mean(component_support_midpoint, weights[component_mask])
                    )
                    reference_mu0 = float(np.clip(reference_seed, lower_mu0, upper_mu0))
                    interval_lower_total += component_share * lower_mu0
                    interval_upper_total += component_share * upper_mu0
                    interval_reference_total += component_share * reference_mu0
                    component_entry.update(
                        {
                            "fallback": None
                            if mechanism_class == "support_only"
                            else "support_only_no_respondents",
                            "lower_nonrespondent_mean": lower_mu0,
                            "upper_nonrespondent_mean": upper_mu0,
                            "reference_nonrespondent_mean": reference_mu0,
                        }
                    )
                    stratum_payload["missing_components"].append(component_entry)
                    continue

                if mechanism_class.startswith("selection"):
                    component_gamma_grid = _resolve_component_grid(
                        component_label,
                        common_grid=gamma_grid,
                        overrides=gamma_overrides,
                        default_interval=gamma_interval,
                        n_points=int(params.get("n_gamma_points", 21)),
                        name="gamma",
                    )
                    component_gamma_range = (
                        float(np.min(component_gamma_grid)),
                        float(np.max(component_gamma_grid)),
                    )
                    component_reference_gamma = _resolve_reference_value(
                        component_label,
                        common_reference=params.get("reference_gamma"),
                        overrides=params.get("reference_gamma_overrides", {}),
                        default_value=0.0,
                        interval=component_gamma_range,
                    )
                    score_values = _score_values(
                        stratum_observed_income,
                        stratum_observed_target,
                        stratum_observed_weights,
                        score_name,
                        equivalence_scale=stratum_observed_equivalence,
                    )
                    if mechanism_class == "selection.logit":
                        curve, ess_curve = _selection_logit_curve(
                            stratum_observed_target,
                            stratum_observed_weights,
                            score_values,
                            component_gamma_grid,
                        )
                        reference_curve, reference_ess = _selection_logit_curve(
                            stratum_observed_target,
                            stratum_observed_weights,
                            score_values,
                            np.asarray([component_reference_gamma], dtype=float),
                        )
                        alpha_values: list[float] | None = None
                    else:
                        curve, solved_alpha, solved, ess_curve = _selection_probit_curve(
                            stratum_observed_target,
                            stratum_observed_weights,
                            score_values,
                            component_gamma_grid,
                            stratum_response_rate,
                        )
                        alpha_solver_converged = bool(alpha_solver_converged) and solved
                        reference_curve, reference_alpha, solved_reference, reference_ess = (
                            _selection_probit_curve(
                                stratum_observed_target,
                                stratum_observed_weights,
                                score_values,
                                np.asarray([component_reference_gamma], dtype=float),
                                stratum_response_rate,
                            )
                        )
                        alpha_solver_converged = bool(alpha_solver_converged) and solved_reference
                        alpha_values = [float(item) for item in solved_alpha]
                        component_entry["reference_alpha"] = float(reference_alpha[0])

                    lower_mu0 = float(np.min(curve))
                    upper_mu0 = float(np.max(curve))
                    reference_mu0 = float(reference_curve[0])
                    selection_effective_sample_size_min = (
                        float(np.min(np.concatenate([ess_curve, reference_ess])))
                        if selection_effective_sample_size_min is None
                        else float(
                            min(
                                selection_effective_sample_size_min,
                                np.min(np.concatenate([ess_curve, reference_ess])),
                            )
                        )
                    )
                    if uses_component_specific_parameters:
                        independent_lower_total += component_share * lower_mu0
                        independent_upper_total += component_share * upper_mu0
                        independent_reference_total += component_share * reference_mu0
                    else:
                        shared_selection_curves.append(component_share * curve)
                        shared_reference_total += component_share * reference_mu0
                    component_entry.update(
                        {
                            "gamma_range": [component_gamma_range[0], component_gamma_range[1]],
                            "lower_nonrespondent_mean": lower_mu0,
                            "upper_nonrespondent_mean": upper_mu0,
                            "reference_nonrespondent_mean": reference_mu0,
                            "effective_sample_size_min": float(np.min(ess_curve)),
                            "reference_effective_sample_size": float(reference_ess[0]),
                            "curve": [
                                {
                                    "gamma": float(gamma_value),
                                    "nonrespondent_mean": float(curve_value),
                                }
                                for gamma_value, curve_value in zip(
                                    component_gamma_grid.tolist(), curve.tolist()
                                )
                            ],
                        }
                    )
                    if alpha_values is not None:
                        component_entry["alpha_curve"] = alpha_values
                    stratum_payload["missing_components"].append(component_entry)
                    continue

                component_delta_grid = _resolve_component_grid(
                    component_label,
                    common_grid=delta_grid,
                    overrides=delta_overrides,
                    default_interval=delta_interval,
                    n_points=int(params.get("n_delta_points", 11)),
                    name="delta",
                )
                component_lambda_grid = _resolve_component_grid(
                    component_label,
                    common_grid=lambda_grid,
                    overrides=lambda_overrides,
                    default_interval=lambda_interval,
                    n_points=int(params.get("n_lambda_points", 11)),
                    name="lambda",
                )
                component_delta_range = (
                    float(np.min(component_delta_grid)),
                    float(np.max(component_delta_grid)),
                )
                component_lambda_range = (
                    float(np.min(component_lambda_grid)),
                    float(np.max(component_lambda_grid)),
                )
                component_reference_delta = _resolve_reference_value(
                    component_label,
                    common_reference=params.get("reference_delta"),
                    overrides=params.get("reference_delta_overrides", {}),
                    default_value=0.0,
                    interval=component_delta_range,
                )
                component_reference_lambda = _resolve_reference_value(
                    component_label,
                    common_reference=params.get("reference_lambda"),
                    overrides=params.get("reference_lambda_overrides", {}),
                    default_value=1.0,
                    interval=component_lambda_range,
                )
                surface, clip_surface = _pattern_mixture_surface(
                    stratum_observed_target,
                    stratum_observed_weights,
                    component_delta_grid,
                    component_lambda_grid,
                    missing_support_lower=component_support_lower,
                    missing_support_upper=component_support_upper,
                    missing_weights=weights[component_mask],
                )
                reference_surface, reference_clip_surface = _pattern_mixture_surface(
                    stratum_observed_target,
                    stratum_observed_weights,
                    np.asarray([component_reference_delta], dtype=float),
                    np.asarray([component_reference_lambda], dtype=float),
                    missing_support_lower=component_support_lower,
                    missing_support_upper=component_support_upper,
                    missing_weights=weights[component_mask],
                )
                reference_mu0 = float(reference_surface[0, 0])
                lower_mu0 = float(np.min(surface))
                upper_mu0 = float(np.max(surface))
                reference_clip_share_component = float(reference_clip_surface[0, 0])
                max_clip_share_component = float(np.max(clip_surface))
                pattern_reference_clip_share += (
                    component_missing_share * reference_clip_share_component
                )
                pattern_max_clip_share = max(pattern_max_clip_share, max_clip_share_component)
                tail_candidate = float(
                    max(component_lambda_range[1], 1.0 / max(component_lambda_range[0], 1e-12))
                )
                tail_amplification = (
                    tail_candidate
                    if tail_amplification is None
                    else max(tail_amplification, tail_candidate)
                )
                if uses_component_specific_parameters:
                    independent_lower_total += component_share * lower_mu0
                    independent_upper_total += component_share * upper_mu0
                    independent_reference_total += component_share * reference_mu0
                else:
                    shared_pattern_surfaces.append(component_share * surface)
                    shared_reference_total += component_share * reference_mu0
                component_entry.update(
                    {
                        "delta_range": [component_delta_range[0], component_delta_range[1]],
                        "lambda_range": [component_lambda_range[0], component_lambda_range[1]],
                        "lower_nonrespondent_mean": lower_mu0,
                        "upper_nonrespondent_mean": upper_mu0,
                        "reference_nonrespondent_mean": reference_mu0,
                        "share_clipped_to_support_reference": reference_clip_share_component,
                        "share_clipped_to_support_max": max_clip_share_component,
                        "surface": [
                            {
                                "delta": float(delta_value),
                                "lambda": float(lambda_value),
                                "nonrespondent_mean": float(surface[row_idx, col_idx]),
                            }
                            for row_idx, delta_value in enumerate(component_delta_grid.tolist())
                            for col_idx, lambda_value in enumerate(component_lambda_grid.tolist())
                        ],
                    }
                )
                stratum_payload["missing_components"].append(component_entry)

            strata_payloads.append(stratum_payload)

        scenario_grid: list[dict[str, Any]] = []
        grid_argmin: dict[str, Any] | None = None
        grid_argmax: dict[str, Any] | None = None

        if mechanism_class == "support_only":
            lower_bound = manski_lower
            upper_bound = manski_upper
            reference_value = fixed_observed_total + missing_weight_share * support_reference
        elif uses_component_specific_parameters:
            lower_bound = fixed_observed_total + independent_lower_total + interval_lower_total
            upper_bound = fixed_observed_total + independent_upper_total + interval_upper_total
            reference_value = (
                fixed_observed_total + independent_reference_total + interval_reference_total
            )
            warnings.append(
                "component_specific_parameter_overrides_disable_single_collapsed_scenario_grid"
            )
        elif mechanism_class.startswith("selection"):
            if shared_selection_curves:
                total_curve = fixed_observed_total + np.sum(
                    np.vstack(shared_selection_curves), axis=0
                )
                lower_index = int(np.argmin(total_curve))
                upper_index = int(np.argmax(total_curve))
                selection_curve_monotonicity = _curve_monotonicity(total_curve)
                lower_bound = float(total_curve[lower_index] + interval_lower_total)
                upper_bound = float(total_curve[upper_index] + interval_upper_total)
                reference_value = float(
                    fixed_observed_total + shared_reference_total + interval_reference_total
                )
                grid_argmin = {"gamma": float(gamma_grid[lower_index])}
                grid_argmax = {"gamma": float(gamma_grid[upper_index])}
                scenario_grid = [
                    {
                        "gamma": float(gamma_value),
                        "estimate": float(curve_value + interval_reference_total),
                    }
                    for gamma_value, curve_value in zip(gamma_grid.tolist(), total_curve.tolist())
                ]
                if mechanism_class == "selection.probit":
                    grid_argmin["alpha_solver_converged"] = bool(alpha_solver_converged)
                    grid_argmax["alpha_solver_converged"] = bool(alpha_solver_converged)
            else:
                lower_bound = fixed_observed_total + interval_lower_total
                upper_bound = fixed_observed_total + interval_upper_total
                reference_value = fixed_observed_total + interval_reference_total
        else:
            if shared_pattern_surfaces:
                total_surface = fixed_observed_total + np.sum(
                    np.stack(shared_pattern_surfaces), axis=0
                )
                flat_argmin = int(np.argmin(total_surface))
                flat_argmax = int(np.argmax(total_surface))
                lower_coords = np.unravel_index(flat_argmin, total_surface.shape)
                upper_coords = np.unravel_index(flat_argmax, total_surface.shape)
                lower_bound = float(total_surface[lower_coords] + interval_lower_total)
                upper_bound = float(total_surface[upper_coords] + interval_upper_total)
                reference_value = float(
                    fixed_observed_total + shared_reference_total + interval_reference_total
                )
                grid_argmin = {
                    "delta": float(delta_grid[lower_coords[0]]),
                    "lambda": float(lambda_grid[lower_coords[1]]),
                }
                grid_argmax = {
                    "delta": float(delta_grid[upper_coords[0]]),
                    "lambda": float(lambda_grid[upper_coords[1]]),
                }
                scenario_grid = [
                    {
                        "delta": float(delta_grid[row_idx]),
                        "lambda": float(lambda_grid[col_idx]),
                        "estimate": float(
                            total_surface[row_idx, col_idx] + interval_reference_total
                        ),
                    }
                    for row_idx in range(total_surface.shape[0])
                    for col_idx in range(total_surface.shape[1])
                ]
            else:
                lower_bound = fixed_observed_total + interval_lower_total
                upper_bound = fixed_observed_total + interval_upper_total
                reference_value = fixed_observed_total + interval_reference_total

        bounds_payload = MNARIncomeBoundsResult(
            target=target_payload,
            assumption_vector=MNARIncomeAssumptionVector(
                external_anchors=external_anchors,
                mechanism_class=mechanism_class,
                income_score=None
                if mechanism_class in {"support_only", "pattern_mixture.locscale"}
                else score_name,
                gamma_range=None
                if mechanism_class not in {"selection.logit", "selection.probit"}
                else gamma_interval,
                delta_range=None
                if mechanism_class != "pattern_mixture.locscale"
                else delta_interval,
                lambda_range=None
                if mechanism_class != "pattern_mixture.locscale"
                else lambda_interval,
                support_bounds=target_support_summary,
                strata=tuple(
                    item["label"] for item in strata_payloads if item["label"] != _ALL_GROUP
                ),
                missingness_types=tuple(
                    sorted(
                        {
                            str(label)
                            for label in missingness_types[missing_mask].tolist()
                            if str(label) and str(label) != _ALL_MISSING
                        }
                    )
                ),
                taxonomy_entries=taxonomy_entries,
                additional_restrictions=additional_restrictions,
            ),
            bounds=MNARIncomeBoundsInterval(
                lower=lower_bound,
                upper=upper_bound,
                reference_value=reference_value,
                grid_argmin=grid_argmin,
                grid_argmax=grid_argmax,
                manski_outer_bound={"lower": manski_lower, "upper": manski_upper},
            ),
            diagnostics=MNARIncomeBoundsDiagnostics(
                response_rate=weighted_response_rate,
                missing_share=missing_weight_share,
                weight_dispersion=float(np.std(weights) / max(np.mean(weights), 1e-12)),
                effective_sample_size=_effective_sample_size(weights),
                share_clipped_to_support=(
                    pattern_reference_clip_share
                    if mechanism_class == "pattern_mixture.locscale"
                    else clipped_share
                ),
                alpha_solver_converged=alpha_solver_converged,
                selection_weight_effective_sample_size_min=selection_effective_sample_size_min,
                selection_curve_monotonicity=selection_curve_monotonicity,
                tail_amplification=tail_amplification,
                mi_monte_carlo_error=None,
                notes={
                    "baseline_strategy": baseline_strategy,
                    "support_bounds_source": support_source,
                    "raw_support_bounds": [support_lower, support_upper],
                    "target_support_bounds_summary": list(target_support_summary),
                    "target_scale": target_scale,
                    "equivalence_scale_source": (
                        equivalence_scale_source
                        if equivalence_scale_source is not None
                        else "implicit_unity"
                    ),
                    "unit_specific_support": bool(target_scale == "equivalized_income"),
                    "component_specific_parameters": uses_component_specific_parameters,
                    "reference_point_imputation": "mar_baseline_clipped_to_support",
                    "pattern_reference_share_clipped_to_support": (
                        pattern_reference_clip_share
                        if mechanism_class == "pattern_mixture.locscale"
                        else None
                    ),
                    "pattern_max_share_clipped_to_support": (
                        pattern_max_clip_share
                        if mechanism_class == "pattern_mixture.locscale"
                        else None
                    ),
                },
            ),
            provenance=MNARIncomeBoundsProvenance(
                method="microsim.imputation.mnar_income_bounds@1.0.0",
                timestamp_utc=datetime.now(UTC).isoformat(),
            ),
            scenario_grid=tuple(scenario_grid),
            strata=tuple(strata_payloads),
            warnings=tuple(warnings),
        )

        result = ImputationResult(
            imputed_market_income=completed_income,
            missing_share=float(np.mean(missing_mask)),
            rmse_train=baseline_rmse,
            metadata={
                "strategy": baseline_strategy,
                "mnar_bounds": bounds_payload.model_dump(mode="json"),
            },
        )
        envelope = _build_envelope(
            lower=lower_bound,
            upper=upper_bound,
            point_estimate=reference_value,
            mechanism_class=mechanism_class,
            target_scale=target_scale,
        )
        return {
            "result": result,
            "market_income": completed_income,
            "uncertainty_envelope": envelope,
        }


__all__ = ["MNARIncomeBoundsEstimator"]
