"""DP-aware calibration helpers for conditional independence tests.

This module centralizes the privacy context, threshold-policy resolution,
sample-size requirement heuristics, and conservative threshold corrections used
by CI tests under differentially private releases.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.dp_robustness import classical_gaussian_sigma

type Path = Any
_Path = __import__("pathlib", fromlist=("Path",)).Path
_EPS = 1e-12

DPMechanism = Literal["none", "laplace_counts", "gaussian_counts", "noised_rows"]

__all__ = [
    "CIFPRInflationBound",
    "CISampleSizeRequirement",
    "CITestCalibration",
    "CITestThresholdPolicy",
    "DPContext",
    "calibrate_discrete_ci",
    "calibrate_kernel_ci",
    "coerce_dp_context",
    "effective_privacy_xi",
    "required_n_chi2",
    "required_n_kernel",
    "resolve_ci_threshold_policy",
]


class DPContext(BaseModel):
    """Privacy context attached to a CI test invocation."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mechanism: DPMechanism = "none"
    epsilon: float = Field(default=math.inf, gt=0.0)
    delta: float = Field(default=0.0, ge=0.0, lt=1.0)
    l1_sensitivity: float | None = Field(default=None, gt=0.0)
    l2_sensitivity: float | None = Field(default=None, gt=0.0)
    clip_norm: float | None = Field(default=None, gt=0.0)
    effective_xi: float | None = Field(default=None, gt=0.0)
    released_statistics: str | None = None
    sample_size_n: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_private(self) -> bool:
        return self.mechanism != "none"

    @property
    def mechanism_family(self) -> str:
        if self.mechanism == "laplace_counts":
            return "laplace"
        if self.mechanism == "gaussian_counts":
            return "gaussian"
        if self.mechanism == "noised_rows":
            return "row_noise"
        return "none"


class CITestThresholdPolicy(BaseModel):
    """Resolved CI calibration controls, optionally sourced from the registry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha_base: float = Field(default=0.05, gt=0.0, lt=1.0)
    mc_bootstrap_B: int = Field(default=299, ge=32)
    min_n_rule_constant: float = Field(default=4.0, gt=0.0)
    naive_fpr_bound_rho: float = Field(default=0.01, ge=0.0, le=1.0)
    threshold_scope: dict[str, str | None] = Field(default_factory=dict)
    threshold_registry_version: int | None = None


class CIFPRInflationBound(BaseModel):
    """Conservative upper bound for naive clean-data thresholding on DP data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    naive_alpha: float = Field(gt=0.0, lt=1.0)
    threshold_shift: float = Field(ge=0.0)
    rho_tail: float = Field(ge=0.0, le=1.0)
    reject_probability_upper_bound: float = Field(ge=0.0, le=1.0)
    reference_threshold: float = Field(ge=0.0)
    tail_mass: float = Field(ge=0.0, le=1.0)


class CISampleSizeRequirement(BaseModel):
    """Sufficient sample-size proxy for a calibrated CI test."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: Literal["kernel_ci", "categorical_ci"]
    required_n: int = Field(ge=1)
    target_power: float = Field(gt=0.0, lt=1.0)
    epsilon: float = Field(gt=0.0)
    delta: float = Field(ge=0.0, lt=1.0)
    effect_proxy: float | None = Field(default=None, gt=0.0)
    method: str
    notes: list[str] = Field(default_factory=list)


class CITestCalibration(BaseModel):
    """Normalized CI calibration output consumed by concrete test methods."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha: float = Field(gt=0.0, lt=1.0)
    p_value: float = Field(ge=0.0, le=1.0)
    critical_statistic_value: float = Field(ge=0.0)
    calibration_mode: str
    threshold_policy: CITestThresholdPolicy
    sample_size_requirement: CISampleSizeRequirement | None = None
    naive_fpr_inflation_bound: CIFPRInflationBound | None = None
    dp_context_summary: dict[str, Any] | None = None
    null_summary: dict[str, Any] = Field(default_factory=dict)


