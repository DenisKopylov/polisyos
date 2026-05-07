"""Uncertainty estimators for Sobol and Morris sensitivity outputs."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

_NORMAL = NormalDist()
_EPS = 1e-12


class SensitivityUncertaintyConfig(BaseModel):
    """Configuration for sensitivity-analysis confidence intervals and rank uncertainty."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    level: float = Field(default=0.95, gt=0.0, lt=1.0)
    method: str = "auto"
    n_resamples: int = Field(default=1999, ge=10, le=100_000)
    interval_types: list[str] = Field(
        default_factory=lambda: ["marginal", "simultaneous"],
    )
    rank_uncertainty: bool = True
    random_seed: int | None = None
    uncertainty_scope: str = Field(
        default="sampling_only",
        pattern=r"^(sampling_only|sampling_plus_simulator_noise|surrogate_only|sampling_plus_surrogate)$",
    )
    top_k: list[int] = Field(default_factory=lambda: [1, 3])
    simulated_rank_draws: int = Field(default=1999, ge=100, le=100_000)
    studentized_inner_resamples: int = Field(default=99, ge=10, le=10_000)


class ResolvedSensitivityUncertaintyMethod(BaseModel):
    """Decision-tree result for sensitivity uncertainty method selection."""

    model_config = ConfigDict(extra="forbid")

    method: str
    ci_status: str = "ok"
    warnings: list[str] = Field(default_factory=list)


class SensitivityInterval(BaseModel):
    """One confidence interval for a reported sensitivity index."""

    model_config = ConfigDict(extra="forbid")

    level: float
    low: float
    high: float
    raw_low: float
    raw_high: float
    method: str
    simultaneous: bool = False
    n_resamples: int
    coverage_profile_id: str | None = None


class SensitivityDiagnostics(BaseModel):
    """Diagnostics describing how an interval should be interpreted."""

    model_config = ConfigDict(extra="forbid")

    bootstrap_out_of_bounds_rate: float = 0.0
    degenerate: bool = False
    ci_status: str = "ok"
    uncertainty_scope: str = "sampling_only"
    warnings: list[str] = Field(default_factory=list)


class SensitivityIndexUncertainty(BaseModel):
    """Point estimate, standard error, and CI for one parameter/index pair."""

    model_config = ConfigDict(extra="forbid")

    parameter: str
    index: str
    estimate: float
    standard_error: float | None = None
    ci: SensitivityInterval | None = None
    simultaneous_ci: SensitivityInterval | None = None
    diagnostics: SensitivityDiagnostics = Field(default_factory=SensitivityDiagnostics)


class JointSensitivityUncertainty(BaseModel):
    """Joint uncertainty artifacts derived from the same resampling distribution."""

    model_config = ConfigDict(extra="forbid")

    covariance_matrix: list[list[float]] | None = None
    rank_probabilities: dict[str, dict[str, float]] = Field(default_factory=dict)
    top_k_probabilities: dict[str, dict[str, float]] = Field(default_factory=dict)
    pairwise_dominance: dict[str, float] = Field(default_factory=dict)
    difference_ci: dict[str, SensitivityInterval] = Field(default_factory=dict)


class SensitivityMethodMetadata(BaseModel):
    """Metadata for the uncertainty analyzer and calibration layer."""

    model_config = ConfigDict(extra="forbid")

    analyzer_version: str = "sensitivity-ci-0.1.0"
    benchmark_profile_version: str = "2026-04"
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class SensitivityUncertaintyBundle(BaseModel):
    """Catalog-ready sensitivity uncertainty payload."""

    model_config = ConfigDict(extra="forbid")

    sensitivity_results: list[SensitivityIndexUncertainty] = Field(default_factory=list)
    joint_uncertainty: JointSensitivityUncertainty = Field(
        default_factory=JointSensitivityUncertainty,
    )
    method_metadata: SensitivityMethodMetadata = Field(default_factory=SensitivityMethodMetadata)


@dataclass(frozen=True)
class SobolRowBlockData:
    """Pick-freeze output blocks with one row per shared Monte Carlo base draw."""

    y_a: np.ndarray
    y_b: np.ndarray
    y_ab: np.ndarray
    parameter_names: tuple[str, ...]
    y_ba: np.ndarray | None = None


def resolve_sensitivity_uncertainty_method(
    analysis_kind: str,
    *,
    sampler: str = "iid_mc",
    rqmc_replicates: int = 0,
    surrogate_family: str | None = None,
    large_n: bool = False,
) -> ResolvedSensitivityUncertaintyMethod:
    """Resolve the default CI method from the memo's public API policy."""

    kind = analysis_kind.lower()
    sampler_key = sampler.lower()
    if surrogate_family is not None:
        return ResolvedSensitivityUncertaintyMethod(method="surrogate_design_bootstrap")
    if kind == "sobol" and sampler_key in {"iid_mc", "saltelli", "monte_carlo"}:
        return ResolvedSensitivityUncertaintyMethod(
            method="asymptotic_delta" if large_n else "paired_bca_bootstrap"
        )
    if kind == "sobol" and sampler_key in {"rqmc", "scrambled_sobol", "randomized_qmc"}:
        if rqmc_replicates >= 8:
            return ResolvedSensitivityUncertaintyMethod(method="replicate_t_interval")
        if rqmc_replicates <= 1:
            return ResolvedSensitivityUncertaintyMethod(
                method="none",
                ci_status="not_calibrated_single_qmc",
                warnings=["interval not calibrated; rerun with independent scrambles"],
            )
        return ResolvedSensitivityUncertaintyMethod(
            method="replicate_t_interval",
            ci_status="not_calibrated_few_qmc_replicates",
            warnings=["fewer than 8 independent QMC replicates"],
        )
    if kind == "morris":
        return ResolvedSensitivityUncertaintyMethod(method="trajectory_bca_bootstrap")
    return ResolvedSensitivityUncertaintyMethod(
        method="asymptotic_delta",
        ci_status="asymptotic_with_warning",
        warnings=["no calibrated method profile matched this sensitivity analysis"],
    )


class SobolQMCMetadata(BaseModel):
    """QMC provenance for Sobol sensitivity data."""

    model_config = ConfigDict(extra="forbid")

    used: bool = False
    scramble_id: str | None = None
    replicate_id: str | None = None
    n_replicates: int | None = None


class SobolStoragePayload(BaseModel):
    """JSON-serializable row-level Sobol data needed for calibrated uncertainty."""

    model_config = ConfigDict(extra="forbid")

    sampler: str = "saltelli"
    estimator: str = "saltelli_saltelli_first_jansen_total"
    n: int
    d: int
    parameter_names: list[str]
    y_a: list[float]
    y_b: list[float]
    y_ab: list[list[float]]
    y_ba: list[list[float]] | None = None
    row_block_id: str | None = None
    rng_seed: int | None = None
    qmc: SobolQMCMetadata = Field(default_factory=SobolQMCMetadata)
    moment_contributions_ref: str | None = None


class MorrisStoragePayload(BaseModel):
    """JSON-serializable Morris trajectory data needed for calibrated uncertainty."""

    model_config = ConfigDict(extra="forbid")

    method: str = "morris"
    r_trajectories: int
    num_levels: int | None = None
    delta: float | None = None
    optimized_trajectories: bool = False
    parameter_names: list[str]
    elementary_effects: list[list[float]]
    trajectory_ids: list[str] = Field(default_factory=list)
    scaled: bool = False


