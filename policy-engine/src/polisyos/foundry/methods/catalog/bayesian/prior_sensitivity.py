"""Prior robustness, prior-predictive checks, and interval-sensitivity gates."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriorSensitivityStatus(StrEnum):
    """Lifecycle state for the prior-sensitivity gate."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_RUN = "not_run"


class ReadinessTier(StrEnum):
    """Governance tier requested or achieved by a Bayesian prior gate."""

    TIER_0 = "tier_0"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"
    NONE = "none"


class BayesianPolicyModelFamily(StrEnum):
    """Model families covered by the Phase-5 prior-sensitivity contract."""

    LINEAR = "linear"
    LOGISTIC = "logistic"
    BART = "bart"
    GP = "gp"
    VAR = "var"
    UNKNOWN = "unknown"


class DataConditioningMode(StrEnum):
    """How any outcome-conditioned prior hyperparameters were calibrated."""

    NONE = "none"
    SPLIT = "split"
    FULL_PROCEDURE_CALIBRATED = "full_procedure_calibrated"
    INVALID = "invalid"


def _enum_payload(value: Any) -> str:
    return str(value.value) if isinstance(value, StrEnum) else str(value)


def _coerce_model_family(value: BayesianPolicyModelFamily | str) -> BayesianPolicyModelFamily:
    return value if isinstance(value, BayesianPolicyModelFamily) else BayesianPolicyModelFamily(str(value))


def _coerce_readiness_tier(value: ReadinessTier | str) -> ReadinessTier:
    return value if isinstance(value, ReadinessTier) else ReadinessTier(str(value))


def _coerce_conditioning_mode(value: DataConditioningMode | str) -> DataConditioningMode:
    return (
        value
        if isinstance(value, DataConditioningMode)
        else DataConditioningMode(str(value))
    )


class PriorConstraintRecord(BaseModel):
    """One auditable constraint in an admissible prior class."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    threshold: float | str | None = None
    estimated_probability: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class HyperparameterSpaceRecord(BaseModel):
    """Declared transform and support for one prior hyperparameter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transform: str = "identity"
    lower: float | None = None
    upper: float | None = None
    baseline: float | None = None


class AdmissiblePriorClassRecord(BaseModel):
    """Catalog record for a model-family-specific admissible prior class."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    class_id: str
    constraints: tuple[PriorConstraintRecord, ...] = ()
    hyperparameter_space: dict[str, HyperparameterSpaceRecord] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return all(constraint.passed for constraint in self.constraints)


class PriorPredictiveDiagnosticRecord(BaseModel):
    """Rank and observed value for one prior-predictive diagnostic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    observed: float
    prior_predictive_rank: float
    simulated_mean: float | None = None
    simulated_sd: float | None = None


class PriorPredictiveCheckRecord(BaseModel):
    """Exchangeability-ranked prior-predictive compatibility check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: PriorSensitivityStatus = PriorSensitivityStatus.NOT_RUN
    alpha: float = 0.05
    p_value: float | None = None
    monte_carlo_se: float | None = None
    n_simulations: int = 0
    calibration: str = "exchangeability_rank"
    conditioned_on: tuple[str, ...] = ()
    diagnostics: tuple[PriorPredictiveDiagnosticRecord, ...] = ()
    rejected_diagnostics: tuple[str, ...] = ()
    observed_nonconformity: float | None = None


class PriorClassCalibrationRecord(BaseModel):
    """Class-adjusted calibration for a searched prior-hyperparameter neighborhood."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: PriorSensitivityStatus = PriorSensitivityStatus.NOT_RUN
    method: str = "not_run"
    alpha: float = 0.05
    p_min: float | None = None
    calibrated_cutoff: float | None = None
    n_candidates: int = 0
    n_outer_simulations: int = 0
    candidate_prior_ids: tuple[str, ...] = ()
    candidate_p_values: dict[str, float] = Field(default_factory=dict)
    class_adjusted_pass: bool = False
    notes: tuple[str, ...] = ()