def coerce_dp_context(payload: DPContext | Mapping[str, Any] | None) -> DPContext | None:
    """Normalize an optional DP context payload."""

    if payload is None:
        return None
    if isinstance(payload, DPContext):
        return payload if payload.is_private else None
    if not isinstance(payload, Mapping):
        raise TypeError("dp_context must be a mapping or DPContext")
    context = DPContext.model_validate(dict(payload))
    return context if context.is_private else None


def effective_privacy_xi(dp_context: DPContext | None) -> float:
    """Return an effective privacy level used by DP kernel-rate heuristics."""

    if dp_context is None or not dp_context.is_private:
        return math.inf
    if dp_context.effective_xi is not None:
        return float(dp_context.effective_xi)
    epsilon = float(dp_context.epsilon)
    if not math.isfinite(epsilon):
        return math.inf
    if dp_context.delta <= 0.0:
        return max(epsilon, _EPS)
    penalty = math.sqrt(max(2.0 * math.log(1.25 / max(dp_context.delta, 1e-12)), 1.0))
    return max(epsilon / penalty, _EPS)


def resolve_ci_threshold_policy(
    *,
    family: Literal["kernel_ci", "categorical_ci"],
    query_type: str,
    estimator: str,
    dp_context: DPContext | Mapping[str, Any] | None = None,
    registry_root: str | Path | None = None,
    alpha: float = 0.05,
    n_bootstrap: int = 299,
    readiness_target: str = "diagnostic",
) -> CITestThresholdPolicy:
    """Resolve CI calibration controls from the threshold registry when present."""

    context = coerce_dp_context(dp_context)
    policy = CITestThresholdPolicy(
        alpha_base=float(alpha),
        mc_bootstrap_B=int(n_bootstrap),
    )
    if registry_root is None:
        return policy

    from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry

    registry = JudgeThresholdRegistry(_Path(registry_root))
    resolved = registry.resolve(
        "ci_tests",
        family=family,
        query_type=query_type,
        estimator=estimator,
        readiness_target=readiness_target,
        dp_mechanism=None if context is None else context.mechanism,
        dp_epsilon=None if context is None else context.epsilon,
        dp_delta=None if context is None else context.delta,
    )
    alpha_base = resolved.threshold_value("alpha_base")
    mc_bootstrap_B = resolved.threshold_value("mc_bootstrap_B")
    min_n_rule_constant = resolved.threshold_value("min_n_rule_constant")
    naive_fpr_bound_rho = resolved.threshold_value("naive_fpr_bound_rho")
    return CITestThresholdPolicy(
        alpha_base=float(alpha_base if alpha_base is not None else alpha),
        mc_bootstrap_B=int(round(mc_bootstrap_B if mc_bootstrap_B is not None else n_bootstrap)),
        min_n_rule_constant=float(
            min_n_rule_constant if min_n_rule_constant is not None else policy.min_n_rule_constant
        ),
        naive_fpr_bound_rho=float(
            naive_fpr_bound_rho if naive_fpr_bound_rho is not None else policy.naive_fpr_bound_rho
        ),
        threshold_scope=dict(resolved.scope),
        threshold_registry_version=resolved.registry_version,
    )


def required_n_chi2(
    dp_context: DPContext,
    *,
    m_cells: int,
    z_strata: int = 1,
    target_power: float = 0.8,
    effect_proxy: float = 0.10,
    min_n_rule_constant: float = 4.0,
    min_expected_count: float = 5.0,
) -> CISampleSizeRequirement:
    """Conservative sample-size rule for categorical CI under additive DP noise."""

    xi = max(effective_privacy_xi(dp_context), _EPS)
    cells = max(int(m_cells), 1)
    strata = max(int(z_strata), 1)
    power_multiplier = 1.0 + 2.0 * max(0.0, float(target_power) - 0.5)
    effect = max(float(effect_proxy), 0.02)
    privacy_term = math.ceil(
        float(min_n_rule_constant) * power_multiplier * cells * strata / (xi**2)
    )
    effect_term = math.ceil(power_multiplier * cells * strata / (effect**2))
    expected_term = math.ceil(float(min_expected_count) * cells * strata)
    return CISampleSizeRequirement(
        family="categorical_ci",
        required_n=max(privacy_term, effect_term, expected_term),
        target_power=float(target_power),
        epsilon=float(dp_context.epsilon),
        delta=float(dp_context.delta),
        effect_proxy=effect,
        method="counts_rule_plus_min_expected_counts",
        notes=[
            "Uses O(m / xi^2) privacy inflation together with minimum expected-count support.",
            "effect_proxy is a proxy departure size for the target power calculation.",
        ],
    )