def sobol_blocks_from_salib_outputs(
    outputs: Sequence[float] | np.ndarray,
    parameter_names: Sequence[str],
    *,
    calc_second_order: bool = True,
) -> SobolRowBlockData:
    """Recover Sobol row blocks from SALib Saltelli/Sobol output ordering."""

    names = tuple(parameter_names)
    d = len(names)
    if d < 1:
        raise ValueError("parameter_names must contain at least one parameter")

    y = _as_1d_float("outputs", outputs)
    step = (2 * d + 2) if calc_second_order else (d + 2)
    if y.size % step != 0:
        if calc_second_order:
            return sobol_blocks_from_salib_outputs(
                y,
                names,
                calc_second_order=False,
            )
        raise ValueError(
            "outputs length is not compatible with a Sobol row-block design "
            f"(n={y.size}, d={d}, step={step})"
        )

    n = y.size // step
    y_ab = np.empty((n, d), dtype=float)
    y_ba = np.empty((n, d), dtype=float) if calc_second_order else None
    for j in range(d):
        y_ab[:, j] = y[(j + 1) : y.size : step]
        if y_ba is not None:
            y_ba[:, j] = y[(j + 1 + d) : y.size : step]

    return SobolRowBlockData(
        y_a=y[0:y.size:step],
        y_b=y[(step - 1) : y.size : step],
        y_ab=y_ab,
        y_ba=y_ba,
        parameter_names=names,
    )


def analyze_sobol_paired_bootstrap(
    blocks: SobolRowBlockData,
    config: SensitivityUncertaintyConfig | None = None,
) -> SensitivityUncertaintyBundle:
    """Compute marginal, simultaneous, and rank uncertainty by resampling Sobol row blocks."""

    cfg = config or SensitivityUncertaintyConfig(enabled=True)
    method = _resolve_bootstrap_method(
        cfg.method,
        default="paired_bca_bootstrap",
        aliases={"paired_row_bootstrap", "paired_bootstrap"},
    )
    normalized = _normalize_sobol_blocks(blocks)
    n = normalized.y_a.size
    if n < 2:
        raise ValueError("Sobol uncertainty requires at least two row blocks")

    labels, point = _sobol_estimates(normalized)
    rng = np.random.default_rng(cfg.random_seed)
    bootstrap = np.empty((cfg.n_resamples, point.size), dtype=float)
    bootstrap_se = (
        np.empty((cfg.n_resamples, point.size), dtype=float)
        if method.endswith("_studentized_bootstrap")
        else None
    )
    for b in range(cfg.n_resamples):
        idx = rng.integers(0, n, size=n)
        sampled = _take_sobol_rows(normalized, idx)
        _, bootstrap[b] = _sobol_estimates(sampled)
        if bootstrap_se is not None:
            bootstrap_se[b] = _sobol_inner_bootstrap_se(
                sampled,
                cfg.studentized_inner_resamples,
                rng,
            )

    jackknife = _jackknife_sobol(normalized) if method.endswith("_bca_bootstrap") else None
    covariance = _covariance_matrix(bootstrap)
    simultaneous = (
        _simultaneous_intervals(point, bootstrap, cfg.level, method, cfg.n_resamples)
        if "simultaneous" in cfg.interval_types
        else None
    )
    results = _index_results_from_bootstrap(
        labels=labels,
        point=point,
        bootstrap=bootstrap,
        bootstrap_se=bootstrap_se,
        jackknife=jackknife,
        config=cfg,
        method=method,
        simultaneous=simultaneous,
        clip_bounds=(0.0, 1.0),
        nonnegative_indices={"S1", "ST", "S2"},
        coverage_profile_id=_coverage_profile_id("sobol_iid_saltelli", method),
    )
    rank_metric = _bootstrap_metric_matrix(labels, bootstrap, normalized.parameter_names, "ST")
    if rank_metric is None:
        rank_metric = _bootstrap_metric_matrix(labels, bootstrap, normalized.parameter_names, "S1")

    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=_joint_uncertainty(
            normalized.parameter_names,
            rank_metric,
            cfg,
            method=method,
            covariance_matrix=covariance,
        ),
        method_metadata=SensitivityMethodMetadata(),
    )


def analyze_sobol_asymptotic_delta(
    blocks: SobolRowBlockData,
    config: SensitivityUncertaintyConfig | None = None,
) -> SensitivityUncertaintyBundle:
    """Compute Sobol large-sample CIs from an empirical influence-function covariance."""

    cfg = config or SensitivityUncertaintyConfig(enabled=True, method="asymptotic")
    normalized = _normalize_sobol_blocks(blocks)
    labels, point = _sobol_estimates(normalized)
    jackknife = _jackknife_sobol(normalized)
    covariance = _jackknife_covariance(jackknife) if jackknife is not None else None
    if covariance is None:
        covariance = np.zeros((point.size, point.size), dtype=float)

    simulated = _simulate_normal_draws(
        point,
        covariance,
        cfg.simulated_rank_draws,
        seed=cfg.random_seed,
    )
    simultaneous = (
        _simultaneous_intervals(point, simulated, cfg.level, "asymptotic_delta", cfg.simulated_rank_draws)
        if "simultaneous" in cfg.interval_types and simulated.size
        else None
    )
    results = _index_results_from_covariance(
        labels=labels,
        point=point,
        covariance=covariance,
        config=cfg,
        method="asymptotic_delta",
        simultaneous=simultaneous,
        clip_bounds=(0.0, 1.0),
        coverage_profile_id=_coverage_profile_id("sobol_iid_saltelli", "asymptotic_delta"),
    )
    rank_metric = _bootstrap_metric_matrix(labels, simulated, normalized.parameter_names, "ST")
    if rank_metric is None:
        rank_metric = _bootstrap_metric_matrix(labels, simulated, normalized.parameter_names, "S1")

    warnings = []
    if normalized.y_a.size < 30:
        warnings.append("asymptotic_precision_low")
        for item in results:
            item.diagnostics.warnings.append("asymptotic_precision_low")
            if item.diagnostics.ci_status == "ok":
                item.diagnostics.ci_status = "asymptotic_precision_low"

    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=_joint_uncertainty(
            normalized.parameter_names,
            rank_metric,
            cfg,
            method="asymptotic_delta",
            covariance_matrix=covariance.tolist(),
        ),
        method_metadata=SensitivityMethodMetadata(warnings=warnings),
    )


def sobol_storage_from_blocks(
    blocks: SobolRowBlockData,
    *,
    sampler: str = "saltelli",
    estimator: str = "saltelli_saltelli_first_jansen_total",
    row_block_id: str | None = None,
    rng_seed: int | None = None,
    qmc: SobolQMCMetadata | None = None,
) -> SobolStoragePayload:
    """Create the retained Sobol row-block payload required by the catalog."""

    normalized = _normalize_sobol_blocks(blocks)
    return SobolStoragePayload(
        sampler=sampler,
        estimator=estimator,
        n=int(normalized.y_a.size),
        d=len(normalized.parameter_names),
        parameter_names=list(normalized.parameter_names),
        y_a=normalized.y_a.astype(float).tolist(),
        y_b=normalized.y_b.astype(float).tolist(),
        y_ab=normalized.y_ab.astype(float).tolist(),
        y_ba=normalized.y_ba.astype(float).tolist() if normalized.y_ba is not None else None,
        row_block_id=row_block_id,
        rng_seed=rng_seed,
        qmc=qmc or SobolQMCMetadata(),
    )


def sobol_blocks_from_storage(payload: SobolStoragePayload) -> SobolRowBlockData:
    """Restore Sobol row blocks from a retained catalog storage payload."""

    if payload.d != len(payload.parameter_names):
        raise ValueError("Sobol payload d does not match parameter_names")
    if payload.n != len(payload.y_a) or payload.n != len(payload.y_b):
        raise ValueError("Sobol payload n does not match y_a/y_b lengths")
    return _normalize_sobol_blocks(
        SobolRowBlockData(
            y_a=np.asarray(payload.y_a, dtype=float),
            y_b=np.asarray(payload.y_b, dtype=float),
            y_ab=np.asarray(payload.y_ab, dtype=float),
            y_ba=np.asarray(payload.y_ba, dtype=float) if payload.y_ba is not None else None,
            parameter_names=tuple(payload.parameter_names),
        )
    )


