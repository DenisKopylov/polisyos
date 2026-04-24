"""Metrics: RMSE, PEHE, coverage, bias, bootstrap SEs, Wilcoxon tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class AggregatedMetrics:
    """Metrics aggregated across K replications for one method+dataset."""

    method_name: str
    dataset_name: str
    tier: str
    n_replications: int
    n_failed: int

    ate_bias: float
    ate_bias_se: float
    ate_rmse: float
    ate_rmse_se: float
    ci_coverage: float
    ci_coverage_se: float
    ci_width_mean: float
    pehe: float | None  # only for CATE methods
    pehe_se: float | None
    wall_time_mean: float
    wall_time_p95: float
    failure_rate: float

    # Per-replication arrays (for pairwise tests)
    per_rep_ate_error: np.ndarray  # (K,) array of ATE_hat - ATE_true
    per_rep_sq_error: np.ndarray  # (K,) array of (ATE_hat - ATE_true)^2


def aggregate_metrics(
    method_name: str,
    dataset_name: str,
    tier: str,
    true_ate: float,
    results: list,  # list of EstimatorResult
    true_cates: list[np.ndarray | None] | None = None,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> AggregatedMetrics:
    """Compute all metrics from K replication results."""
    rng = np.random.default_rng(seed)

    # Filter successful runs
    valid = [(i, r) for i, r in enumerate(results) if not r.failed and r.ate is not None]
    n_failed = len(results) - len(valid)
    n_valid = len(valid)

    if n_valid == 0:
        return AggregatedMetrics(
            method_name=method_name,
            dataset_name=dataset_name,
            tier=tier,
            n_replications=len(results),
            n_failed=n_failed,
            ate_bias=np.nan,
            ate_bias_se=np.nan,
            ate_rmse=np.nan,
            ate_rmse_se=np.nan,
            ci_coverage=np.nan,
            ci_coverage_se=np.nan,
            ci_width_mean=np.nan,
            pehe=np.nan,
            pehe_se=np.nan,
            wall_time_mean=np.nan,
            wall_time_p95=np.nan,
            failure_rate=1.0,
            per_rep_ate_error=np.array([]),
            per_rep_sq_error=np.array([]),
        )

    ates = np.array([r.ate for _, r in valid])
    errors = ates - true_ate
    sq_errors = errors**2

    # ATE Bias
    bias = float(np.mean(errors))
    # ATE RMSE
    rmse = float(np.sqrt(np.mean(sq_errors)))

    # CI Coverage
    coverage_hits = []
    ci_widths = []
    for _, r in valid:
        if r.ci_lower is not None and r.ci_upper is not None:
            covered = r.ci_lower <= true_ate <= r.ci_upper
            coverage_hits.append(float(covered))
            ci_widths.append(r.ci_upper - r.ci_lower)
    coverage = float(np.mean(coverage_hits)) if coverage_hits else np.nan
    ci_width_mean = float(np.mean(ci_widths)) if ci_widths else np.nan

    # PEHE (if CATE available)
    pehe_val = None
    if true_cates is not None:
        pehe_list = []
        for (i, r), tc in zip(valid, [true_cates[i] for i, _ in valid]):
            if r.cate is not None and tc is not None and len(r.cate) == len(tc):
                pehe_list.append(float(np.sqrt(np.mean((r.cate - tc) ** 2))))
        if pehe_list:
            pehe_val = float(np.mean(pehe_list))

    # Wall-clock time
    times = np.array([r.elapsed_s for _, r in valid])
    wall_mean = float(np.mean(times))
    wall_p95 = float(np.percentile(times, 95))

    # Bootstrap SEs for bias and RMSE
    bias_boots = np.empty(n_bootstrap)
    rmse_boots = np.empty(n_bootstrap)
    cov_boots = np.empty(n_bootstrap)
    pehe_boots = np.empty(n_bootstrap) if pehe_val is not None else None

    for b in range(n_bootstrap):
        idx = rng.integers(0, n_valid, n_valid)
        b_errors = errors[idx]
        bias_boots[b] = np.mean(b_errors)
        rmse_boots[b] = np.sqrt(np.mean(b_errors**2))
        if coverage_hits:
            b_cov = np.array(coverage_hits)[idx[: len(coverage_hits)]]
            cov_boots[b] = np.mean(b_cov)
        if pehe_boots is not None and pehe_list:
            b_pehe = np.array(pehe_list)
            b_idx = rng.integers(0, len(b_pehe), len(b_pehe))
            pehe_boots[b] = np.mean(b_pehe[b_idx])

    return AggregatedMetrics(
        method_name=method_name,
        dataset_name=dataset_name,
        tier=tier,
        n_replications=len(results),
        n_failed=n_failed,
        ate_bias=bias,
        ate_bias_se=float(np.std(bias_boots, ddof=1)),
        ate_rmse=rmse,
        ate_rmse_se=float(np.std(rmse_boots, ddof=1)),
        ci_coverage=coverage,
        ci_coverage_se=float(np.std(cov_boots, ddof=1)) if coverage_hits else np.nan,
        ci_width_mean=ci_width_mean,
        pehe=pehe_val,
        pehe_se=float(np.std(pehe_boots, ddof=1)) if pehe_boots is not None and pehe_list else None,
        wall_time_mean=wall_mean,
        wall_time_p95=wall_p95,
        failure_rate=n_failed / len(results),
        per_rep_ate_error=errors,
        per_rep_sq_error=sq_errors,
    )


# -----------------------------------------------------------------------
# Pairwise statistical tests
# -----------------------------------------------------------------------


@dataclass
class PairwiseTestResult:
    method_a: str
    method_b: str
    statistic: float
    p_value: float
    corrected_p: float
    effect_size: float  # Cohen's d
    significant: bool


def pairwise_wilcoxon(
    metrics_list: list[AggregatedMetrics],
    alpha: float = 0.05,
) -> list[PairwiseTestResult]:
    """Run Wilcoxon signed-rank tests on per-replication squared errors, with Holm-Bonferroni."""
    results: list[PairwiseTestResult] = []
    n_methods = len(metrics_list)
    if n_methods < 2:
        return results

    raw_tests = []
    for i in range(n_methods):
        for j in range(i + 1, n_methods):
            a = metrics_list[i]
            b = metrics_list[j]
            # Align replications
            min_len = min(len(a.per_rep_sq_error), len(b.per_rep_sq_error))
            if min_len < 5:
                continue
            sq_a = a.per_rep_sq_error[:min_len]
            sq_b = b.per_rep_sq_error[:min_len]
            diff = sq_a - sq_b

            try:
                stat_val, p_val = stats.wilcoxon(diff, alternative="two-sided")
            except ValueError:
                continue

            # Cohen's d on squared errors
            pooled_std = np.sqrt((np.var(sq_a, ddof=1) + np.var(sq_b, ddof=1)) / 2)
            d = float(np.mean(diff) / pooled_std) if pooled_std > 0 else 0.0

            raw_tests.append((a.method_name, b.method_name, float(stat_val), float(p_val), d))

    # Holm-Bonferroni correction
    raw_tests.sort(key=lambda t: t[3])
    m = len(raw_tests)

    for rank, (name_a, name_b, stat_val, p_val, d) in enumerate(raw_tests):
        corrected = min(p_val * (m - rank), 1.0)
        results.append(
            PairwiseTestResult(
                method_a=name_a,
                method_b=name_b,
                statistic=stat_val,
                p_value=p_val,
                corrected_p=corrected,
                effect_size=d,
                significant=corrected < alpha,
            )
        )

    return results