def required_n_kernel(
    dp_context: DPContext,
    *,
    dims: int,
    rho_star: float = 0.10,
    target_power: float = 0.8,
) -> CISampleSizeRequirement:
    """Sample-size proxy for dpHSIC-style kernel tests."""

    xi = max(effective_privacy_xi(dp_context), _EPS)
    power_multiplier = 1.0 + 2.0 * max(0.0, float(target_power) - 0.5)
    effect = max(float(rho_star), 0.02)
    dim_penalty = max(int(dims), 1)
    sampling_term = math.ceil(power_multiplier * dim_penalty / (effect**2))
    dp_quadratic_term = math.ceil(power_multiplier * dim_penalty / max(effect * xi, _EPS))
    dp_mixed_term = math.ceil(
        (power_multiplier * dim_penalty / max(effect * xi, _EPS)) ** (2.0 / 3.0)
    )
    return CISampleSizeRequirement(
        family="kernel_ci",
        required_n=max(sampling_term, dp_quadratic_term, dp_mixed_term),
        target_power=float(target_power),
        epsilon=float(dp_context.epsilon),
        delta=float(dp_context.delta),
        effect_proxy=effect,
        method="dpHSIC_minimum_separation_proxy",
        notes=[
            "Matches the dpHSIC separation bound structure with 1/(n^2 xi^2) and 1/(n^(3/2) xi) penalties.",
            "rho_star is a proxy minimum detectable dependence level.",
        ],
    )


def calibrate_kernel_ci(
    *,
    observed: float,
    null_distribution: Sequence[float] | np.ndarray,
    n_obs: int,
    alpha: float,
    dp_context: DPContext | Mapping[str, Any] | None,
    threshold_policy: CITestThresholdPolicy,
    dims: int = 1,
    rho_star: float = 0.10,
) -> CITestCalibration:
    """Calibrate a kernel CI test under an optional DP context."""

    null_dist = np.asarray(null_distribution, dtype=float).reshape(-1)
    if null_dist.size == 0:
        raise ValueError("null_distribution must be non-empty")
    alpha_base = float(alpha)
    classical_threshold = float(np.quantile(null_dist, 1.0 - alpha_base))
    null_mean = float(np.mean(null_dist))
    null_std = float(np.std(null_dist))
    context = coerce_dp_context(dp_context)
    sample_requirement: CISampleSizeRequirement | None = None
    fpr_bound: CIFPRInflationBound | None = None
    shift = 0.0
    calibration_mode = "permutation_quantile"

    if context is not None:
        xi = max(effective_privacy_xi(context), _EPS)
        kernel_shift = (1.0 / (max(n_obs, 1) * xi)) + (
            1.0 / (max(n_obs, 1) ** 0.75 * math.sqrt(xi))
        )
        clip_norm = float(context.clip_norm or 1.0)
        shift = min(1.0, clip_norm * kernel_shift)
        calibration_mode = "dp_permutation_quantile"
        sample_requirement = required_n_kernel(
            context,
            dims=max(int(dims), 1),
            rho_star=rho_star,
            target_power=0.80,
        )

    corrected_threshold = float(min(1.0, classical_threshold + shift))
    conservative_p_value = min(
        1.0,
        float(np.mean(null_dist >= max(float(observed) - shift, 0.0)))
        + threshold_policy.naive_fpr_bound_rho,
    )
    if shift > 0.0:
        fpr_bound = _empirical_fpr_inflation_bound(
            null_distribution=null_dist,
            alpha=alpha_base,
            threshold_shift=shift,
            rho_tail=threshold_policy.naive_fpr_bound_rho,
            reference_threshold=classical_threshold,
        )

    return CITestCalibration(
        alpha=alpha_base,
        p_value=conservative_p_value
        if context is not None
        else float(np.mean(null_dist >= observed)),
        critical_statistic_value=corrected_threshold,
        calibration_mode=calibration_mode,
        threshold_policy=threshold_policy,
        sample_size_requirement=sample_requirement,
        naive_fpr_inflation_bound=fpr_bound,
        dp_context_summary=None if context is None else _dp_context_summary(context),
        null_summary={
            "null_mean": null_mean,
            "null_std": null_std,
            "null_threshold_classical": classical_threshold,
            "null_samples": int(null_dist.size),
        },
    )