def morris_elementary_effects_from_samples(
    samples: np.ndarray,
    outputs: np.ndarray,
    parameter_names: Sequence[str],
) -> np.ndarray:
    """Infer Morris elementary effects from trajectory-ordered samples and outputs."""

    x = np.asarray(samples, dtype=float)
    y = _as_1d_float("outputs", outputs)
    d = len(tuple(parameter_names))
    if x.ndim != 2:
        raise ValueError("samples must be a 2D array")
    if x.shape[0] != y.size:
        raise ValueError("samples and outputs must have the same row count")
    if x.shape[1] != d:
        raise ValueError("samples column count must match parameter_names")
    trajectory_size = d + 1
    if y.size % trajectory_size != 0:
        raise ValueError(
            "samples do not align to Morris trajectories "
            f"(n={y.size}, d={d}, trajectory_size={trajectory_size})"
        )

    r = y.size // trajectory_size
    x_traj = x.reshape(r, trajectory_size, d)
    y_traj = y.reshape(r, trajectory_size)
    effects = np.full((r, d), np.nan, dtype=float)
    for t in range(r):
        for step in range(d):
            delta_x = x_traj[t, step + 1] - x_traj[t, step]
            changed = np.flatnonzero(np.abs(delta_x) > _EPS)
            if changed.size == 0:
                continue
            factor_idx = int(changed[np.argmax(np.abs(delta_x[changed]))])
            effects[t, factor_idx] = (y_traj[t, step + 1] - y_traj[t, step]) / delta_x[factor_idx]

    if np.any(~np.isfinite(effects)):
        raise ValueError("could not infer a complete elementary-effect matrix from samples")
    return effects


def analyze_morris_trajectory_bootstrap(
    elementary_effects: np.ndarray,
    parameter_names: Sequence[str],
    config: SensitivityUncertaintyConfig | None = None,
) -> SensitivityUncertaintyBundle:
    """Compute Morris CI and rank uncertainty by resampling whole trajectories."""

    cfg = config or SensitivityUncertaintyConfig(enabled=True)
    method = _resolve_bootstrap_method(
        cfg.method,
        default="trajectory_bca_bootstrap",
        aliases={"trajectory_bootstrap", "morris_bootstrap"},
    )
    names = tuple(parameter_names)
    ee = _as_2d_float("elementary_effects", elementary_effects)
    if ee.shape[1] != len(names):
        raise ValueError("elementary_effects column count must match parameter_names")
    if ee.shape[0] < 2:
        raise ValueError("Morris uncertainty requires at least two trajectories")

    labels, point = _morris_estimates(ee, names)
    rng = np.random.default_rng(cfg.random_seed)
    bootstrap = np.empty((cfg.n_resamples, point.size), dtype=float)
    bootstrap_se = (
        np.empty((cfg.n_resamples, point.size), dtype=float)
        if method.endswith("_studentized_bootstrap")
        else None
    )
    for b in range(cfg.n_resamples):
        idx = rng.integers(0, ee.shape[0], size=ee.shape[0])
        sampled = ee[idx]
        _, bootstrap[b] = _morris_estimates(sampled, names)
        if bootstrap_se is not None:
            bootstrap_se[b] = _morris_inner_bootstrap_se(
                sampled,
                names,
                cfg.studentized_inner_resamples,
                rng,
            )

    jackknife = _jackknife_morris(ee, names) if method.endswith("_bca_bootstrap") else None
    simultaneous = (
        _simultaneous_intervals(point, bootstrap, cfg.level, method, cfg.n_resamples)
        if "simultaneous" in cfg.interval_types
        else None
    )
    results = _index_results_from_bootstrap(
        labels=labels,
        point=point,
        bootstrap=bootstrap,
        bootstrap_se=bootstrap_se,
        jackknife=jackknife,
        config=cfg,
        method=method,
        simultaneous=simultaneous,
        clip_bounds_by_index={"mu_star": (0.0, math.inf), "sigma": (0.0, math.inf)},
        nonnegative_indices={"mu_star", "sigma"},
        coverage_profile_id=_coverage_profile_id("morris_trajectory", method),
    )

    warnings: list[str] = []
    if ee.shape[0] < 20:
        warnings.append("screening_precision_low")
        for item in results:
            item.diagnostics.warnings.append("screening_precision_low")
            if item.diagnostics.ci_status == "ok":
                item.diagnostics.ci_status = "screening_precision_low"

    rank_metric = _bootstrap_metric_matrix(labels, bootstrap, names, "mu_star")
    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=_joint_uncertainty(
            names,
            rank_metric,
            cfg,
            method=method,
            covariance_matrix=_covariance_matrix(bootstrap),
        ),
        method_metadata=SensitivityMethodMetadata(warnings=warnings),
    )


def morris_storage_from_elementary_effects(
    elementary_effects: np.ndarray,
    parameter_names: Sequence[str],
    *,
    num_levels: int | None = None,
    delta: float | None = None,
    optimized_trajectories: bool = False,
    trajectory_ids: Sequence[str] | None = None,
    scaled: bool = False,
) -> MorrisStoragePayload:
    """Create the retained Morris trajectory payload required by the catalog."""

    names = list(parameter_names)
    ee = _as_2d_float("elementary_effects", elementary_effects)
    if ee.shape[1] != len(names):
        raise ValueError("elementary_effects column count must match parameter_names")
    ids = list(trajectory_ids) if trajectory_ids is not None else [f"t{idx + 1}" for idx in range(ee.shape[0])]
    if len(ids) != ee.shape[0]:
        raise ValueError("trajectory_ids length must match elementary_effects row count")
    return MorrisStoragePayload(
        r_trajectories=int(ee.shape[0]),
        num_levels=num_levels,
        delta=delta,
        optimized_trajectories=optimized_trajectories,
        parameter_names=names,
        elementary_effects=ee.astype(float).tolist(),
        trajectory_ids=ids,
        scaled=scaled,
    )


def morris_elementary_effects_from_storage(payload: MorrisStoragePayload) -> np.ndarray:
    """Restore Morris elementary effects from a retained catalog storage payload."""

    ee = _as_2d_float("elementary_effects", payload.elementary_effects)
    if ee.shape != (payload.r_trajectories, len(payload.parameter_names)):
        raise ValueError("Morris payload dimensions do not match metadata")
    return ee


def morris_analytic_intervals(
    elementary_effects: np.ndarray,
    parameter_names: Sequence[str],
    *,
    level: float = 0.95,
    n_resamples: int = 999,
    random_seed: int | None = None,
) -> dict[str, SensitivityInterval]:
    """Quick t intervals for Morris ``mu`` and ``mu_star`` plus log-scale sigma intervals."""

    names = tuple(parameter_names)
    ee = _as_2d_float("elementary_effects", elementary_effects)
    if ee.shape[1] != len(names):
        raise ValueError("elementary_effects column count must match parameter_names")
    if ee.shape[0] < 2:
        raise ValueError("analytic Morris intervals require at least two trajectories")

    r = ee.shape[0]
    crit = _t_critical(level, r - 1)
    rng = np.random.default_rng(random_seed)
    intervals: dict[str, SensitivityInterval] = {}
    for idx, name in enumerate(names):
        effects = ee[:, idx]
        abs_effects = np.abs(effects)
        mu = float(np.mean(effects))
        mu_star = float(np.mean(abs_effects))
        sigma = float(np.std(effects, ddof=1))
        mu_se = float(np.std(effects, ddof=1) / math.sqrt(r))
        mu_star_se = float(np.std(abs_effects, ddof=1) / math.sqrt(r))

        intervals[f"{name}:mu"] = _plain_interval(
            mu,
            crit * mu_se,
            level,
            "morris_analytic_t",
        )
        intervals[f"{name}:mu_star"] = _plain_interval(
            mu_star,
            crit * mu_star_se,
            level,
            "morris_analytic_t",
            clip_low=0.0,
        )

        sigma_boot = _sigma_bootstrap_log(effects, n_resamples, rng)
        if sigma_boot.size:
            low, high = np.quantile(sigma_boot, [(1.0 - level) / 2.0, 1.0 - (1.0 - level) / 2.0])
            raw_low = float(math.exp(low) - _EPS)
            raw_high = float(math.exp(high) - _EPS)
        else:
            raw_low = raw_high = sigma
        intervals[f"{name}:sigma"] = SensitivityInterval(
            level=level,
            low=max(0.0, raw_low),
            high=max(0.0, raw_high),
            raw_low=raw_low,
            raw_high=raw_high,
            method="morris_log_sigma_bootstrap",
            simultaneous=False,
            n_resamples=n_resamples,
        )
    return intervals