class SensitivityCurvePoint(BaseModel):
    """One posterior-interval perturbation point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hyperparameter: str
    multiplier: float | None = None
    interval: tuple[float, float]
    half_width: float
    effective_sample_size: float | None = None
    refit_required: bool = False


class PosteriorSensitivityRecord(BaseModel):
    """Credible-interval width curve for one policy estimand."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    estimand_id: str
    credible_interval_level: float
    baseline_interval: tuple[float, float]
    baseline_half_width: float
    perturbation_radius: str = "log(2)"
    hyperparameter_metric: str = "max_abs_log_scale_shift"
    width_factor: float
    expansion: float
    contraction: float
    max_center_shift_in_half_widths: float
    decision_stability: float
    pass_: bool = Field(alias="pass")
    curve: tuple[SensitivityCurvePoint, ...] = ()
    elasticities: dict[str, float] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class PriorSensitivityReport(BaseModel):
    """Top-level ``PosteriorResult.prior_sensitivity`` contract."""

    contract_id: ClassVar[str] = "foundry.bayesian.prior_sensitivity.v1"
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    version: str = "1.0"
    status: PriorSensitivityStatus = PriorSensitivityStatus.NOT_RUN
    readiness_tier_requested: ReadinessTier = ReadinessTier.TIER_0
    readiness_tier_achieved: ReadinessTier = ReadinessTier.NONE
    model_family: BayesianPolicyModelFamily = BayesianPolicyModelFamily.UNKNOWN
    selected_prior_id: str = "not_declared"
    admissible_prior_class_id: str = "not_declared"
    uses_outcome_to_set_prior: bool = False
    data_conditioning_mode: DataConditioningMode = DataConditioningMode.NONE
    admissible_prior_class: AdmissiblePriorClassRecord | None = None
    prior_predictive_check: PriorPredictiveCheckRecord | None = None
    prior_class_calibration: PriorClassCalibrationRecord | None = None
    sensitivity: PosteriorSensitivityRecord | None = None
    sensitivity_by_estimand: tuple[PosteriorSensitivityRecord, ...] = ()
    failure_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _enforce_outcome_conditioning_failure(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        uses_outcome = bool(payload.get("uses_outcome_to_set_prior", False))
        mode = _enum_payload(payload.get("data_conditioning_mode", DataConditioningMode.NONE)).lower()
        if uses_outcome and mode not in {
            DataConditioningMode.SPLIT.value,
            DataConditioningMode.FULL_PROCEDURE_CALIBRATED.value,
        }:
            reasons = list(payload.get("failure_reasons") or ())
            reasons.append("outcome_used_to_set_prior_without_split_or_full_procedure_calibration")
            payload["failure_reasons"] = tuple(dict.fromkeys(reasons))
            payload["status"] = PriorSensitivityStatus.FAIL.value
            payload["data_conditioning_mode"] = DataConditioningMode.INVALID.value
            payload.setdefault("readiness_tier_achieved", ReadinessTier.NONE.value)
        return payload


_TIER_ORDER = {
    ReadinessTier.NONE: -1,
    ReadinessTier.TIER_0: 0,
    ReadinessTier.TIER_1: 1,
    ReadinessTier.TIER_2: 2,
    ReadinessTier.TIER_3: 3,
    ReadinessTier.TIER_4: 4,
}


_READINESS_THRESHOLDS: dict[ReadinessTier, dict[str, float | bool | None]] = {
    ReadinessTier.TIER_0: {
        "p_value_min": None,
        "width_factor_max": None,
        "center_shift_max": None,
        "decision_stability_min": None,
        "class_adjusted_required": False,
    },
    ReadinessTier.TIER_1: {
        "p_value_min": 0.01,
        "width_factor_max": 2.00,
        "center_shift_max": 1.00,
        "decision_stability_min": None,
        "class_adjusted_required": False,
    },
    ReadinessTier.TIER_2: {
        "p_value_min": 0.025,
        "width_factor_max": 1.50,
        "center_shift_max": 0.50,
        "decision_stability_min": 0.90,
        "class_adjusted_required": True,
    },
    ReadinessTier.TIER_3: {
        "p_value_min": 0.05,
        "width_factor_max": 1.25,
        "center_shift_max": 0.25,
        "decision_stability_min": 0.95,
        "class_adjusted_required": True,
    },
    ReadinessTier.TIER_4: {
        "p_value_min": 0.10,
        "width_factor_max": 1.15,
        "center_shift_max": 0.10,
        "decision_stability_min": 0.99,
        "class_adjusted_required": True,
    },
}


def infer_bayesian_policy_model_family(method_name: str | None) -> BayesianPolicyModelFamily:
    """Infer the Phase-5 model family from a Bayesian method name."""

    name = str(method_name or "").strip().lower()
    if "bart" in name:
        return BayesianPolicyModelFamily.BART
    if "gp" in name or "gaussian_process" in name:
        return BayesianPolicyModelFamily.GP
    if "autoregression" in name or "var" in name or "timeseries" in name:
        return BayesianPolicyModelFamily.VAR
    if "logistic" in name:
        return BayesianPolicyModelFamily.LOGISTIC
    if "regression" in name or "hmc" in name or "nuts" in name:
        return BayesianPolicyModelFamily.LINEAR
    return BayesianPolicyModelFamily.UNKNOWN


def not_run_prior_sensitivity_report(
    *,
    model_family: BayesianPolicyModelFamily | str = BayesianPolicyModelFamily.UNKNOWN,
    selected_prior_id: str = "not_declared",
    admissible_prior_class_id: str = "not_declared",
    reason: str = "prior_sensitivity_gate_not_run",
) -> PriorSensitivityReport:
    """Build a stable default report for posterior methods without a prior gate yet."""

    return PriorSensitivityReport(
        status=PriorSensitivityStatus.NOT_RUN,
        readiness_tier_requested=ReadinessTier.TIER_0,
        readiness_tier_achieved=ReadinessTier.NONE,
        model_family=_coerce_model_family(model_family),
        selected_prior_id=selected_prior_id,
        admissible_prior_class_id=admissible_prior_class_id,
        warnings=(reason,),
    )


def _constraint(
    name: str,
    passed: bool,
    *,
    threshold: float | str | None = None,
    estimated_probability: float | None = None,
    details: Mapping[str, Any] | None = None,
) -> PriorConstraintRecord:
    return PriorConstraintRecord(
        name=name,
        passed=bool(passed),
        threshold=threshold,
        estimated_probability=estimated_probability,
        details=dict(details or {}),
    )


def _finite_positive(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) and result > 0.0 else default


def _as_2d_features(features: Any | None, n_obs: int | None = None) -> np.ndarray | None:
    if features is None:
        return None
    arr = np.asarray(features, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2 or arr.shape[0] == 0:
        return None
    if n_obs is not None and arr.shape[0] != n_obs:
        return None
    return arr


def _plausible_bounds_probability(
    simulations: np.ndarray | None,
    bounds: tuple[float, float] | None,
) -> float | None:
    if simulations is None or bounds is None:
        return None
    lower, upper = map(float, bounds)
    if not (np.isfinite(lower) and np.isfinite(upper) and lower < upper):
        return None
    arr = np.asarray(simulations, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return float(np.mean(np.all((arr >= lower) & (arr <= upper), axis=1)))


def _minimum_positive_spacing(values: np.ndarray) -> float | None:
    unique = np.unique(np.sort(np.asarray(values, dtype=float).reshape(-1)))
    if unique.size < 2:
        return None
    diffs = np.diff(unique)
    positive = diffs[diffs > 1e-12]
    if positive.size == 0:
        return None
    return float(np.min(positive))


def _as_probability_matrix(value: Any | None) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2 or arr.size == 0:
        return None
    return np.clip(arr, 0.0, 1.0)


def _as_simulation_matrix(value: Any | None) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2 or arr.size == 0:
        return None
    return arr


def build_admissible_prior_class(
    model_family: BayesianPolicyModelFamily | str,
    *,
    hyperparameters: Mapping[str, Any] | None = None,
    policy_context: Mapping[str, Any] | None = None,
    prior_predictive_simulations: np.ndarray | None = None,
) -> AdmissiblePriorClassRecord:
    """Build an auditable admissible-prior-library record for a model family."""

    family = _coerce_model_family(model_family)
    hp = dict(hyperparameters or {})
    ctx = dict(policy_context or {})
    conditioning_mode = _coerce_conditioning_mode(
        hp.get("data_conditioning_mode", ctx.get("data_conditioning_mode", DataConditioningMode.NONE))
    )
    uses_outcome = bool(hp.get("uses_outcome_to_set_prior", ctx.get("uses_outcome_to_set_prior", False)))
    leakage_ok = (not uses_outcome) or conditioning_mode in {
        DataConditioningMode.SPLIT,
        DataConditioningMode.FULL_PROCEDURE_CALIBRATED,
    }
    constraints: list[PriorConstraintRecord] = [
        _constraint("proper_prior", not bool(hp.get("improper_prior", False))),
        _constraint(
            "finite_prior_predictive_simulator",
            bool(hp.get("finite_prior_predictive_simulator", True)),
        ),
        _constraint("support_compatible", not bool(hp.get("support_incompatible", False))),
        _constraint("scale_equivariant_under_catalog_standardization", True),
        _constraint(
            "no_prohibited_outcome_leakage_in_hyperparameters",
            leakage_ok,
            details={
                "uses_outcome_to_set_prior": uses_outcome,
                "data_conditioning_mode": conditioning_mode.value,
            },
        ),
        _constraint(
            "posterior_and_prior_predictive_computation_auditable",
            bool(hp.get("auditable", ctx.get("auditable", True))),
        ),
    ]
    bounds = ctx.get("y_plausible_bounds")
    bounds_tuple = tuple(bounds) if isinstance(bounds, (list, tuple)) and len(bounds) == 2 else None
    bounds_probability = _plausible_bounds_probability(prior_predictive_simulations, bounds_tuple)
    if bounds_probability is not None:
        threshold = _finite_positive(ctx.get("predictive_envelope_threshold", 0.95), 0.95)
        constraints.append(
            _constraint(
                "predictive_outcome_envelope",
                bounds_probability >= threshold,
                threshold=threshold,
                estimated_probability=bounds_probability,
            )
        )

    hyperparameter_space: dict[str, HyperparameterSpaceRecord]
    notes: list[str] = []
    if family is BayesianPolicyModelFamily.LINEAR:
        nu_beta = float(hp.get("nu_beta", 10.0))
        sigma_scale = _finite_positive(hp.get("sigma_scale", hp.get("prior_scale", 1.0)), 1.0)
        prior_scale = _finite_positive(hp.get("prior_scale", 1.0), 1.0)
        constraints.extend(
            (
                _constraint("strict_finite_variance_beta_tail", 3.0 <= nu_beta <= 30.0),
                _constraint("positive_sigma_prior_scale", sigma_scale > 0.0),
            )
        )
        sigma_min = ctx.get("sigma_min")
        sigma_max = ctx.get("sigma_max")
        if sigma_min is not None and sigma_max is not None:
            sigma_samples = _as_simulation_matrix(hp.get("sigma_prior_samples"))
            if sigma_samples is not None:
                sigma_values = sigma_samples.reshape(-1)
                sigma_probability = float(
                    np.mean((sigma_values >= float(sigma_min)) & (sigma_values <= float(sigma_max)))
                )
            else:
                sigma_probability = 1.0 if float(sigma_min) <= sigma_scale <= float(sigma_max) else 0.0
            constraints.append(
                _constraint(
                    "sigma_prior_envelope",
                    sigma_probability >= 1.0 - float(ctx.get("q_sigma", 0.05)),
                    threshold=f"P({sigma_min} <= sigma <= {sigma_max}) >= {1.0 - float(ctx.get('q_sigma', 0.05))}",
                    estimated_probability=sigma_probability,
                )
            )
        psi_bound = ctx.get("policy_contrast_bound")
        psi_scale = hp.get("policy_contrast_scale")
        if psi_bound is not None and psi_scale is not None:
            probability = 1.0 if abs(float(psi_scale)) <= float(psi_bound) else 0.0
            constraints.append(
                _constraint(
                    "policy_contrast_prior_envelope",
                    probability >= 1.0 - float(ctx.get("q_psi", 0.05)),
                    threshold=f"P(|psi| <= {psi_bound}) >= {1.0 - float(ctx.get('q_psi', 0.05))}",
                    estimated_probability=probability,
                )
            )
        hyperparameter_space = {
            "prior_scale": HyperparameterSpaceRecord(
                transform="log", lower=1e-3, upper=1e3, baseline=prior_scale
            ),
            "sigma_scale": HyperparameterSpaceRecord(
                transform="log", lower=1e-3, upper=1e3, baseline=sigma_scale
            ),
            "nu_beta": HyperparameterSpaceRecord(
                transform="identity", lower=3.0, upper=30.0, baseline=nu_beta
            ),
        }
        class_id = "linear_gaussian_policy_v1"
    elif family is BayesianPolicyModelFamily.LOGISTIC:
        p0 = hp.get("baseline_probability")
        baseline_ok = p0 is not None and 0.0 < float(p0) < 1.0
        coef_scale = _finite_positive(hp.get("coefficient_scale", hp.get("prior_scale", 2.5)), 2.5)
        nu_beta = float(hp.get("nu_beta", 7.0))
        constraints.extend(
            (
                _constraint("baseline_aware_intercept", baseline_ok),
                _constraint("positive_coefficient_scale", coef_scale > 0.0),
                _constraint("weakly_informative_tail_recorded", nu_beta > 0.0),
            )
        )
        probabilities = _as_probability_matrix(
            hp.get("prior_probability_draws", ctx.get("prior_probability_draws"))
        )
        if probabilities is not None:
            eps = float(ctx.get("deterministic_probability_epsilon", 0.01))
            r_det = float(ctx.get("deterministic_probability_fraction_max", 0.1))
            q_p = float(ctx.get("q_p", 0.05))
            deterministic_fraction = np.mean(
                (probabilities < eps) | (probabilities > 1.0 - eps),
                axis=1,
            )
            probability_ok = float(np.mean(deterministic_fraction <= r_det))
            constraints.append(
                _constraint(
                    "deterministic_probability_fraction",
                    probability_ok >= 1.0 - q_p,
                    threshold=f"P(mean(I[p < eps or p > 1-eps]) <= {r_det}) >= {1.0 - q_p}",
                    estimated_probability=probability_ok,
                )
            )
            p_min = float(ctx.get("p_min", 0.0))
            p_max = float(ctx.get("p_max", 1.0))
            q_bar_p = float(ctx.get("q_bar_p", 0.05))
            mean_probabilities = np.mean(probabilities, axis=1)
            mean_probability_ok = float(
                np.mean((mean_probabilities >= p_min) & (mean_probabilities <= p_max))
            )
            constraints.append(
                _constraint(
                    "baseline_prevalence_envelope",
                    mean_probability_ok >= 1.0 - q_bar_p,
                    threshold=f"P(p_bar in [{p_min}, {p_max}]) >= {1.0 - q_bar_p}",
                    estimated_probability=mean_probability_ok,
                )
            )
        log_or_bound = ctx.get("log_odds_ratio_bound")
        if log_or_bound is not None:
            probability = 1.0 if coef_scale <= float(log_or_bound) else 0.0
            constraints.append(
                _constraint(
                    "log_odds_policy_contrast_envelope",
                    probability >= 1.0 - float(ctx.get("q_psi", 0.05)),
                    threshold=f"P(|psi| <= {log_or_bound}) >= {1.0 - float(ctx.get('q_psi', 0.05))}",
                    estimated_probability=probability,
                )
            )
        hyperparameter_space = {
            "baseline_probability": HyperparameterSpaceRecord(
                transform="logit", lower=1e-6, upper=1.0 - 1e-6, baseline=float(p0 or 0.5)
            ),
            "coefficient_scale": HyperparameterSpaceRecord(
                transform="log", lower=1e-3, upper=1e2, baseline=coef_scale
            ),
            "nu_beta": HyperparameterSpaceRecord(
                transform="identity", lower=1.0, upper=30.0, baseline=nu_beta
            ),
        }
        class_id = "logistic_baseline_aware_policy_v1"
    elif family is BayesianPolicyModelFamily.BART:
        alpha = float(hp.get("tree_split_alpha", hp.get("a", 0.95)))
        beta = float(hp.get("tree_split_beta", hp.get("b", 2.0)))
        k = float(hp.get("leaf_scale_k", hp.get("k", 2.0)))
        expected_terminal_nodes = hp.get("expected_terminal_nodes")
        constraints.extend(
            (
                _constraint("tree_split_alpha_range", 0.75 <= alpha <= 0.99),
                _constraint("tree_split_beta_range", 1.0 <= beta <= 3.0),
                _constraint("leaf_scale_k_range", 1.0 <= k <= 3.5),
            )
        )
        max_depth_probability = hp.get("max_depth_probability")
        if max_depth_probability is not None:
            constraints.append(
                _constraint(
                    "tree_depth_envelope",
                    float(max_depth_probability) >= 1.0 - float(ctx.get("q_D", 0.05)),
                    threshold=f"P(max_depth <= D_max) >= {1.0 - float(ctx.get('q_D', 0.05))}",
                    estimated_probability=float(max_depth_probability),
                )
            )
        if expected_terminal_nodes is not None:
            limit = _finite_positive(ctx.get("terminal_nodes_max", 8.0), 8.0)
            constraints.append(
                _constraint(
                    "expected_terminal_nodes_per_tree",
                    float(expected_terminal_nodes) <= limit,
                    threshold=limit,
                    estimated_probability=float(expected_terminal_nodes),
                )
            )
        treatment_effect_bound = ctx.get("treatment_effect_bound")
        treatment_effect_sup = hp.get("treatment_effect_sup")
        if treatment_effect_bound is not None and treatment_effect_sup is not None:
            probability = 1.0 if float(treatment_effect_sup) <= float(treatment_effect_bound) else 0.0
            constraints.append(
                _constraint(
                    "treatment_effect_heterogeneity_envelope",
                    probability >= 1.0 - float(ctx.get("q_tau", 0.05)),
                    threshold=f"P(sup |tau(x)| <= {treatment_effect_bound}) >= {1.0 - float(ctx.get('q_tau', 0.05))}",
                    estimated_probability=probability,
                )
            )
        hyperparameter_space = {
            "tree_split_alpha": HyperparameterSpaceRecord(
                transform="logit", lower=0.75, upper=0.99, baseline=alpha
            ),
            "tree_split_beta": HyperparameterSpaceRecord(
                transform="log", lower=1.0, upper=3.0, baseline=beta
            ),
            "leaf_scale_k": HyperparameterSpaceRecord(
                transform="log", lower=1.0, upper=3.5, baseline=k
            ),
        }
        notes.append("outcome-scaled BART priors require split or full-procedure calibration")
        class_id = "bart_sum_of_trees_policy_v1"
    elif family is BayesianPolicyModelFamily.GP:
        kernel = str(hp.get("kernel", "rbf")).lower()
        allowed_kernels = {
            "rbf",
            "squared_exponential",
            "matern12",
            "matern32",
            "matern52",
            "additive",
            "product",
        }
        lengthscale = _finite_positive(hp.get("lengthscale", hp.get("rho", 1.0)), 1.0)
        alpha = _finite_positive(
            hp.get("signal_std", np.sqrt(_finite_positive(hp.get("signal_variance", 1.0), 1.0))),
            1.0,
        )
        features = _as_2d_features(ctx.get("features"))
        constraints.append(_constraint("admissible_kernel", kernel in allowed_kernels))
        if features is not None and features.shape[1] >= 1:
            spacing = _minimum_positive_spacing(features[:, 0])
            if spacing is not None:
                c_min = _finite_positive(ctx.get("lengthscale_spacing_multiplier_min", 0.25), 0.25)
                constraints.append(
                    _constraint(
                        "lengthscale_lower_bound",
                        lengthscale >= c_min * spacing,
                        threshold=f"rho >= {c_min} * delta_x",
                        estimated_probability=1.0 if lengthscale >= c_min * spacing else 0.0,
                        details={"delta_x": spacing},
                    )
                )
            feature_range = float(np.ptp(features[:, 0]))
            if feature_range > 0.0 and ctx.get("lengthscale_range_multiplier_max") is not None:
                c_max = _finite_positive(ctx.get("lengthscale_range_multiplier_max"), 20.0)
                constraints.append(
                    _constraint(
                        "lengthscale_upper_bound",
                        lengthscale <= c_max * feature_range,
                        threshold=f"rho <= {c_max} * R_x",
                        estimated_probability=1.0 if lengthscale <= c_max * feature_range else 0.0,
                        details={"range_x": feature_range},
                    )
                )
        alpha_max = ctx.get("signal_std_max")
        if alpha_max is not None:
            alpha_limit = _finite_positive(alpha_max, float(alpha_max))
            constraints.append(
                _constraint(
                    "signal_amplitude_bound",
                    alpha <= alpha_limit,
                    threshold=alpha_limit,
                    estimated_probability=1.0 if alpha <= alpha_limit else 0.0,
                )
            )
        gp_sup_bound = ctx.get("gp_function_sup_bound")
        if gp_sup_bound is not None and prior_predictive_simulations is not None:
            sims = _as_simulation_matrix(prior_predictive_simulations)
            if sims is not None:
                probability = float(np.mean(np.max(np.abs(sims), axis=1) <= float(gp_sup_bound)))
                constraints.append(
                    _constraint(
                        "gp_function_supremum_envelope",
                        probability >= 1.0 - float(ctx.get("q_f", 0.05)),
                        threshold=f"P(sup |f(x)| <= {gp_sup_bound}) >= {1.0 - float(ctx.get('q_f', 0.05))}",
                        estimated_probability=probability,
                    )
                )
        hyperparameter_space = {
            "alpha": HyperparameterSpaceRecord(
                transform="log", lower=1e-3, upper=1e3, baseline=alpha
            ),
            "rho": HyperparameterSpaceRecord(
                transform="log", lower=1e-4, upper=1e4, baseline=lengthscale
            ),
            "sigma": HyperparameterSpaceRecord(
                transform="log",
                lower=1e-6,
                upper=1e3,
                baseline=np.sqrt(_finite_positive(hp.get("noise_variance", 0.1), 0.1)),
            ),
        }
        class_id = "gp_kernel_policy_v1"
    elif family is BayesianPolicyModelFamily.VAR:
        tightness = _finite_positive(hp.get("lambda", hp.get("prior_scale", 1.0)), 1.0)
        lag_decay = _finite_positive(hp.get("lag_decay", hp.get("a", 1.0)), 1.0)
        companion_radius = hp.get("companion_radius")
        constraints.extend(
            (
                _constraint("positive_overall_tightness", tightness > 0.0),
                _constraint("positive_lag_decay", lag_decay > 0.0),
            )
        )
        if companion_radius is not None:
            constraints.append(
                _constraint(
                    "stationary_companion_radius",
                    float(companion_radius) < 1.0,
                    threshold="rho(F) < 1",
                    estimated_probability=1.0 if float(companion_radius) < 1.0 else 0.0,
                )
            )
        forecast_bound = ctx.get("forecast_growth_bound")
        if forecast_bound is not None and prior_predictive_simulations is not None:
            sims = _as_simulation_matrix(prior_predictive_simulations)
            if sims is not None:
                growth = np.max(np.abs(sims - sims[:, :1]), axis=1)
                probability = float(np.mean(growth <= float(forecast_bound)))
                constraints.append(
                    _constraint(
                        "forecast_growth_envelope",
                        probability >= 1.0 - float(ctx.get("q_H", 0.05)),
                        threshold=f"P(max_h |Y_T+h - Y_T| <= {forecast_bound}) >= {1.0 - float(ctx.get('q_H', 0.05))}",
                        estimated_probability=probability,
                    )
                )
        irf_bound = ctx.get("irf_bound")
        irf_sup = hp.get("irf_sup")
        if irf_bound is not None and irf_sup is not None:
            probability = 1.0 if float(irf_sup) <= float(irf_bound) else 0.0
            constraints.append(
                _constraint(
                    "impulse_response_envelope",
                    probability >= 1.0 - float(ctx.get("q_irf", 0.05)),
                    threshold=f"P(max_h |IRF(h)| <= {irf_bound}) >= {1.0 - float(ctx.get('q_irf', 0.05))}",
                    estimated_probability=probability,
                )
            )
        hyperparameter_space = {
            "lambda": HyperparameterSpaceRecord(
                transform="log", lower=1e-4, upper=1e2, baseline=tightness
            ),
            "lag_decay": HyperparameterSpaceRecord(
                transform="log", lower=0.1, upper=5.0, baseline=lag_decay
            ),
        }
        class_id = "bvar_minnesota_policy_v1"
    else:
        class_id = "unknown_prior_policy_v1"
        hyperparameter_space = {}
        constraints.append(_constraint("known_model_family", False))

    return AdmissiblePriorClassRecord(
        class_id=class_id,
        constraints=tuple(constraints),
        hyperparameter_space=hyperparameter_space,
        notes=tuple(notes),
    )


def _mad(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size == 0:
        return 0.0
    median = float(np.median(arr))
    return float(np.median(np.abs(arr - median)))


def _safe_corr(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2 or y.size < 2:
        return 0.0
    sx = float(np.std(x))
    sy = float(np.std(y))
    if sx <= 1e-12 or sy <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _raw_policy_contrast(
    y: np.ndarray,
    treatment: np.ndarray | None,
    features: np.ndarray | None,
) -> float:
    if treatment is not None and treatment.shape[0] == y.shape[0]:
        treated = y[treatment > np.median(treatment)]
        control = y[treatment <= np.median(treatment)]
        if treated.size > 0 and control.size > 0:
            return float(np.mean(treated) - np.mean(control))
    if features is not None and features.shape[0] == y.shape[0] and features.shape[1] > 0:
        return _safe_corr(features[:, 0], y)
    return 0.0


def _zero_crossings(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if arr.size < 2:
        return 0.0
    centred = arr - float(np.median(arr))
    signs = np.sign(centred)
    signs[signs == 0.0] = 1.0
    return float(np.sum(signs[1:] * signs[:-1] < 0.0))


def prior_predictive_diagnostics(
    y: Sequence[float] | np.ndarray,
    *,
    model_family: BayesianPolicyModelFamily | str = BayesianPolicyModelFamily.LINEAR,
    treatment: Sequence[float] | np.ndarray | None = None,
    features: Sequence[Sequence[float]] | np.ndarray | None = None,
    plausible_bounds: tuple[float, float] | None = None,
) -> dict[str, float]:
    """Compute universal and family-specific prior-predictive diagnostics."""

    family = _coerce_model_family(model_family)
    arr = np.asarray(y, dtype=float).reshape(-1)
    if arr.size == 0:
        raise ValueError("prior-predictive diagnostics require at least one outcome")
    treatment_arr = None if treatment is None else np.asarray(treatment, dtype=float).reshape(-1)
    feature_arr = _as_2d_features(features, arr.shape[0])
    median = float(np.median(arr))
    mad = _mad(arr)
    diagnostics = {
        "outcome_median": median,
        "outcome_mad": mad,
        "outcome_tail_max_abs": float(np.max(np.abs(arr - median))),
        "outcome_bounds_fraction": 0.0,
        "raw_policy_contrast": _raw_policy_contrast(arr, treatment_arr, feature_arr),
    }
    if plausible_bounds is not None:
        lower, upper = map(float, plausible_bounds)
        diagnostics["outcome_bounds_fraction"] = float(np.mean((arr < lower) | (arr > upper)))

    if family is BayesianPolicyModelFamily.LINEAR:
        diagnostics["linear_prior_signal_ratio"] = float(np.var(arr) / max(mad * mad, 1e-12))
        diagnostics["linear_residual_scale_envelope"] = mad
    elif family is BayesianPolicyModelFamily.LOGISTIC:
        diagnostics["prevalence"] = float(np.mean(arr))
        diagnostics["separation_rate"] = float(np.mean((arr <= 0.0) | (arr >= 1.0)))
        diagnostics["deterministic_history_indicator"] = float(
            np.mean(arr) <= 1e-12 or np.mean(arr) >= 1.0 - 1e-12
        )
    elif family is BayesianPolicyModelFamily.BART:
        ordered = arr
        if feature_arr is not None and feature_arr.shape[1] > 0:
            ordered = arr[np.argsort(feature_arr[:, 0])]
        diagnostics["prior_function_range"] = float(np.max(arr) - np.min(arr))
        diagnostics["local_jump_max"] = (
            float(np.max(np.abs(np.diff(ordered)))) if ordered.size > 1 else 0.0
        )
    elif family is BayesianPolicyModelFamily.GP:
        ordered = arr
        if feature_arr is not None and feature_arr.shape[1] > 0:
            ordered = arr[np.argsort(feature_arr[:, 0])]
        diagnostics["gp_zero_crossings"] = _zero_crossings(ordered)
        diagnostics["gp_local_roughness"] = (
            float(np.mean(np.abs(np.diff(ordered)))) if ordered.size > 1 else 0.0
        )
        diagnostics["gp_amplitude_to_noise"] = float((np.max(arr) - np.min(arr)) / max(mad, 1e-12))
    elif family is BayesianPolicyModelFamily.VAR:
        diagnostics["var_lag1_autocorrelation"] = (
            _safe_corr(arr[:-1], arr[1:]) if arr.size > 2 else 0.0
        )
        diagnostics["var_forecast_growth_proxy"] = (
            float(np.max(np.abs(np.diff(arr)))) if arr.size > 1 else 0.0
        )
        diagnostics["var_explosiveness_proxy"] = float(
            np.max(np.abs(arr - arr[0])) / max(mad, 1e-12)
        )

    return {
        key: float(value) if np.isfinite(float(value)) else 0.0
        for key, value in diagnostics.items()
    }


def prior_predictive_rank_test(
    observed_y: Sequence[float] | np.ndarray,
    simulated_y: Sequence[Sequence[float]] | np.ndarray,
    *,
    alpha: float = 0.05,
    model_family: BayesianPolicyModelFamily | str = BayesianPolicyModelFamily.LINEAR,
    treatment: Sequence[float] | np.ndarray | None = None,
    features: Sequence[Sequence[float]] | np.ndarray | None = None,
    plausible_bounds: tuple[float, float] | None = None,
    conditioned_on: Sequence[str] = ("covariates", "sampling_design"),
    diagnostics_fn: Callable[[np.ndarray], Mapping[str, float]] | None = None,
) -> PriorPredictiveCheckRecord:
    """Run the exchangeability-calibrated prior-predictive rank test."""

    observed = np.asarray(observed_y, dtype=float).reshape(-1)
    simulations = np.asarray(simulated_y, dtype=float)
    if simulations.ndim == 1:
        simulations = simulations.reshape(1, -1)
    if simulations.ndim != 2 or simulations.shape[0] == 0:
        raise ValueError("simulated_y must have shape (n_simulations, n_observations)")
    if simulations.shape[1] != observed.shape[0]:
        raise ValueError("observed and simulated histories must have the same length")

    def compute(values: np.ndarray) -> Mapping[str, float]:
        if diagnostics_fn is not None:
            return diagnostics_fn(values)
        return prior_predictive_diagnostics(
            values,
            model_family=model_family,
            treatment=treatment,
            features=features,
            plausible_bounds=plausible_bounds,
        )

    diagnostic_maps = [dict(compute(observed))]
    diagnostic_maps.extend(dict(compute(row)) for row in simulations)
    candidate_keys = tuple(
        key for key in diagnostic_maps[0] if all(key in item for item in diagnostic_maps)
    )
    keys = tuple(
        key
        for key in candidate_keys
        if np.ptp(np.asarray([float(item[key]) for item in diagnostic_maps], dtype=float)) > 1e-12
    )
    if not keys and candidate_keys:
        keys = (candidate_keys[0],)
    if not keys:
        raise ValueError("at least one shared prior-predictive diagnostic is required")
    values = np.asarray(
        [[float(item[key]) for key in keys] for item in diagnostic_maps],
        dtype=float,
    )
    if not np.all(np.isfinite(values)):
        raise ValueError("prior-predictive diagnostics must be finite")

    ranks = np.empty_like(values, dtype=float)
    for col in range(values.shape[1]):
        column = values[:, col]
        for row in range(values.shape[0]):
            ranks[row, col] = (1.0 + float(np.sum(column <= column[row]))) / (
                values.shape[0] + 1.0
            )
    nonconformity = np.max(np.abs(2.0 * ranks - 1.0), axis=1)
    p_value = (1.0 + float(np.sum(nonconformity[1:] >= nonconformity[0]))) / (
        simulations.shape[0] + 1.0
    )
    mc_se = float(np.sqrt(p_value * (1.0 - p_value) / max(simulations.shape[0] + 1, 1)))
    diagnostic_records = []
    rejected: list[str] = []
    per_diagnostic_alpha = float(alpha) / max(1, len(keys))
    for idx, key in enumerate(keys):
        rank = float(ranks[0, idx])
        if rank <= per_diagnostic_alpha / 2.0 or rank >= 1.0 - per_diagnostic_alpha / 2.0:
            rejected.append(key)
        diagnostic_records.append(
            PriorPredictiveDiagnosticRecord(
                name=key,
                observed=float(values[0, idx]),
                prior_predictive_rank=rank,
                simulated_mean=float(np.mean(values[1:, idx])),
                simulated_sd=float(np.std(values[1:, idx], ddof=1))
                if simulations.shape[0] > 1
                else 0.0,
            )
        )
    return PriorPredictiveCheckRecord(
        status=PriorSensitivityStatus.PASS
        if p_value >= float(alpha)
        else PriorSensitivityStatus.FAIL,
        alpha=float(alpha),
        p_value=float(p_value),
        monte_carlo_se=mc_se,
        n_simulations=int(simulations.shape[0]),
        conditioned_on=tuple(str(item) for item in conditioned_on),
        diagnostics=tuple(diagnostic_records),
        rejected_diagnostics=tuple(rejected),
        observed_nonconformity=float(nonconformity[0]),
    )


def _half_width(interval: tuple[float, float]) -> float:
    lower, upper = map(float, interval)
    return max((upper - lower) / 2.0, 0.0)


def _center(interval: tuple[float, float]) -> float:
    lower, upper = map(float, interval)
    return (lower + upper) / 2.0


def _decision_label(interval: tuple[float, float]) -> str:
    lower, upper = map(float, interval)
    if lower > 0.0:
        return "positive"
    if upper < 0.0:
        return "negative"
    return "indeterminate"


def build_sensitivity_record_from_intervals(
    *,
    estimand_id: str,
    baseline_interval: tuple[float, float],
    perturbation_intervals: Sequence[Mapping[str, Any] | SensitivityCurvePoint],
    credible_interval_level: float = 0.95,
    width_factor_threshold: float = 2.0,
    center_shift_threshold: float = 1.0,
    decision_stability_threshold: float | None = None,
) -> PosteriorSensitivityRecord:
    """Build the posterior credible-interval half-width sensitivity curve."""

    baseline = (float(baseline_interval[0]), float(baseline_interval[1]))
    baseline_hw = max(_half_width(baseline), 1e-12)
    points: list[SensitivityCurvePoint] = []
    for raw in perturbation_intervals:
        point = (
            raw
            if isinstance(raw, SensitivityCurvePoint)
            else SensitivityCurvePoint.model_validate(dict(raw))
        )
        points.append(point)
    if not points:
        points.append(
            SensitivityCurvePoint(
                hyperparameter="baseline",
                multiplier=1.0,
                interval=baseline,
                half_width=baseline_hw,
            )
        )
    half_widths = np.asarray([point.half_width for point in points] + [baseline_hw], dtype=float)
    max_hw = float(np.max(np.maximum(half_widths, 1e-12)))
    min_hw = float(np.min(np.maximum(half_widths, 1e-12)))
    width_factor = max_hw / min_hw
    expansion = max_hw / baseline_hw
    contraction = baseline_hw / min_hw
    center_shift = max(
        abs(_center(point.interval) - _center(baseline)) / baseline_hw for point in points
    )
    baseline_decision = _decision_label(baseline)
    decision_stability = float(
        np.mean([_decision_label(point.interval) == baseline_decision for point in points])
    )
    pass_gate = (
        width_factor <= float(width_factor_threshold)
        and center_shift <= float(center_shift_threshold)
        and (
            decision_stability_threshold is None
            or decision_stability >= float(decision_stability_threshold)
        )
    )
    elasticities: dict[str, float] = {}
    by_hyperparameter: dict[str, list[SensitivityCurvePoint]] = {}
    for point in points:
        by_hyperparameter.setdefault(point.hyperparameter, []).append(point)
    for name, grouped in by_hyperparameter.items():
        lower = next((point for point in grouped if point.multiplier and point.multiplier < 1.0), None)
        upper = next((point for point in grouped if point.multiplier and point.multiplier > 1.0), None)
        if lower is not None and upper is not None:
            denominator = np.log(float(upper.multiplier)) - np.log(float(lower.multiplier))
            if abs(denominator) > 1e-12 and lower.half_width > 0.0 and upper.half_width > 0.0:
                elasticities[name] = float(
                    (np.log(upper.half_width) - np.log(lower.half_width)) / denominator
                )
    return PosteriorSensitivityRecord(
        estimand_id=estimand_id,
        credible_interval_level=float(credible_interval_level),
        baseline_interval=baseline,
        baseline_half_width=float(baseline_hw),
        width_factor=float(width_factor),
        expansion=float(expansion),
        contraction=float(contraction),
        max_center_shift_in_half_widths=float(center_shift),
        decision_stability=decision_stability,
        pass_=pass_gate,
        curve=tuple(points),
        elasticities=elasticities,
    )


def _tier_threshold(tier: ReadinessTier, key: str) -> float | bool | None:
    return _READINESS_THRESHOLDS[tier][key]


def _satisfies_tier(
    tier: ReadinessTier,
    *,
    prior_predictive_check: PriorPredictiveCheckRecord | None,
    sensitivity: PosteriorSensitivityRecord | None,
    admissible_prior_class: AdmissiblePriorClassRecord | None,
    class_adjusted_pass: bool,
) -> bool:
    if tier is ReadinessTier.TIER_0:
        return prior_predictive_check is not None or sensitivity is not None
    if admissible_prior_class is not None and not admissible_prior_class.passed:
        return False
    if prior_predictive_check is None or prior_predictive_check.p_value is None:
        return False
    p_min = _tier_threshold(tier, "p_value_min")
    if isinstance(p_min, float) and prior_predictive_check.p_value < p_min:
        return False
    required = _tier_threshold(tier, "class_adjusted_required")
    if bool(required) and not class_adjusted_pass:
        return False
    if sensitivity is None:
        return False
    width_max = _tier_threshold(tier, "width_factor_max")
    center_max = _tier_threshold(tier, "center_shift_max")
    stability_min = _tier_threshold(tier, "decision_stability_min")
    if isinstance(width_max, float) and sensitivity.width_factor > width_max:
        return False
    if isinstance(center_max, float) and sensitivity.max_center_shift_in_half_widths > center_max:
        return False
    if isinstance(stability_min, float) and sensitivity.decision_stability < stability_min:
        return False
    return True


def achieved_readiness_tier(
    *,
    prior_predictive_check: PriorPredictiveCheckRecord | None,
    sensitivity: PosteriorSensitivityRecord | None,
    admissible_prior_class: AdmissiblePriorClassRecord | None = None,
    class_adjusted_pass: bool = False,
) -> ReadinessTier:
    """Return the highest readiness tier satisfied by the gate evidence."""

    achieved = ReadinessTier.NONE
    for tier in (
        ReadinessTier.TIER_0,
        ReadinessTier.TIER_1,
        ReadinessTier.TIER_2,
        ReadinessTier.TIER_3,
        ReadinessTier.TIER_4,
    ):
        if _satisfies_tier(
            tier,
            prior_predictive_check=prior_predictive_check,
            sensitivity=sensitivity,
            admissible_prior_class=admissible_prior_class,
            class_adjusted_pass=class_adjusted_pass,
        ):
            achieved = tier
    return achieved


def calibrate_composite_prior_class(
    candidate_p_values: Mapping[str, float],
    *,
    alpha: float = 0.05,
    method: str = "bonferroni",
    null_p_min_samples: Sequence[float] | np.ndarray | None = None,
    calibrated_cutoff: float | None = None,
) -> PriorClassCalibrationRecord:
    """Calibrate a class-level p-min gate over a prior perturbation grid.

    ``method="simulation"`` uses the empirical alpha-quantile of simulated
    p-min values. ``method="bonferroni"`` is the explicit small-grid fallback.
    """

    finite_values = {
        str(key): float(value)
        for key, value in candidate_p_values.items()
        if np.isfinite(float(value))
    }
    if not finite_values:
        return PriorClassCalibrationRecord(
            status=PriorSensitivityStatus.NOT_RUN,
            method=method,
            alpha=float(alpha),
            notes=("no_candidate_prior_p_values",),
        )
    p_min = float(min(finite_values.values()))
    method_name = str(method).strip().lower()
    cutoff: float
    n_outer = 0
    notes: list[str] = []
    if calibrated_cutoff is not None:
        cutoff = float(calibrated_cutoff)
        method_name = f"{method_name}_declared_cutoff"
    elif method_name == "simulation" and null_p_min_samples is not None:
        samples = np.asarray(null_p_min_samples, dtype=float).reshape(-1)
        samples = samples[np.isfinite(samples)]
        if samples.size > 0:
            cutoff = float(np.quantile(samples, np.clip(float(alpha), 0.0, 1.0)))
            n_outer = int(samples.size)
        else:
            cutoff = float(alpha) / max(len(finite_values), 1)
            method_name = "bonferroni"
            notes.append("empty_simulation_calibration_fell_back_to_bonferroni")
    else:
        cutoff = float(alpha) / max(len(finite_values), 1)
        method_name = "bonferroni"
    class_pass = p_min >= cutoff
    return PriorClassCalibrationRecord(
        status=PriorSensitivityStatus.PASS if class_pass else PriorSensitivityStatus.FAIL,
        method=method_name,
        alpha=float(alpha),
        p_min=p_min,
        calibrated_cutoff=cutoff,
        n_candidates=len(finite_values),
        n_outer_simulations=n_outer,
        candidate_prior_ids=tuple(sorted(finite_values)),
        candidate_p_values=finite_values,
        class_adjusted_pass=class_pass,
        notes=tuple(notes),
    )


def assemble_prior_sensitivity_report(
    *,
    model_family: BayesianPolicyModelFamily | str,
    selected_prior_id: str,
    admissible_prior_class: AdmissiblePriorClassRecord,
    prior_predictive_check: PriorPredictiveCheckRecord | None,
    sensitivity: PosteriorSensitivityRecord | None,
    readiness_tier_requested: ReadinessTier | str = ReadinessTier.TIER_1,
    uses_outcome_to_set_prior: bool = False,
    data_conditioning_mode: DataConditioningMode | str = DataConditioningMode.NONE,
    prior_class_calibration: PriorClassCalibrationRecord | None = None,
    class_adjusted_pass: bool = False,
    sensitivity_by_estimand: Sequence[PosteriorSensitivityRecord] | None = None,
    warnings: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> PriorSensitivityReport:
    """Combine admissibility, prior-predictive, and sensitivity gates."""

    requested = _coerce_readiness_tier(readiness_tier_requested)
    effective_class_adjusted_pass = (
        prior_class_calibration.class_adjusted_pass
        if prior_class_calibration is not None
        else class_adjusted_pass
    )
    sensitivity_records = tuple(sensitivity_by_estimand or ([sensitivity] if sensitivity is not None else []))
    achieved = achieved_readiness_tier(
        prior_predictive_check=prior_predictive_check,
        sensitivity=sensitivity,
        admissible_prior_class=admissible_prior_class,
        class_adjusted_pass=effective_class_adjusted_pass,
    )
    reasons: list[str] = []
    if not admissible_prior_class.passed:
        reasons.extend(
            f"admissible_prior_constraint_failed:{constraint.name}"
            for constraint in admissible_prior_class.constraints
            if not constraint.passed
        )
    if (
        prior_predictive_check is not None
        and prior_predictive_check.status is PriorSensitivityStatus.FAIL
    ):
        reasons.append("prior_predictive_p_value_below_alpha")
    if (
        prior_class_calibration is not None
        and prior_class_calibration.status is PriorSensitivityStatus.FAIL
    ):
        reasons.append("class_adjusted_prior_predictive_p_min_below_calibrated_cutoff")
    if sensitivity is not None and not sensitivity.pass_:
        thresholds = _READINESS_THRESHOLDS.get(requested, _READINESS_THRESHOLDS[ReadinessTier.TIER_1])
        width_max = thresholds.get("width_factor_max")
        center_max = thresholds.get("center_shift_max")
        stability_min = thresholds.get("decision_stability_min")
        if isinstance(width_max, float) and sensitivity.width_factor > width_max:
            reasons.append("credible_interval_width_factor_exceeds_tier_threshold")
        if (
            isinstance(center_max, float)
            and sensitivity.max_center_shift_in_half_widths > center_max
        ):
            reasons.append("credible_interval_center_shift_exceeds_tier_threshold")
        if isinstance(stability_min, float) and sensitivity.decision_stability < stability_min:
            reasons.append("decision_stability_below_tier_threshold")
    if (
        requested in {ReadinessTier.TIER_2, ReadinessTier.TIER_3, ReadinessTier.TIER_4}
        and not effective_class_adjusted_pass
    ):
        reasons.append("class_adjusted_prior_predictive_calibration_missing")
    if _TIER_ORDER[achieved] < _TIER_ORDER[requested]:
        reasons.append("readiness_tier_requested_not_achieved")

    status = PriorSensitivityStatus.PASS
    if reasons:
        status = PriorSensitivityStatus.FAIL
    elif achieved is ReadinessTier.TIER_0 and requested is ReadinessTier.TIER_0:
        status = PriorSensitivityStatus.WARNING
    return PriorSensitivityReport(
        status=status,
        readiness_tier_requested=requested,
        readiness_tier_achieved=achieved,
        model_family=_coerce_model_family(model_family),
        selected_prior_id=selected_prior_id,
        admissible_prior_class_id=admissible_prior_class.class_id,
        uses_outcome_to_set_prior=uses_outcome_to_set_prior,
        data_conditioning_mode=_coerce_conditioning_mode(data_conditioning_mode),
        admissible_prior_class=admissible_prior_class,
        prior_predictive_check=prior_predictive_check,
        prior_class_calibration=prior_class_calibration,
        sensitivity=sensitivity,
        sensitivity_by_estimand=sensitivity_records,
        failure_reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(str(item) for item in warnings)),
        metadata=dict(metadata or {}),
    )


def simulate_linear_gaussian_prior_predictive(
    design_matrix: Sequence[Sequence[float]] | np.ndarray,
    *,
    prior_scale: float,
    n_simulations: int,
    rng: np.random.Generator,
    log_sigma_scale: float | None = None,
) -> np.ndarray:
    """Simulate Gaussian linear-regression histories from the declared prior."""

    design = np.asarray(design_matrix, dtype=float)
    if design.ndim != 2:
        raise ValueError("design_matrix must be two-dimensional")
    scale = _finite_positive(prior_scale, 1.0)
    log_scale = _finite_positive(log_sigma_scale, scale)
    beta = rng.normal(loc=0.0, scale=scale, size=(max(1, int(n_simulations)), design.shape[1]))
    log_sigma = rng.normal(loc=0.0, scale=log_scale, size=beta.shape[0])
    mean = beta @ design.T
    noise = rng.normal(loc=0.0, scale=np.exp(log_sigma)[:, None], size=mean.shape)
    return np.asarray(mean + noise, dtype=float)


def simulate_logistic_prior_predictive(
    features: Sequence[Sequence[float]] | np.ndarray,
    *,
    baseline_probability: float,
    coefficient_scale: float,
    n_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulate Bernoulli histories from a baseline-aware logistic prior."""

    x = np.asarray(features, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    p0 = float(np.clip(baseline_probability, 1e-6, 1.0 - 1e-6))
    alpha = np.log(p0 / (1.0 - p0))
    scale = _finite_positive(coefficient_scale, 2.5)
    beta = rng.normal(loc=0.0, scale=scale, size=(max(1, int(n_simulations)), x.shape[1]))
    logits = alpha + beta @ x.T
    probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
    return rng.binomial(1, probabilities).astype(float)


def _kernel_matrix(
    x1: np.ndarray,
    x2: np.ndarray,
    *,
    kernel: str,
    lengthscale: float,
    signal_variance: float,
) -> np.ndarray:
    diff = x1[:, None, :] - x2[None, :, :]
    distance = np.sqrt(np.maximum(np.sum(diff * diff, axis=-1), 0.0))
    ls = max(float(lengthscale), 1e-12)
    variance = max(float(signal_variance), 1e-12)
    kernel_name = str(kernel).lower()
    if kernel_name == "matern12":
        base = np.exp(-distance / ls)
    elif kernel_name == "matern32":
        scaled = np.sqrt(3.0) * distance / ls
        base = (1.0 + scaled) * np.exp(-scaled)
    elif kernel_name == "matern52":
        scaled = np.sqrt(5.0) * distance / ls
        base = (1.0 + scaled + scaled * scaled / 3.0) * np.exp(-scaled)
    else:
        base = np.exp(-0.5 * (distance / ls) ** 2)
    return variance * base


def simulate_gp_prior_predictive(
    features: Sequence[Sequence[float]] | np.ndarray,
    *,
    kernel: str,
    lengthscale: float,
    signal_variance: float,
    noise_variance: float,
    n_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulate GP regression histories at the observed design points."""

    x = np.asarray(features, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    covariance = _kernel_matrix(
        x,
        x,
        kernel=kernel,
        lengthscale=lengthscale,
        signal_variance=signal_variance,
    )
    covariance += max(float(noise_variance), 1e-12) * np.eye(x.shape[0])
    covariance += 1e-8 * np.eye(x.shape[0])
    try:
        chol = np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError:
        eigvals, eigvecs = np.linalg.eigh(covariance)
        chol = eigvecs @ np.diag(np.sqrt(np.maximum(eigvals, 1e-10)))
    standard = rng.normal(size=(x.shape[0], max(1, int(n_simulations))))
    return np.asarray((chol @ standard).T, dtype=float)


def simulate_bart_prior_predictive(
    features: Sequence[Sequence[float]] | np.ndarray,
    *,
    num_trees: int,
    tree_split_alpha: float = 0.95,
    tree_split_beta: float = 2.0,
    leaf_scale_k: float = 2.0,
    function_scale: float = 1.0,
    noise_scale: float = 0.1,
    n_simulations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, float]]:
    """Simulate lightweight sum-of-stumps BART prior histories and tree summaries."""

    x = np.asarray(features, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    n_obs, n_features = x.shape
    trees = max(1, int(num_trees))
    sims = np.zeros((max(1, int(n_simulations)), n_obs), dtype=float)
    max_depths: list[float] = []
    terminal_nodes: list[float] = []
    leaf_sd = max(float(function_scale), 1e-12) / (max(float(leaf_scale_k), 1e-12) * np.sqrt(trees))
    split_alpha = float(np.clip(tree_split_alpha, 0.0, 1.0))
    split_beta = max(float(tree_split_beta), 1e-12)
    for sim_idx in range(sims.shape[0]):
        fitted = np.zeros(n_obs, dtype=float)
        for _ in range(trees):
            split_probability_root = split_alpha
            if rng.uniform() < split_probability_root and n_features > 0:
                feature_idx = int(rng.integers(0, n_features))
                threshold = float(np.median(x[:, feature_idx]))
                left = x[:, feature_idx] <= threshold
                left_value = float(rng.normal(scale=leaf_sd))
                right_value = float(rng.normal(scale=leaf_sd))
                fitted += np.where(left, left_value, right_value)
                max_depths.append(1.0)
                terminal_nodes.append(2.0)
            else:
                fitted += float(rng.normal(scale=leaf_sd))
                max_depths.append(0.0)
                terminal_nodes.append(1.0)
        sims[sim_idx] = fitted + rng.normal(scale=max(float(noise_scale), 1e-12), size=n_obs)
    d_max = 1.0
    summary = {
        "expected_terminal_nodes": float(np.mean(terminal_nodes)) if terminal_nodes else 1.0,
        "max_depth_probability": float(np.mean(np.asarray(max_depths) <= d_max))
        if max_depths
        else 1.0,
        "tree_split_alpha": split_alpha,
        "tree_split_beta": split_beta,
        "leaf_scale_k": float(leaf_scale_k),
    }
    return sims, summary


def simulate_var_prior_predictive(
    initial_values: Sequence[float] | np.ndarray,
    *,
    n_lags: int,
    horizon: int,
    tightness: float,
    lag_decay: float = 1.0,
    innovation_scale: float = 1.0,
    n_simulations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, float]]:
    """Simulate univariate Minnesota-style AR/VAR prior histories."""

    initial = np.asarray(initial_values, dtype=float).reshape(-1)
    lags = max(1, int(n_lags))
    if initial.size < lags:
        raise ValueError("initial_values must contain at least n_lags observations")
    total = max(lags + 1, int(horizon))
    sims = np.zeros((max(1, int(n_simulations)), total), dtype=float)
    sims[:, :lags] = initial[-lags:][None, :]
    lag_index = np.arange(1, lags + 1, dtype=float)
    coef_sd = max(float(tightness), 1e-12) / (lag_index ** max(float(lag_decay), 1e-12))
    radii: list[float] = []
    for sim_idx in range(sims.shape[0]):
        phi = rng.normal(loc=0.0, scale=coef_sd)
        if lags > 0:
            phi[0] += 0.5
        radii.append(float(np.sum(np.abs(phi))))
        for t_idx in range(lags, total):
            lagged = sims[sim_idx, t_idx - lags : t_idx][::-1]
            sims[sim_idx, t_idx] = float(
                np.dot(phi, lagged) + rng.normal(scale=max(float(innovation_scale), 1e-12))
            )
    summary = {
        "companion_radius": float(np.mean(radii)) if radii else 0.0,
        "tightness": float(tightness),
        "lag_decay": float(lag_decay),
    }
    return sims, summary


def prior_scale_sensitivity_from_samples(
    *,
    samples: Mapping[str, Sequence[float] | np.ndarray],
    estimand_id: str,
    baseline_interval: tuple[float, float],
    credible_interval_level: float,
    baseline_prior_scale: float,
    candidate_multipliers: Sequence[float] = (0.5, 2.0),
    ess_threshold: float | None = None,
) -> PosteriorSensitivityRecord:
    """Estimate interval sensitivity by prior-scale importance reweighting."""

    if estimand_id not in samples:
        raise ValueError(f"estimand samples missing: {estimand_id}")
    scale0 = _finite_positive(baseline_prior_scale, 1.0)
    flattened = {name: np.asarray(value, dtype=float).reshape(-1) for name, value in samples.items()}
    n_draws = len(next(iter(flattened.values())))
    if any(value.shape[0] != n_draws for value in flattened.values()):
        raise ValueError("all sample arrays must have the same number of draws")
    parameter_stack = np.column_stack([flattened[name] for name in sorted(flattened)])
    estimand = flattened[estimand_id]
    alpha = max(1e-6, 1.0 - float(credible_interval_level))
    threshold = float(ess_threshold) if ess_threshold is not None else max(1000.0, 0.4 * n_draws)
    points: list[SensitivityCurvePoint] = []
    warnings: list[str] = []
    for multiplier in candidate_multipliers:
        scale = max(scale0 * float(multiplier), 1e-12)
        log_ratio = (
            -0.5 * np.sum((parameter_stack / scale) ** 2, axis=1)
            - parameter_stack.shape[1] * np.log(scale)
            + 0.5 * np.sum((parameter_stack / scale0) ** 2, axis=1)
            + parameter_stack.shape[1] * np.log(scale0)
        )
        log_ratio -= float(np.max(log_ratio))
        weights = np.exp(log_ratio)
        ess = float(np.sum(weights) ** 2 / max(float(np.sum(weights * weights)), 1e-12))
        lower, upper = weighted_quantile(
            estimand,
            (alpha / 2.0, 1.0 - alpha / 2.0),
            sample_weight=weights,
        )
        interval = (float(lower), float(upper))
        refit_required = ess < threshold
        if refit_required:
            warnings.append("importance_weight_ess_below_refit_threshold")
        points.append(
            SensitivityCurvePoint(
                hyperparameter="prior_scale",
                multiplier=float(multiplier),
                interval=interval,
                half_width=_half_width(interval),
                effective_sample_size=ess,
                refit_required=refit_required,
            )
        )
    record = build_sensitivity_record_from_intervals(
        estimand_id=estimand_id,
        baseline_interval=baseline_interval,
        perturbation_intervals=points,
        credible_interval_level=credible_interval_level,
    )
    return record.model_copy(update={"warnings": tuple(dict.fromkeys(warnings))})


def prior_scale_sensitivity_records_from_samples(
    *,
    samples: Mapping[str, Sequence[float] | np.ndarray],
    credible_intervals: Mapping[str, tuple[float, float]],
    credible_interval_level: float,
    baseline_prior_scale: float,
    estimand_ids: Sequence[str] | None = None,
    candidate_multipliers: Sequence[float] = (0.5, 2.0),
    ess_threshold: float | None = None,
) -> tuple[PosteriorSensitivityRecord, ...]:
    """Attach the half-width sensitivity curve to every declared estimand."""

    ids = tuple(estimand_ids or credible_intervals.keys())
    records: list[PosteriorSensitivityRecord] = []
    for estimand_id in ids:
        if estimand_id not in samples or estimand_id not in credible_intervals:
            continue
        records.append(
            prior_scale_sensitivity_from_samples(
                samples=samples,
                estimand_id=estimand_id,
                baseline_interval=credible_intervals[estimand_id],
                credible_interval_level=credible_interval_level,
                baseline_prior_scale=baseline_prior_scale,
                candidate_multipliers=candidate_multipliers,
                ess_threshold=ess_threshold,
            )
        )
    return tuple(records)


def weighted_quantile(
    values: np.ndarray,
    quantiles: Sequence[float] | np.ndarray,
    *,
    sample_weight: np.ndarray | None = None,
) -> np.ndarray:
    """Compute weighted quantiles without importing posterior protocols."""

    arr = np.asarray(values, dtype=float).reshape(-1)
    probs = np.atleast_1d(np.asarray(quantiles, dtype=float))
    if arr.size == 0:
        raise ValueError("weighted_quantile requires at least one sample")
    if sample_weight is None:
        return np.asarray(np.quantile(arr, probs), dtype=float)
    weights = np.asarray(sample_weight, dtype=float).reshape(-1)
    if weights.shape[0] != arr.shape[0]:
        raise ValueError("sample_weight must align with values")
    if np.any(weights < 0.0) or not np.all(np.isfinite(weights)):
        raise ValueError("sample_weight must be finite and non-negative")
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError("sample_weight must sum to a positive value")
    order = np.argsort(arr)
    sorted_values = arr[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights) / total
    return np.asarray(np.interp(np.clip(probs, 0.0, 1.0), cumulative, sorted_values), dtype=float)


__all__ = [
    "AdmissiblePriorClassRecord",
    "BayesianPolicyModelFamily",
    "DataConditioningMode",
    "HyperparameterSpaceRecord",
    "PosteriorSensitivityRecord",
    "PriorConstraintRecord",
    "PriorClassCalibrationRecord",
    "PriorPredictiveCheckRecord",
    "PriorPredictiveDiagnosticRecord",
    "PriorSensitivityReport",
    "PriorSensitivityStatus",
    "ReadinessTier",
    "SensitivityCurvePoint",
    "achieved_readiness_tier",
    "assemble_prior_sensitivity_report",
    "build_admissible_prior_class",
    "build_sensitivity_record_from_intervals",
    "calibrate_composite_prior_class",
    "infer_bayesian_policy_model_family",
    "not_run_prior_sensitivity_report",
    "prior_predictive_diagnostics",
    "prior_predictive_rank_test",
    "prior_scale_sensitivity_records_from_samples",
    "prior_scale_sensitivity_from_samples",
    "simulate_bart_prior_predictive",
    "simulate_gp_prior_predictive",
    "simulate_linear_gaussian_prior_predictive",
    "simulate_logistic_prior_predictive",
    "simulate_var_prior_predictive",
    "weighted_quantile",
]