def calibrate_discrete_ci(
    *,
    tables: Sequence[np.ndarray],
    alpha: float,
    statistic_family: Literal["g2", "chi2"],
    dp_context: DPContext | Mapping[str, Any] | None,
    threshold_policy: CITestThresholdPolicy,
    rng: np.random.Generator | None = None,
) -> tuple[float, dict[str, Any], CITestCalibration]:
    """Calibrate a categorical CI test for conditional or marginal independence."""

    valid_tables = [np.asarray(table, dtype=float) for table in tables if np.asarray(table).size]
    observed, degrees_of_freedom, observed_meta = _aggregate_discrete_statistic(
        valid_tables,
        statistic_family=statistic_family,
    )
    alpha_base = float(alpha)
    if degrees_of_freedom <= 0:
        calibration = CITestCalibration(
            alpha=alpha_base,
            p_value=1.0,
            critical_statistic_value=0.0,
            calibration_mode="degenerate",
            threshold_policy=threshold_policy,
            dp_context_summary=None,
        )
        observed_meta["degenerate"] = True
        return observed, observed_meta, calibration

    context = coerce_dp_context(dp_context)
    cell_count = int(sum(int(table.size) for table in valid_tables))
    n_obs = int(sum(int(round(float(table.sum()))) for table in valid_tables))
    classical_threshold, classical_p_value = _chi_square_reference(
        observed,
        degrees_of_freedom=degrees_of_freedom,
        alpha=alpha_base,
    )

    calibration_mode = "classical_chi2_reference"
    corrected_threshold = classical_threshold
    corrected_p_value = classical_p_value
    sample_requirement: CISampleSizeRequirement | None = None
    fpr_bound: CIFPRInflationBound | None = None

    if context is not None:
        sample_requirement = required_n_chi2(
            context,
            m_cells=cell_count,
            z_strata=len(valid_tables),
            target_power=0.80,
            min_n_rule_constant=threshold_policy.min_n_rule_constant,
        )
        if context.mechanism == "gaussian_counts":
            corrected_threshold, corrected_p_value = _analytic_gaussian_discrete_threshold(
                observed=observed,
                degrees_of_freedom=degrees_of_freedom,
                alpha=alpha_base,
                cell_count=cell_count,
                n_obs=max(n_obs, 1),
                dp_context=context,
            )
            calibration_mode = "analytic_weighted_chi2"
        else:
            mc_rng = rng or np.random.default_rng(0)
            null_dist = _mc_private_discrete_null(
                tables=valid_tables,
                statistic_family=statistic_family,
                n_draws=int(threshold_policy.mc_bootstrap_B),
                dp_context=context,
                rng=mc_rng,
            )
            corrected_threshold = float(np.quantile(null_dist, 1.0 - alpha_base))
            corrected_p_value = float(np.mean(null_dist >= observed))
            calibration_mode = "mc_null_simulation"
        shift = max(corrected_threshold - classical_threshold, 0.0)
        fpr_bound = _chi_square_fpr_inflation_bound(
            degrees_of_freedom=degrees_of_freedom,
            alpha=alpha_base,
            threshold_shift=shift,
            rho_tail=threshold_policy.naive_fpr_bound_rho,
            reference_threshold=classical_threshold,
        )

    observed_meta.update(
        {
            "cell_count": cell_count,
            "n_obs": n_obs,
        }
    )
    calibration = CITestCalibration(
        alpha=alpha_base,
        p_value=corrected_p_value,
        critical_statistic_value=corrected_threshold,
        calibration_mode=calibration_mode,
        threshold_policy=threshold_policy,
        sample_size_requirement=sample_requirement,
        naive_fpr_inflation_bound=fpr_bound,
        dp_context_summary=None if context is None else _dp_context_summary(context),
        null_summary={
            "degrees_of_freedom": degrees_of_freedom,
            "null_threshold_classical": classical_threshold,
        },
    )
    return observed, observed_meta, calibration