def analyze_rqmc_replicate_ci(
    replicate_estimates: np.ndarray,
    parameter_names: Sequence[str],
    *,
    index: str = "ST",
    config: SensitivityUncertaintyConfig | None = None,
) -> SensitivityUncertaintyBundle:
    """Compute replicate-level t intervals for independently randomized QMC estimates."""

    cfg = config or SensitivityUncertaintyConfig(enabled=True, method="replicate_t_interval")
    method = "replicate_t_interval"
    names = tuple(parameter_names)
    estimates = _as_2d_float("replicate_estimates", replicate_estimates)
    if estimates.shape[1] != len(names):
        raise ValueError("replicate_estimates column count must match parameter_names")
    if estimates.shape[0] < 2:
        raise ValueError("replicate-level CI requires at least two independent replicates")

    r = estimates.shape[0]
    point = np.mean(estimates, axis=0)
    se = np.std(estimates, axis=0, ddof=1) / math.sqrt(r)
    crit = _t_critical(cfg.level, r - 1)
    warnings = [] if r >= 8 else ["not_calibrated_few_qmc_replicates"]

    rng = np.random.default_rng(cfg.random_seed)
    boot_means = np.empty((cfg.n_resamples, len(names)), dtype=float)
    for b in range(cfg.n_resamples):
        boot_idx = rng.integers(0, r, size=r)
        boot_means[b] = np.mean(estimates[boot_idx], axis=0)
    simultaneous = (
        _simultaneous_intervals(point, boot_means, cfg.level, method, cfg.n_resamples)
        if "simultaneous" in cfg.interval_types
        else None
    )

    results: list[SensitivityIndexUncertainty] = []
    for idx, name in enumerate(names):
        raw_low = float(point[idx] - crit * se[idx])
        raw_high = float(point[idx] + crit * se[idx])
        ci = SensitivityInterval(
            level=cfg.level,
            low=max(0.0, min(1.0, raw_low)),
            high=max(0.0, min(1.0, raw_high)),
            raw_low=raw_low,
            raw_high=raw_high,
            method=method,
            simultaneous=False,
            n_resamples=r,
            coverage_profile_id=_coverage_profile_id("sobol_rqmc", method),
        )
        sim_ci = None
        if simultaneous is not None:
            sim_low, sim_high = simultaneous
            raw_sim_low = float(sim_low[idx])
            raw_sim_high = float(sim_high[idx])
            sim_ci = SensitivityInterval(
                level=cfg.level,
                low=max(0.0, min(1.0, raw_sim_low)),
                high=max(0.0, min(1.0, raw_sim_high)),
                raw_low=raw_sim_low,
                raw_high=raw_sim_high,
                method=f"{method}_max_t",
                simultaneous=True,
                n_resamples=cfg.n_resamples,
                coverage_profile_id=_coverage_profile_id("sobol_rqmc", method),
            )
        status = "ok" if r >= 8 else "not_calibrated_few_qmc_replicates"
        results.append(
            SensitivityIndexUncertainty(
                parameter=name,
                index=index,
                estimate=float(point[idx]),
                standard_error=float(se[idx]),
                ci=ci,
                simultaneous_ci=sim_ci,
                diagnostics=SensitivityDiagnostics(
                    bootstrap_out_of_bounds_rate=float(
                        np.mean((estimates[:, idx] < 0.0) | (estimates[:, idx] > 1.0))
                    ),
                    ci_status=status,
                    uncertainty_scope=cfg.uncertainty_scope,
                    warnings=list(warnings),
                ),
            )
        )

    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=_joint_uncertainty(
            names,
            boot_means,
            cfg,
            method=method,
            covariance_matrix=_covariance_matrix(boot_means),
        ),
        method_metadata=SensitivityMethodMetadata(warnings=warnings),
    )


def analyze_hierarchical_replicate_bootstrap(
    replicate_estimates: np.ndarray,
    parameter_names: Sequence[str],
    *,
    index: str = "ST",
    config: SensitivityUncertaintyConfig | None = None,
) -> SensitivityUncertaintyBundle:
    """Hierarchical bootstrap over input-sampling blocks and simulator-noise replicates."""

    cfg = config or SensitivityUncertaintyConfig(
        enabled=True,
        method="hierarchical_bootstrap",
        uncertainty_scope="sampling_plus_simulator_noise",
    )
    if cfg.uncertainty_scope == "sampling_only":
        cfg = cfg.model_copy(update={"uncertainty_scope": "sampling_plus_simulator_noise"})
    names = tuple(parameter_names)
    estimates = np.asarray(replicate_estimates, dtype=float)
    if estimates.ndim != 3:
        raise ValueError("replicate_estimates must have shape (n_blocks, n_replicates, n_parameters)")
    if estimates.shape[2] != len(names):
        raise ValueError("replicate_estimates parameter dimension must match parameter_names")
    if estimates.shape[0] < 2 or estimates.shape[1] < 1:
        raise ValueError("hierarchical bootstrap requires at least two blocks and one replicate")
    if not np.all(np.isfinite(estimates)):
        raise ValueError("replicate_estimates must contain only finite values")

    point = np.mean(estimates, axis=(0, 1))
    labels = [(index, name) for name in names]
    rng = np.random.default_rng(cfg.random_seed)
    bootstrap = np.empty((cfg.n_resamples, len(names)), dtype=float)
    n_blocks, n_reps, _ = estimates.shape
    for b in range(cfg.n_resamples):
        block_idx = rng.integers(0, n_blocks, size=n_blocks)
        rep_idx = rng.integers(0, n_reps, size=(n_blocks, n_reps))
        sampled = estimates[block_idx[:, None], rep_idx]
        bootstrap[b] = np.mean(sampled, axis=(0, 1))

    simultaneous = (
        _simultaneous_intervals(point, bootstrap, cfg.level, "hierarchical_bootstrap", cfg.n_resamples)
        if "simultaneous" in cfg.interval_types
        else None
    )
    results = _index_results_from_bootstrap(
        labels=labels,
        point=point,
        bootstrap=bootstrap,
        bootstrap_se=None,
        jackknife=None,
        config=cfg,
        method="hierarchical_bootstrap",
        simultaneous=simultaneous,
        clip_bounds=(0.0, 1.0),
        nonnegative_indices={index},
        coverage_profile_id=_coverage_profile_id("stochastic_simulator", "hierarchical_bootstrap"),
    )
    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=_joint_uncertainty(
            names,
            bootstrap,
            cfg,
            method="hierarchical_bootstrap",
            covariance_matrix=_covariance_matrix(bootstrap),
        ),
        method_metadata=SensitivityMethodMetadata(
            metadata={
                "outer_blocks": int(n_blocks),
                "simulator_replicates": int(n_reps),
                "uncertainty_scope": cfg.uncertainty_scope,
            }
        ),
    )


def analyze_single_qmc_warning(
    estimates: Mapping[str, float] | Sequence[float] | np.ndarray,
    parameter_names: Sequence[str],
    *,
    index: str = "ST",
    config: SensitivityUncertaintyConfig | None = None,
) -> SensitivityUncertaintyBundle:
    """Return an explicit no-calibrated-CI bundle for a single deterministic QMC run."""

    cfg = config or SensitivityUncertaintyConfig(enabled=True)
    names = tuple(parameter_names)
    if isinstance(estimates, Mapping):
        point = np.asarray([float(estimates[name]) for name in names], dtype=float)
    else:
        point = _as_1d_float("estimates", estimates)
    if point.size != len(names):
        raise ValueError("estimates length must match parameter_names")

    results = [
        SensitivityIndexUncertainty(
            parameter=name,
            index=index,
            estimate=float(point[idx]),
            standard_error=None,
            ci=None,
            diagnostics=SensitivityDiagnostics(
                ci_status="not_calibrated_single_qmc",
                uncertainty_scope=cfg.uncertainty_scope,
                warnings=["interval not calibrated; rerun with independent scrambles"],
            ),
        )
        for idx, name in enumerate(names)
    ]
    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=JointSensitivityUncertainty(),
        method_metadata=SensitivityMethodMetadata(
            warnings=["not_calibrated_single_qmc"],
        ),
    )


def analyze_surrogate_sobol_bootstrap(
    training_x: np.ndarray,
    training_y: np.ndarray,
    parameter_names: Sequence[str],
    *,
    fit_surrogate: Callable[[np.ndarray, np.ndarray], object],
    compute_indices: Callable[[object], Mapping[str, Mapping[str, float]]],
    config: SensitivityUncertaintyConfig | None = None,
    surrogate_family: str,
    validation_error: float | None = None,
    mc_inner_n: int | None = None,
) -> SensitivityUncertaintyBundle:
    """Two-stage surrogate Sobol bootstrap using caller-provided fit/evaluation callbacks."""

    cfg = config or SensitivityUncertaintyConfig(
        enabled=True,
        uncertainty_scope="sampling_plus_surrogate",
    )
    if cfg.uncertainty_scope == "sampling_only":
        cfg = cfg.model_copy(update={"uncertainty_scope": "sampling_plus_surrogate"})
    x = np.asarray(training_x, dtype=float)
    y = _as_1d_float("training_y", training_y)
    names = tuple(parameter_names)
    if x.ndim != 2:
        raise ValueError("training_x must be a 2D array")
    if x.shape[0] != y.size:
        raise ValueError("training_x and training_y must have the same row count")
    if x.shape[1] != len(names):
        raise ValueError("training_x column count must match parameter_names")

    base_model = fit_surrogate(x, y)
    base_indices = compute_indices(base_model)
    labels, point = _labels_and_vector_from_index_mapping(base_indices, names)
    rng = np.random.default_rng(cfg.random_seed)
    bootstrap = np.empty((cfg.n_resamples, point.size), dtype=float)
    for b in range(cfg.n_resamples):
        idx = rng.integers(0, x.shape[0], size=x.shape[0])
        model = fit_surrogate(x[idx], y[idx])
        _, bootstrap[b] = _labels_and_vector_from_index_mapping(compute_indices(model), names, labels=labels)

    simultaneous = (
        _simultaneous_intervals(point, bootstrap, cfg.level, "surrogate_design_bootstrap", cfg.n_resamples)
        if "simultaneous" in cfg.interval_types
        else None
    )
    results = _index_results_from_bootstrap(
        labels=labels,
        point=point,
        bootstrap=bootstrap,
        bootstrap_se=None,
        jackknife=None,
        config=cfg,
        method="surrogate_design_bootstrap",
        simultaneous=simultaneous,
        clip_bounds=(0.0, 1.0),
        nonnegative_indices={"S1", "ST", "S2"},
        coverage_profile_id=_coverage_profile_id("sobol_surrogate", "surrogate_design_bootstrap"),
    )
    rank_metric = _bootstrap_metric_matrix(labels, bootstrap, names, "ST")
    if rank_metric is None:
        rank_metric = _bootstrap_metric_matrix(labels, bootstrap, names, "S1")
    method_metadata = SensitivityMethodMetadata(
        metadata={
            "surrogate_family": surrogate_family,
            "training_n": int(x.shape[0]),
            "validation_error": validation_error,
            "surrogate_bootstrap_B": cfg.n_resamples,
            "mc_inner_N": mc_inner_n,
            "uncertainty_scope": cfg.uncertainty_scope,
        }
    )

    return SensitivityUncertaintyBundle(
        sensitivity_results=results,
        joint_uncertainty=_joint_uncertainty(
            names,
            rank_metric,
            cfg,
            method="surrogate_design_bootstrap",
            covariance_matrix=_covariance_matrix(bootstrap),
        ),
        method_metadata=method_metadata,
    )


def apply_calibrated_multiplier(
    bundle: SensitivityUncertaintyBundle,
    multiplier: float,
) -> SensitivityUncertaintyBundle:
    """Widen marginal and simultaneous intervals by a learned calibration multiplier."""

    if multiplier <= 0.0 or not math.isfinite(multiplier):
        raise ValueError("multiplier must be a positive finite value")
    copied = bundle.model_copy(deep=True)
    for item in copied.sensitivity_results:
        if item.ci is not None:
            item.ci = _scaled_interval(item.ci, item.estimate, multiplier)
        if item.simultaneous_ci is not None:
            item.simultaneous_ci = _scaled_interval(item.simultaneous_ci, item.estimate, multiplier)
        item.diagnostics.warnings.append(f"calibrated_multiplier:{multiplier}")
    copied.method_metadata.metadata["calibrated_multiplier"] = multiplier
    return copied


def _normalize_sobol_blocks(blocks: SobolRowBlockData) -> SobolRowBlockData:
    names = tuple(blocks.parameter_names)
    y_a = _as_1d_float("y_a", blocks.y_a)
    y_b = _as_1d_float("y_b", blocks.y_b)
    if y_a.shape != y_b.shape:
        raise ValueError("y_a and y_b must have the same shape")
    y_ab = _as_2d_float("y_ab", blocks.y_ab)
    if y_ab.shape != (y_a.size, len(names)):
        if y_ab.shape == (len(names), y_a.size):
            y_ab = y_ab.T
        else:
            raise ValueError("y_ab must have shape (n_rows, n_parameters)")
    y_ba = None
    if blocks.y_ba is not None:
        y_ba = _as_2d_float("y_ba", blocks.y_ba)
        if y_ba.shape != (y_a.size, len(names)):
            if y_ba.shape == (len(names), y_a.size):
                y_ba = y_ba.T
            else:
                raise ValueError("y_ba must have shape (n_rows, n_parameters)")
    if not (np.all(np.isfinite(y_a)) and np.all(np.isfinite(y_b)) and np.all(np.isfinite(y_ab))):
        raise ValueError("Sobol row blocks must be finite")
    if y_ba is not None and not np.all(np.isfinite(y_ba)):
        raise ValueError("Sobol BA row blocks must be finite")
    return SobolRowBlockData(y_a=y_a, y_b=y_b, y_ab=y_ab, y_ba=y_ba, parameter_names=names)


def _take_sobol_rows(blocks: SobolRowBlockData, idx: np.ndarray) -> SobolRowBlockData:
    return SobolRowBlockData(
        y_a=blocks.y_a[idx],
        y_b=blocks.y_b[idx],
        y_ab=blocks.y_ab[idx],
        y_ba=blocks.y_ba[idx] if blocks.y_ba is not None else None,
        parameter_names=blocks.parameter_names,
    )


def _sobol_estimates(blocks: SobolRowBlockData) -> tuple[list[tuple[str, str]], np.ndarray]:
    names = blocks.parameter_names
    y_all = [blocks.y_a, blocks.y_b, blocks.y_ab.reshape(-1)]
    if blocks.y_ba is not None:
        y_all.append(blocks.y_ba.reshape(-1))
    stacked = np.concatenate(y_all)
    mean = float(np.mean(stacked))
    std = float(np.std(stacked))
    if std <= _EPS:
        labels = _sobol_labels(names, include_second_order=blocks.y_ba is not None)
        return labels, np.zeros(len(labels), dtype=float)

    a = (blocks.y_a - mean) / std
    b = (blocks.y_b - mean) / std
    ab = (blocks.y_ab - mean) / std
    ba = (blocks.y_ba - mean) / std if blocks.y_ba is not None else None
    variance = float(np.var(np.concatenate([a, b])))
    if variance <= _EPS:
        labels = _sobol_labels(names, include_second_order=blocks.y_ba is not None)
        return labels, np.zeros(len(labels), dtype=float)

    s1 = np.mean(b[:, None] * (ab - a[:, None]), axis=0) / variance
    st = 0.5 * np.mean((a[:, None] - ab) ** 2, axis=0) / variance
    labels: list[tuple[str, str]] = []
    values: list[float] = []
    for idx, name in enumerate(names):
        labels.append(("S1", name))
        values.append(float(s1[idx]))
    for idx, name in enumerate(names):
        labels.append(("ST", name))
        values.append(float(st[idx]))

    if ba is not None and len(names) > 1:
        for left_idx, left in enumerate(names):
            for right_idx in range(left_idx + 1, len(names)):
                right = names[right_idx]
                vij = float(np.mean(ba[:, left_idx] * ab[:, right_idx] - a * b) / variance)
                labels.append(("S2", f"{left}:{right}"))
                values.append(vij - float(s1[left_idx]) - float(s1[right_idx]))

    return labels, np.asarray(values, dtype=float)