def _dp_context_summary(dp_context: DPContext) -> dict[str, Any]:
    return {
        "mechanism": dp_context.mechanism,
        "mechanism_family": dp_context.mechanism_family,
        "epsilon": float(dp_context.epsilon),
        "delta": float(dp_context.delta),
        "effective_xi": effective_privacy_xi(dp_context),
        "clip_norm": None if dp_context.clip_norm is None else float(dp_context.clip_norm),
        "released_statistics": dp_context.released_statistics,
    }


def _empirical_fpr_inflation_bound(
    *,
    null_distribution: np.ndarray,
    alpha: float,
    threshold_shift: float,
    rho_tail: float,
    reference_threshold: float,
) -> CIFPRInflationBound:
    lower = max(float(reference_threshold) - float(threshold_shift), 0.0)
    tail_mass = float(
        np.mean((null_distribution > lower) & (null_distribution <= reference_threshold))
    )
    return CIFPRInflationBound(
        naive_alpha=float(alpha),
        threshold_shift=float(threshold_shift),
        rho_tail=float(rho_tail),
        reject_probability_upper_bound=min(1.0, float(alpha) + tail_mass + float(rho_tail)),
        reference_threshold=float(reference_threshold),
        tail_mass=tail_mass,
    )


def _chi_square_fpr_inflation_bound(
    *,
    degrees_of_freedom: int,
    alpha: float,
    threshold_shift: float,
    rho_tail: float,
    reference_threshold: float,
) -> CIFPRInflationBound:
    from scipy.stats import chi2

    lower = max(float(reference_threshold) - float(threshold_shift), 0.0)
    tail_mass = float(
        chi2.cdf(float(reference_threshold), int(degrees_of_freedom))
        - chi2.cdf(lower, int(degrees_of_freedom))
    )
    return CIFPRInflationBound(
        naive_alpha=float(alpha),
        threshold_shift=float(threshold_shift),
        rho_tail=float(rho_tail),
        reject_probability_upper_bound=min(1.0, float(alpha) + tail_mass + float(rho_tail)),
        reference_threshold=float(reference_threshold),
        tail_mass=tail_mass,
    )


def _analytic_gaussian_discrete_threshold(
    *,
    observed: float,
    degrees_of_freedom: int,
    alpha: float,
    cell_count: int,
    n_obs: int,
    dp_context: DPContext,
) -> tuple[float, float]:
    from scipy.stats import chi2

    sigma = classical_gaussian_sigma(
        epsilon=float(dp_context.epsilon),
        delta=max(float(dp_context.delta), 1e-12),
        l2_sensitivity=float(dp_context.l2_sensitivity or 1.0),
    )
    avg_expected = max(float(n_obs) / max(int(cell_count), 1), 1.0)
    lambda_noise = max(int(cell_count), 1) * (sigma**2) / avg_expected
    mean = float(degrees_of_freedom) + lambda_noise
    variance = max(
        2.0 * float(degrees_of_freedom)
        + 4.0 * lambda_noise
        + (2.0 * lambda_noise**2 / max(int(cell_count), 1)),
        _EPS,
    )
    effective_dof = max((2.0 * mean**2) / variance, _EPS)
    scale = max(variance / (2.0 * mean), _EPS)
    threshold = float(scale * chi2.ppf(1.0 - float(alpha), effective_dof))
    p_value = float(chi2.sf(float(observed) / scale, effective_dof))
    return threshold, p_value


def _chi_square_reference(
    observed: float,
    *,
    degrees_of_freedom: int,
    alpha: float,
) -> tuple[float, float]:
    from scipy.stats import chi2

    threshold = float(chi2.ppf(1.0 - float(alpha), int(degrees_of_freedom)))
    p_value = float(chi2.sf(float(observed), int(degrees_of_freedom)))
    return threshold, p_value


def _aggregate_discrete_statistic(
    tables: Sequence[np.ndarray],
    *,
    statistic_family: Literal["g2", "chi2"],
) -> tuple[float, int, dict[str, Any]]:
    total_statistic = 0.0
    total_dof = 0
    valid_strata = 0
    skipped_strata = 0
    for table in tables:
        statistic, dof = _discrete_table_statistic(table, statistic_family=statistic_family)
        if dof <= 0:
            skipped_strata += 1
            continue
        total_statistic += statistic
        total_dof += dof
        valid_strata += 1
    return (
        total_statistic,
        total_dof,
        {
            "degrees_of_freedom": total_dof,
            "valid_strata": valid_strata,
            "skipped_strata": skipped_strata,
            "degenerate": total_dof <= 0,
        },
    )


def _discrete_table_statistic(
    table: np.ndarray,
    *,
    statistic_family: Literal["g2", "chi2"],
) -> tuple[float, int]:
    obs = np.asarray(table, dtype=float)
    if obs.ndim != 2 or obs.shape[0] < 2 or obs.shape[1] < 2:
        return 0.0, 0
    if float(obs.sum()) <= 0.0:
        return 0.0, 0
    expected = _expected_independence_table(obs)
    valid = expected > _EPS
    if not np.any(valid):
        return 0.0, 0
    if statistic_family == "g2":
        ratio = np.ones_like(obs)
        positive = valid & (obs > 0.0)
        ratio[positive] = obs[positive] / expected[positive]
        statistic = 2.0 * float(np.sum(obs[positive] * np.log(ratio[positive])))
    else:
        statistic = float(np.sum(((obs[valid] - expected[valid]) ** 2) / expected[valid]))
    return statistic, max((obs.shape[0] - 1) * (obs.shape[1] - 1), 0)


def _expected_independence_table(table: np.ndarray) -> np.ndarray:
    row_totals = np.sum(table, axis=1, keepdims=True)
    col_totals = np.sum(table, axis=0, keepdims=True)
    grand_total = float(np.sum(table))
    if grand_total <= 0.0:
        return np.zeros_like(table, dtype=float)
    return (row_totals @ col_totals) / grand_total


def _mc_private_discrete_null(
    *,
    tables: Sequence[np.ndarray],
    statistic_family: Literal["g2", "chi2"],
    n_draws: int,
    dp_context: DPContext,
    rng: np.random.Generator,
) -> np.ndarray:
    draws: list[float] = []
    for _ in range(max(int(n_draws), 1)):
        simulated: list[np.ndarray] = []
        for table in tables:
            table = np.asarray(table, dtype=float)
            n_obs = max(int(round(float(table.sum()))), 1)
            probs = _null_joint_probabilities(table)
            sampled = rng.multinomial(n_obs, probs.ravel()).reshape(table.shape).astype(float)
            private_table = _apply_private_count_noise(sampled, dp_context=dp_context, rng=rng)
            simulated.append(private_table)
        statistic, _, _ = _aggregate_discrete_statistic(
            simulated,
            statistic_family=statistic_family,
        )
        draws.append(float(statistic))
    return np.asarray(draws, dtype=float)


def _null_joint_probabilities(table: np.ndarray) -> np.ndarray:
    expected = _expected_independence_table(np.asarray(table, dtype=float))
    total = float(np.sum(expected))
    if total <= 0.0:
        return np.full_like(expected, 1.0 / max(expected.size, 1), dtype=float)
    return expected / total


def _apply_private_count_noise(
    table: np.ndarray,
    *,
    dp_context: DPContext,
    rng: np.random.Generator,
) -> np.ndarray:
    obs = np.asarray(table, dtype=float)
    if dp_context.mechanism == "laplace_counts":
        scale = float(dp_context.l1_sensitivity or 1.0) / float(dp_context.epsilon)
        noisy = obs + rng.laplace(loc=0.0, scale=scale, size=obs.shape)
    elif dp_context.mechanism == "gaussian_counts":
        scale = classical_gaussian_sigma(
            epsilon=float(dp_context.epsilon),
            delta=max(float(dp_context.delta), 1e-12),
            l2_sensitivity=float(dp_context.l2_sensitivity or 1.0),
        )
        noisy = obs + rng.normal(loc=0.0, scale=scale, size=obs.shape)
    else:
        noisy = obs
    return np.clip(noisy, 0.0, None)