def _sobol_labels(
    parameter_names: tuple[str, ...],
    *,
    include_second_order: bool,
) -> list[tuple[str, str]]:
    labels = [("S1", name) for name in parameter_names]
    labels.extend(("ST", name) for name in parameter_names)
    if include_second_order and len(parameter_names) > 1:
        for left_idx, left in enumerate(parameter_names):
            for right in parameter_names[left_idx + 1 :]:
                labels.append(("S2", f"{left}:{right}"))
    return labels


def _morris_estimates(
    elementary_effects: np.ndarray,
    parameter_names: tuple[str, ...],
) -> tuple[list[tuple[str, str]], np.ndarray]:
    mu = np.mean(elementary_effects, axis=0)
    mu_star = np.mean(np.abs(elementary_effects), axis=0)
    sigma = (
        np.std(elementary_effects, axis=0, ddof=1)
        if elementary_effects.shape[0] > 1
        else np.zeros(elementary_effects.shape[1], dtype=float)
    )
    labels: list[tuple[str, str]] = []
    values: list[float] = []
    for index, metric in (("mu", mu), ("mu_star", mu_star), ("sigma", sigma)):
        for idx, name in enumerate(parameter_names):
            labels.append((index, name))
            values.append(float(metric[idx]))
    return labels, np.asarray(values, dtype=float)


def _jackknife_sobol(blocks: SobolRowBlockData) -> np.ndarray | None:
    n = blocks.y_a.size
    if n < 3:
        return None
    values: list[np.ndarray] = []
    base_idx = np.arange(n)
    for row in range(n):
        _, estimate = _sobol_estimates(_take_sobol_rows(blocks, base_idx[base_idx != row]))
        values.append(estimate)
    return np.vstack(values)


def _jackknife_morris(elementary_effects: np.ndarray, names: tuple[str, ...]) -> np.ndarray | None:
    n = elementary_effects.shape[0]
    if n < 3:
        return None
    values: list[np.ndarray] = []
    base_idx = np.arange(n)
    for row in range(n):
        _, estimate = _morris_estimates(elementary_effects[base_idx != row], names)
        values.append(estimate)
    return np.vstack(values)


def _sobol_inner_bootstrap_se(
    blocks: SobolRowBlockData,
    n_inner: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n = blocks.y_a.size
    _, point = _sobol_estimates(blocks)
    if n < 2:
        return np.zeros_like(point)
    inner = np.empty((n_inner, point.size), dtype=float)
    for idx_inner in range(n_inner):
        idx = rng.integers(0, n, size=n)
        _, inner[idx_inner] = _sobol_estimates(_take_sobol_rows(blocks, idx))
    return np.std(inner, axis=0, ddof=1)


def _morris_inner_bootstrap_se(
    elementary_effects: np.ndarray,
    names: tuple[str, ...],
    n_inner: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n = elementary_effects.shape[0]
    _, point = _morris_estimates(elementary_effects, names)
    if n < 2:
        return np.zeros_like(point)
    inner = np.empty((n_inner, point.size), dtype=float)
    for idx_inner in range(n_inner):
        idx = rng.integers(0, n, size=n)
        _, inner[idx_inner] = _morris_estimates(elementary_effects[idx], names)
    return np.std(inner, axis=0, ddof=1)


def _jackknife_covariance(jackknife: np.ndarray | None) -> np.ndarray | None:
    if jackknife is None or jackknife.shape[0] < 3:
        return None
    jack_mean = np.mean(jackknife, axis=0)
    centered = jackknife - jack_mean[None, :]
    return ((jackknife.shape[0] - 1) / jackknife.shape[0]) * (centered.T @ centered)


def _simulate_normal_draws(
    point: np.ndarray,
    covariance: np.ndarray,
    n_draws: int,
    *,
    seed: int | None,
) -> np.ndarray:
    if point.size == 0 or n_draws < 1:
        return np.empty((0, point.size), dtype=float)
    cov = np.asarray(covariance, dtype=float)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    cov = 0.5 * (cov + cov.T)
    jitter = max(float(np.max(np.diag(cov))) if cov.size else 0.0, 1.0) * 1e-12
    cov = cov + np.eye(point.size) * jitter
    rng = np.random.default_rng(seed)
    try:
        return rng.multivariate_normal(point, cov, size=n_draws, check_valid="ignore")
    except Exception:
        se = np.sqrt(np.clip(np.diag(cov), 0.0, math.inf))
        return point[None, :] + rng.standard_normal((n_draws, point.size)) * se[None, :]


def _index_results_from_covariance(
    *,
    labels: list[tuple[str, str]],
    point: np.ndarray,
    covariance: np.ndarray,
    config: SensitivityUncertaintyConfig,
    method: str,
    simultaneous: tuple[np.ndarray, np.ndarray] | None,
    clip_bounds: tuple[float, float] | None = None,
    coverage_profile_id: str | None = None,
) -> list[SensitivityIndexUncertainty]:
    z = _NORMAL.inv_cdf(0.5 + config.level / 2.0)
    se = np.sqrt(np.clip(np.diag(covariance), 0.0, math.inf))
    out: list[SensitivityIndexUncertainty] = []
    for col, (index, parameter) in enumerate(labels):
        raw_low = float(point[col] - z * se[col])
        raw_high = float(point[col] + z * se[col])
        low, high = _clip_interval(raw_low, raw_high, clip_bounds)
        degenerate = bool(se[col] <= _EPS or not np.isfinite(se[col]))
        warnings = ["degenerate_asymptotic_covariance"] if degenerate else []
        ci = SensitivityInterval(
            level=config.level,
            low=low,
            high=high,
            raw_low=raw_low,
            raw_high=raw_high,
            method=method,
            simultaneous=False,
            n_resamples=0,
            coverage_profile_id=coverage_profile_id,
        )
        sim_ci = None
        if simultaneous is not None:
            sim_low, sim_high = simultaneous
            raw_sim_low = float(sim_low[col])
            raw_sim_high = float(sim_high[col])
            low_sim, high_sim = _clip_interval(raw_sim_low, raw_sim_high, clip_bounds)
            sim_ci = SensitivityInterval(
                level=config.level,
                low=low_sim,
                high=high_sim,
                raw_low=raw_sim_low,
                raw_high=raw_sim_high,
                method=f"{method}_max_t",
                simultaneous=True,
                n_resamples=config.simulated_rank_draws,
                coverage_profile_id=coverage_profile_id,
            )
        out.append(
            SensitivityIndexUncertainty(
                parameter=parameter,
                index=index,
                estimate=float(point[col]),
                standard_error=float(se[col]),
                ci=ci,
                simultaneous_ci=sim_ci,
                diagnostics=SensitivityDiagnostics(
                    degenerate=degenerate,
                    ci_status="degenerate_asymptotic_covariance" if degenerate else "ok",
                    uncertainty_scope=config.uncertainty_scope,
                    warnings=warnings,
                ),
            )
        )
    return out


def _labels_and_vector_from_index_mapping(
    indices: Mapping[str, Mapping[str, float]],
    parameter_names: tuple[str, ...],
    *,
    labels: list[tuple[str, str]] | None = None,
) -> tuple[list[tuple[str, str]], np.ndarray]:
    if labels is None:
        generated: list[tuple[str, str]] = []
        for index in ("S1", "ST", "S2"):
            metric_values = indices.get(index)
            if not metric_values:
                continue
            if index == "S2":
                for key in sorted(metric_values):
                    generated.append((index, key))
            else:
                for name in parameter_names:
                    generated.append((index, name))
        labels = generated
    values: list[float] = []
    for index, parameter in labels:
        metric_values = indices.get(index)
        if metric_values is None or parameter not in metric_values:
            raise ValueError(f"surrogate compute_indices missing {index}:{parameter}")
        values.append(float(metric_values[parameter]))
    return labels, np.asarray(values, dtype=float)


def _index_results_from_bootstrap(
    *,
    labels: list[tuple[str, str]],
    point: np.ndarray,
    bootstrap: np.ndarray,
    bootstrap_se: np.ndarray | None,
    jackknife: np.ndarray | None,
    config: SensitivityUncertaintyConfig,
    method: str,
    simultaneous: tuple[np.ndarray, np.ndarray] | None,
    clip_bounds: tuple[float, float] | None = None,
    clip_bounds_by_index: dict[str, tuple[float, float]] | None = None,
    nonnegative_indices: set[str] | None = None,
    coverage_profile_id: str | None = None,
) -> list[SensitivityIndexUncertainty]:
    out: list[SensitivityIndexUncertainty] = []
    nonnegative_indices = nonnegative_indices or set()
    for col, (index, parameter) in enumerate(labels):
        boot_col = bootstrap[:, col]
        jack_col = jackknife[:, col] if jackknife is not None else None
        raw_low, raw_high = _bootstrap_interval(
            point=float(point[col]),
            bootstrap=boot_col,
            bootstrap_se=bootstrap_se[:, col] if bootstrap_se is not None else None,
            jackknife=jack_col,
            level=config.level,
            method=method,
        )
        bounds = clip_bounds_by_index.get(index) if clip_bounds_by_index else clip_bounds
        low, high = _clip_interval(raw_low, raw_high, bounds)
        se = float(np.std(boot_col, ddof=1)) if boot_col.size > 1 else 0.0
        degenerate = bool(se <= _EPS or not np.isfinite(se))
        out_of_bounds = 0.0
        if bounds is not None and all(math.isfinite(v) for v in bounds):
            out_of_bounds = float(np.mean((boot_col < bounds[0]) | (boot_col > bounds[1])))
        elif index in nonnegative_indices:
            out_of_bounds = float(np.mean(boot_col < 0.0))

        warnings: list[str] = []
        status = "ok"
        if degenerate:
            status = "degenerate_bootstrap"
            warnings.append("degenerate_bootstrap")
        elif out_of_bounds > 0.05:
            status = "bootstrap_out_of_bounds"
            warnings.append("bootstrap_out_of_bounds")

        ci = SensitivityInterval(
            level=config.level,
            low=low,
            high=high,
            raw_low=float(raw_low),
            raw_high=float(raw_high),
            method=method,
            simultaneous=False,
            n_resamples=config.n_resamples,
            coverage_profile_id=coverage_profile_id,
        )
        sim_ci = None
        if simultaneous is not None:
            sim_low, sim_high = simultaneous
            raw_sim_low = float(sim_low[col])
            raw_sim_high = float(sim_high[col])
            low_sim, high_sim = _clip_interval(raw_sim_low, raw_sim_high, bounds)
            sim_ci = SensitivityInterval(
                level=config.level,
                low=low_sim,
                high=high_sim,
                raw_low=raw_sim_low,
                raw_high=raw_sim_high,
                method=f"{method}_max_t",
                simultaneous=True,
                n_resamples=config.n_resamples,
                coverage_profile_id=coverage_profile_id,
            )

        out.append(
            SensitivityIndexUncertainty(
                parameter=parameter,
                index=index,
                estimate=float(point[col]),
                standard_error=se,
                ci=ci,
                simultaneous_ci=sim_ci,
                diagnostics=SensitivityDiagnostics(
                    bootstrap_out_of_bounds_rate=out_of_bounds,
                    degenerate=degenerate,
                    ci_status=status,
                    uncertainty_scope=config.uncertainty_scope,
                    warnings=warnings,
                ),
            )
        )
    return out


def _bootstrap_interval(
    *,
    point: float,
    bootstrap: np.ndarray,
    bootstrap_se: np.ndarray | None,
    jackknife: np.ndarray | None,
    level: float,
    method: str,
) -> tuple[float, float]:
    finite = np.asarray(bootstrap[np.isfinite(bootstrap)], dtype=float)
    if finite.size == 0:
        return point, point
    alpha = 1.0 - level
    q_low = alpha / 2.0
    q_high = 1.0 - alpha / 2.0

    if method.endswith("_basic_bootstrap"):
        high, low = np.quantile(finite, [q_high, q_low])
        return float(2.0 * point - high), float(2.0 * point - low)

    if method.endswith("_normal_bootstrap"):
        se = float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0
        z = _NORMAL.inv_cdf(q_high)
        return float(point - z * se), float(point + z * se)

    if method.endswith("_studentized_bootstrap") and bootstrap_se is not None:
        se_hat = float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0
        valid = np.isfinite(bootstrap_se) & (bootstrap_se > _EPS) & np.isfinite(bootstrap)
        if se_hat > _EPS and np.any(valid):
            pivots = (bootstrap[valid] - point) / bootstrap_se[valid]
            upper, lower = np.quantile(pivots, [q_high, q_low])
            return float(point - upper * se_hat), float(point - lower * se_hat)

    if method.endswith("_bca_bootstrap") and jackknife is not None:
        bca = _bca_interval(point, finite, jackknife, q_low, q_high)
        if bca is not None:
            return bca

    low, high = np.quantile(finite, [q_low, q_high])
    return float(low), float(high)


def _bca_interval(
    point: float,
    bootstrap: np.ndarray,
    jackknife: np.ndarray,
    q_low: float,
    q_high: float,
) -> tuple[float, float] | None:
    finite_jack = np.asarray(jackknife[np.isfinite(jackknife)], dtype=float)
    if bootstrap.size < 10 or finite_jack.size < 3:
        return None
    prop_less = float(np.mean(bootstrap < point))
    prop_less = min(max(prop_less, 1.0 / (2.0 * bootstrap.size)), 1.0 - 1.0 / (2.0 * bootstrap.size))
    z0 = _NORMAL.inv_cdf(prop_less)

    jack_mean = float(np.mean(finite_jack))
    centered = jack_mean - finite_jack
    denom = 6.0 * float(np.sum(centered**2)) ** 1.5
    acceleration = 0.0 if denom <= _EPS else float(np.sum(centered**3)) / denom

    def _adjust(q: float) -> float:
        z = _NORMAL.inv_cdf(q)
        denom_inner = 1.0 - acceleration * (z0 + z)
        if abs(denom_inner) <= _EPS:
            return q
        return _NORMAL.cdf(z0 + (z0 + z) / denom_inner)

    adjusted = [
        min(max(_adjust(q_low), 0.0), 1.0),
        min(max(_adjust(q_high), 0.0), 1.0),
    ]
    if adjusted[0] > adjusted[1]:
        adjusted.reverse()
    low, high = np.quantile(bootstrap, adjusted)
    return float(low), float(high)


def _simultaneous_intervals(
    point: np.ndarray,
    bootstrap: np.ndarray,
    level: float,
    method: str,
    n_resamples: int,
) -> tuple[np.ndarray, np.ndarray]:
    del method, n_resamples
    se = np.std(bootstrap, axis=0, ddof=1)
    safe_se = np.where(se > _EPS, se, math.inf)
    max_t = np.max(np.abs((bootstrap - point[None, :]) / safe_se[None, :]), axis=1)
    critical = float(np.quantile(max_t[np.isfinite(max_t)], level)) if np.any(np.isfinite(max_t)) else 0.0
    return point - critical * se, point + critical * se


def _joint_uncertainty(
    parameter_names: tuple[str, ...],
    bootstrap_metric: np.ndarray | None,
    config: SensitivityUncertaintyConfig,
    *,
    method: str,
    covariance_matrix: list[list[float]] | None = None,
) -> JointSensitivityUncertainty:
    if bootstrap_metric is None or not config.rank_uncertainty:
        return JointSensitivityUncertainty(covariance_matrix=covariance_matrix)

    metric = np.asarray(bootstrap_metric, dtype=float)
    names = tuple(parameter_names)
    n_resamples, d = metric.shape
    rank_counts = {name: {str(rank): 0 for rank in range(1, d + 1)} for name in names}
    top_counts = {
        name: {f"top{k}": 0 for k in sorted({k for k in config.top_k if 1 <= k <= d})}
        for name in names
    }
    ranks = np.empty((n_resamples, d), dtype=int)
    for row_idx in range(n_resamples):
        order = np.argsort(-metric[row_idx], kind="mergesort")
        for rank_zero, param_idx in enumerate(order):
            rank = rank_zero + 1
            ranks[row_idx, param_idx] = rank
            rank_counts[names[param_idx]][str(rank)] += 1
            for key in top_counts[names[param_idx]]:
                k = int(key[3:])
                if rank <= k:
                    top_counts[names[param_idx]][key] += 1

    rank_probabilities = {
        name: {rank: count / n_resamples for rank, count in counts.items()}
        for name, counts in rank_counts.items()
    }
    top_k_probabilities = {
        name: {key: count / n_resamples for key, count in counts.items()}
        for name, counts in top_counts.items()
    }

    pairwise: dict[str, float] = {}
    difference_ci: dict[str, SensitivityInterval] = {}
    alpha = 1.0 - config.level
    for i, left in enumerate(names):
        for j, right in enumerate(names):
            if i == j:
                continue
            pairwise[f"{left}>{right}"] = float(np.mean(metric[:, i] > metric[:, j]))
            if i < j:
                diff = metric[:, i] - metric[:, j]
                low, high = np.quantile(diff, [alpha / 2.0, 1.0 - alpha / 2.0])
                difference_ci[f"{left}-{right}"] = SensitivityInterval(
                    level=config.level,
                    low=float(low),
                    high=float(high),
                    raw_low=float(low),
                    raw_high=float(high),
                    method=f"{method}_difference_percentile",
                    simultaneous=False,
                    n_resamples=config.n_resamples,
                )

    return JointSensitivityUncertainty(
        covariance_matrix=covariance_matrix,
        rank_probabilities=rank_probabilities,
        top_k_probabilities=top_k_probabilities,
        pairwise_dominance=pairwise,
        difference_ci=difference_ci,
    )


def _bootstrap_metric_matrix(
    labels: list[tuple[str, str]],
    bootstrap: np.ndarray,
    parameter_names: tuple[str, ...],
    index: str,
) -> np.ndarray | None:
    cols: list[int] = []
    for name in parameter_names:
        try:
            cols.append(labels.index((index, name)))
        except ValueError:
            return None
    return bootstrap[:, cols]


def _resolve_bootstrap_method(method: str, *, default: str, aliases: set[str]) -> str:
    normalized = method.lower()
    if normalized == "auto" or normalized in aliases:
        return default
    if normalized in {"percentile", "bootstrap_percentile"}:
        prefix = default.removesuffix("_bca_bootstrap")
        return f"{prefix}_percentile_bootstrap"
    if normalized in {"basic", "bootstrap_basic"}:
        prefix = default.removesuffix("_bca_bootstrap")
        return f"{prefix}_basic_bootstrap"
    if normalized in {"normal", "bootstrap_normal"}:
        prefix = default.removesuffix("_bca_bootstrap")
        return f"{prefix}_normal_bootstrap"
    if normalized in {"studentized", "bootstrap_studentized", "studentized_bootstrap"}:
        prefix = default.removesuffix("_bca_bootstrap")
        return f"{prefix}_studentized_bootstrap"
    if normalized in {"bca", "bootstrap_bca"}:
        return default
    return normalized


def _coverage_profile_id(prefix: str, method: str) -> str:
    return f"{prefix}_{method}_v1"


def _covariance_matrix(values: np.ndarray) -> list[list[float]] | None:
    if values.shape[0] < 2 or values.shape[1] < 1:
        return None
    cov = np.cov(values, rowvar=False)
    if cov.ndim == 0:
        cov = np.asarray([[float(cov)]], dtype=float)
    return np.asarray(cov, dtype=float).tolist()


def _clip_interval(
    raw_low: float,
    raw_high: float,
    bounds: tuple[float, float] | None,
) -> tuple[float, float]:
    if bounds is None:
        return float(raw_low), float(raw_high)
    low_bound, high_bound = bounds
    low = max(low_bound, raw_low) if math.isfinite(low_bound) else raw_low
    high = min(high_bound, raw_high) if math.isfinite(high_bound) else raw_high
    return float(low), float(high)


def _plain_interval(
    point: float,
    half_width: float,
    level: float,
    method: str,
    *,
    clip_low: float | None = None,
) -> SensitivityInterval:
    raw_low = float(point - half_width)
    raw_high = float(point + half_width)
    low = max(clip_low, raw_low) if clip_low is not None else raw_low
    return SensitivityInterval(
        level=level,
        low=float(low),
        high=raw_high,
        raw_low=raw_low,
        raw_high=raw_high,
        method=method,
        simultaneous=False,
        n_resamples=0,
    )


def _scaled_interval(
    interval: SensitivityInterval,
    estimate: float,
    multiplier: float,
) -> SensitivityInterval:
    raw_low = float(estimate - multiplier * (estimate - interval.raw_low))
    raw_high = float(estimate + multiplier * (interval.raw_high - estimate))
    low_bound = 0.0 if interval.low == 0.0 and interval.raw_low < 0.0 else -math.inf
    high_bound = 1.0 if interval.high == 1.0 and interval.raw_high > 1.0 else math.inf
    low, high = _clip_interval(raw_low, raw_high, (low_bound, high_bound))
    return interval.model_copy(
        update={
            "low": low,
            "high": high,
            "raw_low": raw_low,
            "raw_high": raw_high,
            "method": f"{interval.method}_calibrated",
        }
    )


def _sigma_bootstrap_log(
    effects: np.ndarray,
    n_resamples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if effects.size < 2 or n_resamples < 1:
        return np.asarray([], dtype=float)
    out = np.empty(n_resamples, dtype=float)
    for idx in range(n_resamples):
        subset = effects[rng.integers(0, effects.size, size=effects.size)]
        sigma = float(np.std(subset, ddof=1))
        out[idx] = math.log(max(sigma, 0.0) + _EPS)
    return out


def _t_critical(level: float, df: int) -> float:
    try:
        from scipy import stats  # type: ignore[import-not-found]

        return float(stats.t.ppf(0.5 + level / 2.0, df=df))
    except Exception:
        return float(_NORMAL.inv_cdf(0.5 + level / 2.0))


def _as_1d_float(name: str, values: Sequence[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _as_2d_float(name: str, values: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D array")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


__all__ = [
    "JointSensitivityUncertainty",
    "SensitivityDiagnostics",
    "SensitivityIndexUncertainty",
    "SensitivityInterval",
    "SensitivityMethodMetadata",
    "SensitivityUncertaintyBundle",
    "SensitivityUncertaintyConfig",
    "MorrisStoragePayload",
    "ResolvedSensitivityUncertaintyMethod",
    "SobolQMCMetadata",
    "SobolRowBlockData",
    "SobolStoragePayload",
    "apply_calibrated_multiplier",
    "analyze_hierarchical_replicate_bootstrap",
    "analyze_morris_trajectory_bootstrap",
    "analyze_rqmc_replicate_ci",
    "analyze_single_qmc_warning",
    "analyze_sobol_asymptotic_delta",
    "analyze_sobol_paired_bootstrap",
    "analyze_surrogate_sobol_bootstrap",
    "morris_analytic_intervals",
    "morris_elementary_effects_from_samples",
    "morris_elementary_effects_from_storage",
    "morris_storage_from_elementary_effects",
    "resolve_sensitivity_uncertainty_method",
    "sobol_blocks_from_storage",
    "sobol_blocks_from_salib_outputs",
    "sobol_storage_from_blocks",
]
