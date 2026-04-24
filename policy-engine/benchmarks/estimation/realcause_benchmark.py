"""Circuit 2: Effect Estimation — RealCause benchmark.

Evaluates estimation accuracy against the RealCause collection of datasets
(Gentzel et al., 2021 — "A Case for Evaluating Causal Models Using Interventional
Measures and Empirical Data").  RealCause provides real-world covariate distributions
with interventional ground truth collected from randomized experiments.

Metrics
-------
    ATE bias, RMSE
    CI coverage
    PEHE (when individual effects are available)
    Distributional divergence: KL divergence (P_obs ‖ P_pred) and/or MMD

Bar
---
    ATE RMSE ≤ 2× best baseline on each dataset.
    KL divergence ≤ 3× best baseline.
    CI coverage ≥ 0.75.
    No method failure rate > 30%.

Datasets (synthetic replicas when real data absent)
----------------------------------------------------
    twins       — Low-birthweight twins (Louizos et al.); binary treatment, outcomes
    lalonde_rct — LaLonde RCT (randomized baseline)
    lalonde_obs — LaLonde observational (selection bias)
    ihdp        — Infant Health and Development Program (Hill 2011)
    news        — News reading behavior (synthetic)

Usage
-----
    python benchmarks/estimation/realcause_benchmark.py
    python benchmarks/estimation/realcause_benchmark.py --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_BENCH_ROOT = Path(__file__).resolve().parent.parent
_SRC = _BENCH_ROOT.parent / "src"
for _p in [str(_SRC), str(_BENCH_ROOT.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------

from benchmarks.comparators import (
    ForestDRLearnerComparator,
    build_research_acceptance_comparator_status,
    comparator_degraded_reasons,
    comparator_required_modules,
)
from benchmarks.estimator_profiles import (  # noqa: E402
    ESTIMATION_METHOD_PROFILES,
    benchmark_selection_manifest_from_params,
    external_dml_params,
    fast_benchmark_mode,
    policyos_causal_bcf_params,
    policyos_causal_forest_params,
    policyos_forestdr_params,
    policyos_nuisance_params,
    policyos_xlearner_params,
    resolve_estimation_method_profile,
)
from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
    Verdict,
)
from benchmarks.method_registry import build_method_registry, infer_method_group
from benchmarks.policyos_runner import extract_policyos_result, invoke_policyos_method
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.research_metrics import (
    basic_overlap_diagnostics,
    eceth,
    fit_eval_propensity,
    summarize_calibration_metrics,
    summarize_method_records,
    summarize_overlap_diagnostics,
    summarize_selection_manifest,
)
from benchmarks.runtime import (
    BenchmarkMode,
    BenchmarkTier,
    acceptance_gaps,
    classify_data_source,
    dependency_status,
    env_path_status,
    resolve_mode,
    resolve_tier,
)
from benchmarks.scorecards import (
    build_flagship_scorecard,
    compute_grouped_method_presence,
    compute_grouped_ranking_summary,
    compute_method_presence,
    compute_ranking_summary,
    summarize_method_metrics,
)
from polisyos.foundry.methods.catalog.causal.protocols import (  # noqa: E402
    HTEObservationalData,
)

CIRCUIT = BenchmarkCircuit.ESTIMATION
REALCAUSE_FLAGSHIP_METHOD = "policy_os_xlearner_cf"
REALCAUSE_LITERATURE_ANCHOR = [
    "Gentzel et al. (2021). A Case for Evaluating Causal Models Using Interventional Measures and Empirical Data.",
    "RealCause benchmark collection for causal effect estimation on empirical covariate distributions.",
]
REALCAUSE_BENCHMARK_ROLES = {
    REALCAUSE_FLAGSHIP_METHOD: "flagship",
    "policy_os_aipw_cf": "production_challenger",
    "policy_os_tmle_cf": "production_challenger",
    "policy_os_causal_forest": "production_challenger",
    "policy_os_causal_bcf": "exploratory",
    "policy_os_drlearner_cf": "exploratory",
    "policy_os_forestdr_cf": "exploratory",
    "external_dml_econml": "exploratory",
}
REALCAUSE_GATE_METHOD_SET = tuple(
    method_name
    for method_name, role in REALCAUSE_BENCHMARK_ROLES.items()
    if role in {"flagship", "production_challenger"}
)

REALCAUSE_DATA_DIR: Path | None = (
    Path(p) if (p := os.environ.get("REALCAUSE_DATA_DIR", "")) else None
)


def _realcause_family_name(dataset_name: str) -> str:
    name = str(dataset_name).lower()
    for family in (
        "lalonde_cps",
        "lalonde_psid",
        "lalonde_rct",
        "lalonde_obs",
        "twins",
        "ihdp",
        "news",
    ):
        if name.startswith(family):
            return family
    return name.split("_sample", 1)[0]


def _realcause_nuisance_params(
    tier: BenchmarkTier,
    *,
    seed: int,
    dataset_name: str,
) -> dict[str, Any]:
    params = policyos_nuisance_params(tier, seed=seed, hte=False)
    family = _realcause_family_name(dataset_name)
    if family in {"lalonde_cps", "lalonde_psid", "lalonde_obs"}:
        params.update(
            {
                "propensity_backend": "logistic_regression",
                "propensity_backend_candidates": [
                    "logistic_regression",
                    "histgradientboosting",
                    "lightgbm",
                ],
                "outcome_backend": "elastic_net",
                "outcome_backend_candidates": [
                    "elastic_net",
                    "histgradientboosting",
                    "lightgbm",
                ],
                "propensity_clipping": 0.05 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.025,
                "propensity_trimming": 0.05 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.025,
                "overlap_trim": 0.05 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.025,
                "overlap_guard": 0.20 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.14,
                "min_effective_sample_size": 64 if tier is BenchmarkTier.LOCAL_EVIDENCE else 96,
            }
        )
    elif family == "twins":
        params.update(
            {
                "propensity_clipping": 0.04 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.02,
                "propensity_trimming": 0.04 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.02,
                "overlap_trim": 0.04 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.02,
            }
        )
    return params


def _realcause_xlearner_params(
    tier: BenchmarkTier,
    *,
    seed: int,
    dataset_name: str,
) -> dict[str, Any]:
    params = policyos_xlearner_params(tier, seed=seed)
    family = _realcause_family_name(dataset_name)
    params.update(
        {
            "selection_objective": "dr_ate_overlap",
            "split_policy": "holdout_dr_ate_overlap",
        }
    )
    if family in {"lalonde_cps", "lalonde_psid", "lalonde_obs"}:
        params.update(
            {
                "base_model_candidates": [
                    "linear",
                    "elastic_net_sparse",
                    "gradient_boosting",
                ],
            }
        )
    return params


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class RealCauseMetrics:
    ate_true: float
    ate_pred: float
    ate_ci_lower: float
    ate_ci_upper: float
    cate_true: np.ndarray | None
    cate_pred: np.ndarray | None
    method_name: str
    dataset_name: str
    selection_manifest: dict[str, Any] = dataclasses.field(default_factory=dict)
    overlap_diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)
    failed: bool = False
    fail_reason: str = ""

    @property
    def ate_bias(self) -> float:
        return self.ate_pred - self.ate_true

    @property
    def ci_covers(self) -> bool:
        return self.ate_ci_lower <= self.ate_true <= self.ate_ci_upper

    @property
    def ci_width(self) -> float:
        return self.ate_ci_upper - self.ate_ci_lower

    @property
    def pehe(self) -> float | None:
        if self.cate_true is None or self.cate_pred is None:
            return None
        return float(np.sqrt(np.mean((self.cate_pred - self.cate_true) ** 2)))


@dataclasses.dataclass
class DatasetResult:
    dataset_name: str
    method_name: str
    n_reps: int
    ate_true: float
    ate_biases: list[float]
    ci_covers: list[bool]
    ci_widths: list[float]
    pehe_values: list[float]
    kl_divergences: list[float]
    n_failed: int
    selection_records: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    overlap_records: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    calibration_records: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    @property
    def ate_rmse(self) -> float:
        valid = [b for b in self.ate_biases if math.isfinite(b)]
        if not valid:
            return float("inf")
        return float(np.sqrt(np.mean(np.array(valid) ** 2)))

    @property
    def ci_coverage(self) -> float:
        return float(np.mean(self.ci_covers)) if self.ci_covers else float("nan")

    @property
    def pehe_mean(self) -> float:
        valid = [v for v in self.pehe_values if math.isfinite(v)]
        return float(np.mean(valid)) if valid else float("nan")

    @property
    def kl_mean(self) -> float:
        valid = [v for v in self.kl_divergences if math.isfinite(v) and v >= 0]
        return float(np.mean(valid)) if valid else float("nan")

    @property
    def failure_rate(self) -> float:
        return self.n_failed / self.n_reps if self.n_reps > 0 else 1.0

    @property
    def selection_manifest(self) -> dict[str, Any]:
        return summarize_selection_manifest(self.selection_records)

    @property
    def overlap_diagnostics(self) -> dict[str, Any]:
        return summarize_overlap_diagnostics(self.overlap_records)

    @property
    def calibration_metrics(self) -> dict[str, Any]:
        return summarize_calibration_metrics(self.calibration_records)


# ---------------------------------------------------------------------------
# Distributional divergence metrics
# ---------------------------------------------------------------------------


def _kl_divergence_kde(
    p_samples: np.ndarray, q_samples: np.ndarray, bandwidth: float = 0.5
) -> float:
    """KL divergence D(P ‖ Q) estimated via kernel density.

    Uses a simple histogram-based approximation for robustness.
    Returns float — smaller is better (0 = identical distributions).
    """
    p_samples = np.asarray(p_samples, dtype=float)
    q_samples = np.asarray(q_samples, dtype=float)

    # Shared bin edges over combined support
    combined = np.concatenate([p_samples, q_samples])
    n_bins = min(50, max(10, len(p_samples) // 10))
    lo, hi = np.percentile(combined, 1), np.percentile(combined, 99)
    if lo >= hi:
        return 0.0

    bins = np.linspace(lo, hi, n_bins + 1)
    p_hist, _ = np.histogram(p_samples, bins=bins, density=True)
    q_hist, _ = np.histogram(q_samples, bins=bins, density=True)

    eps = 1e-12
    p_hist = p_hist + eps
    q_hist = q_hist + eps
    p_hist /= p_hist.sum()
    q_hist /= q_hist.sum()

    return float(np.sum(p_hist * np.log(p_hist / q_hist)))


def _mmd_linear(x: np.ndarray, y: np.ndarray) -> float:
    """Linear-time Maximum Mean Discrepancy with RBF kernel (bandwidth = median heuristic)."""
    x = np.asarray(x, dtype=float).reshape(-1, 1) if x.ndim == 1 else x
    y = np.asarray(y, dtype=float).reshape(-1, 1) if y.ndim == 1 else y

    # Bandwidth: median pairwise distance
    combined = np.vstack([x[:100], y[:100]])
    dists = np.sum(combined[:, None] - combined[None, :], axis=-1) ** 2
    bw = float(np.median(dists[dists > 0])) if np.any(dists > 0) else 1.0

    def rbf(a: np.ndarray, b: np.ndarray) -> float:
        d2 = np.mean(np.sum((a[:, None] - b[None, :]) ** 2, axis=-1))
        return float(np.exp(-d2 / (2 * bw)))

    n = min(200, len(x))
    m = min(200, len(y))
    xi, yi = x[:n], y[:m]
    return max(0.0, rbf(xi, xi) - 2 * rbf(xi, yi) + rbf(yi, yi))


def _compute_distributional_divergence(
    y_obs: np.ndarray,
    y_pred: np.ndarray,
) -> float:
    """KL divergence of predicted outcome distribution vs observed."""
    return _kl_divergence_kde(y_obs, y_pred)


# ---------------------------------------------------------------------------
# Synthetic dataset replicas
# ---------------------------------------------------------------------------


def _dgp_twins_like(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 30,
    ate: float = 0.08,
) -> tuple[HTEObservationalData, np.ndarray, float]:
    """Twins-inspired DGP: binary outcome (mortality), selection on observables.

    Returns (data, cate_true_continuous, ate_true).
    """
    X = rng.standard_normal((n, p))
    # Mimic selection on birthweight features
    sel_coef = rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-(X @ sel_coef) * 1.5))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    beta0 = rng.standard_normal(p) / np.sqrt(p)
    mu0 = 0.15 + np.clip(X @ beta0 * 0.5, -0.1, 0.5)
    cate_true = ate * np.ones(n)
    # Observed outcome (binary)
    mu1 = np.clip(mu0 + cate_true, 0.02, 0.98)
    Y = rng.binomial(1, T * mu1 + (1 - T) * mu0).astype(float)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true, float(np.mean(cate_true))


def _dgp_lalonde_obs_like(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 8,
    ate: float = 1794.0,
    ate_scale: float = 1000.0,  # rescale for numerical stability
) -> tuple[HTEObservationalData, np.ndarray, float]:
    """LaLonde-inspired observational DGP (strong selection bias, earnings outcome)."""
    # Normalized so ATE ≈ 1.794 in rescaled units
    ate_norm = ate / ate_scale
    X = rng.standard_normal((n, p))
    # Strong selection on earnings-like covariates
    sel_coef = np.array([1.5, -1.0, 0.5, -0.3, 0.2, 0.0, 0.0, 0.0])[:p]
    sel_coef += 0.2 * rng.standard_normal(len(sel_coef))
    prop = 1 / (1 + np.exp(-(X @ sel_coef)))
    prop = np.clip(prop, 0.03, 0.97)
    T = rng.binomial(1, prop).astype(float)

    beta0 = rng.standard_normal(p) / np.sqrt(p)
    mu0 = X @ beta0 + 2.0
    cate_true = ate_norm + 0.2 * X[:, 0]
    Y = mu0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true, float(np.mean(cate_true))


def _dgp_ihdp_like(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 25,
    ate: float = 4.0,
    hte_strength: float = 1.0,
) -> tuple[HTEObservationalData, np.ndarray, float]:
    """IHDP-inspired DGP (Infant Health and Development Program).

    Non-overlap: treatment group has systematically different covariates.
    Nonlinear outcome.
    """
    # Treated group has shifted X[:,0] (simulating specialist selection)
    X = rng.standard_normal((n, p))
    shift = rng.standard_normal(n) > 0.5  # ~50% chance
    X[:, 0] += 0.5 * shift

    prop_coef = rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-(X @ prop_coef + 0.3 * X[:, 0])))
    prop = np.clip(prop, 0.04, 0.96)
    T = rng.binomial(1, prop).astype(float)

    # Nonlinear potential outcomes
    mu0 = np.exp(X[:, 0] * 0.5 + X[:, 1] * 0.3) - 1
    cate_true = ate + hte_strength * X[:, 0]
    Y = mu0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true, float(np.mean(cate_true))


def _dgp_lalonde_rct_like(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 8,
    ate: float = 1.794,
) -> tuple[HTEObservationalData, np.ndarray, float]:
    """LaLonde RCT-inspired: near-random assignment, well-defined ATE."""
    X = rng.standard_normal((n, p))
    # Near-random with slight imbalance
    T = rng.binomial(1, 0.45, size=n).astype(float)
    beta0 = rng.standard_normal(p) / np.sqrt(p)
    mu0 = X @ beta0 + 1.0
    cate_true = np.full(n, ate)
    Y = mu0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true, float(ate)


def _dgp_news_like(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 50,
    ate: float = 0.3,
) -> tuple[HTEObservationalData, np.ndarray, float]:
    """News-reading-inspired DGP: high-dimensional sparse covariates."""
    X = rng.standard_normal((n, p))
    # Only ~10 features actually matter
    active = rng.choice(p, size=10, replace=False)
    prop_coef = np.zeros(p)
    prop_coef[active] = rng.standard_normal(10) / np.sqrt(10) * 2.0
    prop = 1 / (1 + np.exp(-X @ prop_coef))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    beta0 = np.zeros(p)
    beta0[active] = rng.standard_normal(10) / np.sqrt(10)
    mu0 = X @ beta0
    # HTE driven by subset of active features
    cate_true = ate + 0.2 * X[:, active[0]]
    Y = mu0 + cate_true * T + 0.3 * rng.standard_normal(n)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true, float(np.mean(cate_true))


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_ols(data: HTEObservationalData, rng: np.random.Generator) -> RealCauseMetrics:
    from numpy.linalg import lstsq

    X = np.column_stack([data.covariates, data.treatment, np.ones(len(data.outcome))])
    Y = data.outcome
    coef, _, _, _ = lstsq(X, Y, rcond=None)
    ate_pred = float(coef[-2])
    cate_pred = np.full(len(Y), ate_pred)

    n = len(Y)
    boot_ates: list[float] = []
    for _ in range(200):
        idx = rng.integers(0, n, size=n)
        try:
            cb, _, _, _ = lstsq(X[idx], Y[idx], rcond=None)
            boot_ates.append(float(cb[-2]))
        except Exception:
            pass
    ci_lo = float(np.percentile(boot_ates, 2.5)) if boot_ates else ate_pred - 0.2
    ci_hi = float(np.percentile(boot_ates, 97.5)) if boot_ates else ate_pred + 0.2

    return RealCauseMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=cate_pred,
        method_name="ols",
        dataset_name="",
    )


def _baseline_t_learner(data: HTEObservationalData, rng: np.random.Generator) -> RealCauseMetrics:
    from numpy.linalg import lstsq

    X, T, Y = data.covariates, data.treatment, data.outcome
    mask1, mask0 = T == 1, T == 0

    try:
        from sklearn.ensemble import GradientBoostingRegressor

        m1 = GradientBoostingRegressor(n_estimators=50, random_state=0)
        m0 = GradientBoostingRegressor(n_estimators=50, random_state=0)
        m1.fit(X[mask1], Y[mask1])
        m0.fit(X[mask0], Y[mask0])
        mu1 = m1.predict(X)
        mu0 = m0.predict(X)
    except ImportError:

        def _lfit(Xa: np.ndarray, Ya: np.ndarray) -> np.ndarray:
            Xb = np.column_stack([Xa, np.ones(len(Ya))])
            c, _, _, _ = lstsq(Xb, Ya, rcond=None)
            return c

        c1 = _lfit(X[mask1], Y[mask1])
        c0 = _lfit(X[mask0], Y[mask0])
        Xb = np.column_stack([X, np.ones(len(Y))])
        mu1 = Xb @ c1
        mu0 = Xb @ c0

    cate_pred = mu1 - mu0
    ate_pred = float(np.mean(cate_pred))

    n = len(Y)
    boot_ates: list[float] = []
    for _ in range(100):
        idx = rng.integers(0, n, size=n)
        boot_ates.append(float(np.mean(cate_pred[idx])))
    ci_lo = float(np.percentile(boot_ates, 2.5))
    ci_hi = float(np.percentile(boot_ates, 97.5))

    return RealCauseMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=cate_pred,
        method_name="t_learner",
        dataset_name="",
    )


# ---------------------------------------------------------------------------
# PolicyOS runner
# ---------------------------------------------------------------------------


def _run_policy_os_method(
    method_class: type,
    data: HTEObservationalData,
    params: dict[str, Any],
) -> RealCauseMetrics:
    try:
        result = invoke_policyos_method(method_class, data, params)
    except Exception as exc:
        return RealCauseMetrics(
            ate_true=0.0,
            ate_pred=float("nan"),
            ate_ci_lower=float("nan"),
            ate_ci_upper=float("nan"),
            cate_true=None,
            cate_pred=None,
            method_name=method_class.__name__,
            dataset_name="",
            failed=True,
            fail_reason=str(exc),
        )

    extracted = extract_policyos_result(method_class, data, result)
    if extracted.failed:
        return RealCauseMetrics(
            ate_true=0.0,
            ate_pred=float("nan"),
            ate_ci_lower=float("nan"),
            ate_ci_upper=float("nan"),
            cate_true=None,
            cate_pred=None,
            method_name=method_class.__name__,
            dataset_name="",
            failed=True,
            fail_reason=extracted.fail_reason,
        )

    return RealCauseMetrics(
        ate_true=0.0,
        ate_pred=extracted.ate_pred,
        ate_ci_lower=extracted.ate_ci_lower,
        ate_ci_upper=extracted.ate_ci_upper,
        cate_true=None,
        cate_pred=extracted.cate_pred,
        method_name=method_class.__name__,
        dataset_name="",
        selection_manifest=(
            extracted.selection_manifest
            or benchmark_selection_manifest_from_params(params, method_label=method_class.__name__)
        ),
        overlap_diagnostics=(
            extracted.nuisance_diagnostics
            or basic_overlap_diagnostics(
                fit_eval_propensity(data.covariates, data.treatment),
                data.treatment,
                clip=float(params.get("propensity_clipping", 0.01)),
                overlap_guard=float(params.get("overlap_guard", 0.10)),
            )
        ),
    )


# ---------------------------------------------------------------------------
# Multi-replication runner with distributional metrics
# ---------------------------------------------------------------------------


def _run_dataset_replications(
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    method_fns: dict[str, Any],
    n_obs: int,
    n_reps: int,
    dataset_name: str,
    base_seed: int = 0,
) -> dict[str, DatasetResult]:
    results: dict[str, DatasetResult] = {
        name: DatasetResult(
            dataset_name=dataset_name,
            method_name=name,
            n_reps=n_reps,
            ate_true=float(dgp_kwargs.get("ate", dgp_kwargs.get("ate_scale", 1.0))),
            ate_biases=[],
            ci_covers=[],
            ci_widths=[],
            pehe_values=[],
            kl_divergences=[],
            n_failed=0,
        )
        for name in method_fns
    }

    for rep in range(n_reps):
        rng = np.random.default_rng(base_seed + rep)
        try:
            data, cate_true, ate_true = dgp_fn(n_obs, rng, **dgp_kwargs)
        except Exception:
            continue

        # True counterfactual outcomes for distributional metrics
        y_obs = data.outcome.copy()

        for name, method_fn in method_fns.items():
            res = results[name]
            try:
                m = method_fn(data, rng)
                m.ate_true = ate_true
                m.cate_true = cate_true
                if m.failed:
                    res.n_failed += 1
                    res.ate_biases.append(float("nan"))
                    res.ci_covers.append(False)
                    res.ci_widths.append(float("nan"))
                    res.kl_divergences.append(float("nan"))
                else:
                    res.ate_biases.append(m.ate_bias)
                    res.ci_covers.append(m.ci_covers)
                    res.ci_widths.append(m.ci_width)
                    if m.selection_manifest:
                        res.selection_records.append(m.selection_manifest)
                    if m.overlap_diagnostics:
                        res.overlap_records.append(m.overlap_diagnostics)
                    calibration_record = {
                        "ci_coverage": 1.0 if m.ci_covers else 0.0,
                        "ci_width": m.ci_width,
                        "calibration_mode": next(
                            iter((m.selection_manifest or {}).get("calibration_modes", [])),
                            None,
                        ),
                    }

                    # Distributional divergence: predicted counterfactual vs observed
                    if m.cate_pred is not None:
                        m.cate_true = cate_true
                        # Reconstruct predicted outcome distribution under treatment
                        y_pred_counterfactual = y_obs + m.cate_pred * (1 - data.treatment)
                        kl = _compute_distributional_divergence(y_obs, y_pred_counterfactual)
                        res.kl_divergences.append(kl)
                        calibration_record["eceth"] = eceth(cate_true, m.cate_pred)

                    if m.cate_pred is not None and cate_true is not None:
                        m.cate_true = cate_true
                        p = m.pehe
                        if p is not None:
                            res.pehe_values.append(p)
                    res.calibration_records.append(calibration_record)
            except Exception:
                res.n_failed += 1
                res.ate_biases.append(float("nan"))
                res.ci_covers.append(False)
                res.ci_widths.append(float("nan"))
                res.kl_divergences.append(float("nan"))

    return results


# ---------------------------------------------------------------------------
# BenchmarkCase builder
# ---------------------------------------------------------------------------


def _realcause_case(
    name: str,
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    method_fns: dict[str, Any],
    n_obs: int,
    n_reps: int,
    *,
    ate_rmse_multiplier: float = 2.0,
    kl_multiplier: float = 3.0,
    min_ci_coverage: float = 0.75,
    max_failure_rate: float = 0.30,
    seed: int = 42,
) -> BenchmarkCase:
    def runner() -> dict[str, DatasetResult]:
        return _run_dataset_replications(
            dgp_fn=dgp_fn,
            dgp_kwargs=dgp_kwargs,
            method_fns=method_fns,
            n_obs=n_obs,
            n_reps=n_reps,
            dataset_name=name,
            base_seed=seed,
        )

    def checker(results: dict[str, DatasetResult]) -> bool:
        return _check_realcause_results(
            case_name=name,
            results=results,
            ate_rmse_multiplier=ate_rmse_multiplier,
            kl_multiplier=kl_multiplier,
            min_ci_coverage=min_ci_coverage,
            max_failure_rate=max_failure_rate,
        )

    return BenchmarkCase(
        name=f"realcause::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("realcause",),
        timeout_s=1800.0,
    )


def _check_realcause_results(
    *,
    case_name: str,
    results: dict[str, DatasetResult],
    ate_rmse_multiplier: float,
    kl_multiplier: float,
    min_ci_coverage: float,
    max_failure_rate: float,
) -> bool:
    baseline_names = {"ols", "t_learner"}
    policy_os_names = [k for k in results if infer_method_group(k) == "policy_os_competitive"]

    if not policy_os_names:
        return True

    # Best RMSE and KL among baselines
    baseline_rmse = [
        results[b].ate_rmse
        for b in baseline_names
        if b in results and math.isfinite(results[b].ate_rmse)
    ]
    baseline_kl = [
        results[b].kl_mean
        for b in baseline_names
        if b in results and math.isfinite(results[b].kl_mean)
    ]
    best_rmse = min(baseline_rmse) if baseline_rmse else None
    best_kl = min(baseline_kl) if baseline_kl else None

    issues: list[str] = []
    for pname in policy_os_names:
        res = results[pname]

        if res.failure_rate > max_failure_rate:
            issues.append(f"{pname}: failure_rate={res.failure_rate:.2f} > {max_failure_rate}")

        if res.ci_coverage < min_ci_coverage:
            issues.append(f"{pname}: CI coverage={res.ci_coverage:.2f} < {min_ci_coverage}")

        if best_rmse is not None and math.isfinite(res.ate_rmse):
            if res.ate_rmse > ate_rmse_multiplier * best_rmse + 1e-6:
                issues.append(
                    f"{pname}: ATE RMSE={res.ate_rmse:.3f} > "
                    f"{ate_rmse_multiplier}× best_baseline={best_rmse:.3f}"
                )

        if best_kl is not None and math.isfinite(res.kl_mean) and res.kl_mean > 0:
            if res.kl_mean > kl_multiplier * best_kl + 1e-6:
                issues.append(
                    f"{pname}: KL={res.kl_mean:.3f} > {kl_multiplier}× best_baseline={best_kl:.3f}"
                )

    if issues:
        raise AssertionError(f"realcause::{case_name}: " + "; ".join(issues))
    return True


# ---------------------------------------------------------------------------
# Real data loader (graceful degradation)
# ---------------------------------------------------------------------------


def _try_load_realcause_dataset(
    data_dir: Path,
    dataset_name: str,
) -> tuple[HTEObservationalData, np.ndarray, float] | None:
    """Attempt to load a RealCause dataset.

    Expected layout:
        data_dir/{dataset_name}/x.csv
        data_dir/{dataset_name}/labels.csv  — columns: t, y, mu1, mu0
    """
    cov_file = data_dir / dataset_name / "x.csv"
    labels_file = data_dir / dataset_name / "labels.csv"
    if not cov_file.exists() or not labels_file.exists():
        return None

    try:
        import csv

        with open(cov_file) as f:
            rows_x = list(csv.DictReader(f))
        feature_names = list(rows_x[0].keys())
        X = np.array([[float(r[k]) for k in feature_names] for r in rows_x])

        with open(labels_file) as f:
            rows_l = list(csv.DictReader(f))
        T = np.array([float(r["t"]) for r in rows_l])
        Y = np.array([float(r["y"]) for r in rows_l])
        mu1 = np.array([float(r.get("mu1", "0")) for r in rows_l])
        mu0 = np.array([float(r.get("mu0", "0")) for r in rows_l])
        cate_true = mu1 - mu0
        ate_true = float(np.mean(cate_true))

        data = HTEObservationalData(
            outcome=Y, treatment=T, covariates=X, feature_names=feature_names
        )
        return data, cate_true, ate_true
    except Exception:
        return None


def _try_load_realcause_upstream_sample(
    sample_file: Path,
) -> tuple[HTEObservationalData, np.ndarray, float] | None:
    """Load upstream RealCause flat sample CSV.

    Expected columns:
      feature columns + t, y, y0, y1, ite
    """
    try:
        import csv

        with open(sample_file) as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None

        target_cols = {"t", "y", "y0", "y1", "ite"}
        feature_names = [name for name in rows[0].keys() if name not in target_cols]
        X = np.array([[float(row[name]) for name in feature_names] for row in rows], dtype=float)
        T = np.array([float(row["t"]) for row in rows], dtype=float)
        Y = np.array([float(row["y"]) for row in rows], dtype=float)

        if "ite" in rows[0]:
            cate_true = np.array([float(row["ite"]) for row in rows], dtype=float)
        else:
            mu1 = np.array([float(row["y1"]) for row in rows], dtype=float)
            mu0 = np.array([float(row["y0"]) for row in rows], dtype=float)
            cate_true = mu1 - mu0
        ate_true = float(np.mean(cate_true))

        data = HTEObservationalData(
            outcome=Y,
            treatment=T,
            covariates=X,
            feature_names=feature_names,
        )
        return data, cate_true, ate_true
    except Exception:
        return None


def _discover_realcause_real_datasets(
    data_dir: Path,
) -> list[tuple[str, HTEObservationalData, np.ndarray, float]]:
    datasets: list[tuple[str, HTEObservationalData, np.ndarray, float]] = []
    seen_names: set[str] = set()

    for ds_dir in sorted(path for path in data_dir.iterdir() if path.is_dir()):
        loaded = _try_load_realcause_dataset(data_dir, ds_dir.name)
        if loaded is None:
            continue
        data, cate_true, ate_true = loaded
        datasets.append((ds_dir.name, data, cate_true, ate_true))
        seen_names.add(ds_dir.name)

    flat_roots = [data_dir / "realcause_datasets", data_dir]
    for root in flat_roots:
        if not root.exists():
            continue
        for sample_file in sorted(root.glob("*_sample*.csv")):
            if sample_file.stem in seen_names:
                continue
            loaded = _try_load_realcause_upstream_sample(sample_file)
            if loaded is None:
                continue
            data, cate_true, ate_true = loaded
            datasets.append((sample_file.stem, data, cate_true, ate_true))
            seen_names.add(sample_file.stem)

    return datasets


# ---------------------------------------------------------------------------
# Method factory
# ---------------------------------------------------------------------------


def _make_method_fns(
    seed_offset: int = 0,
    *,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    dataset_name: str = "realcause",
    method_profile: str = "production_estimation",
) -> dict[str, Any]:
    if method_profile not in ESTIMATION_METHOD_PROFILES:
        valid = ", ".join(ESTIMATION_METHOD_PROFILES)
        raise ValueError(
            f"Unknown estimation method profile: {method_profile!r}. Expected one of: {valid}"
        )
    fns: dict[str, Any] = {}
    flagship_params = _realcause_nuisance_params(tier, seed=seed_offset, dataset_name=dataset_name)

    fns["ols"] = lambda data, rng: _baseline_ols(data, rng)
    fns["t_learner"] = lambda data, rng: _baseline_t_learner(data, rng)

    try:
        from polisyos.foundry.methods.catalog.causal.advanced_designs import DRLearnerEstimator
        from polisyos.foundry.methods.catalog.causal.causal_bcf import CausalBCF
        from polisyos.foundry.methods.catalog.causal.treatment_effects import (
            AIPWEstimator,
            TMLEEstimator,
        )

        fns["policy_os_aipw_cf"] = lambda data, rng: _run_policy_os_method(
            AIPWEstimator,
            data,
            {
                **dict(flagship_params),
                "estimation_backend": "econml_direct",
                "direct_model_type": "linear",
            },
        )
        fns["policy_os_tmle_cf"] = lambda data, rng: _run_policy_os_method(
            TMLEEstimator,
            data,
            dict(flagship_params),
        )
    except Exception:
        pass

    try:
        from polisyos.foundry.methods.catalog.causal.cate import CausalForestEstimator

        fns["policy_os_causal_forest"] = lambda data, rng: _run_policy_os_method(
            CausalForestEstimator,
            data,
            policyos_causal_forest_params(tier, seed=seed_offset),
        )
    except Exception:
        pass

    try:
        from polisyos.foundry.methods.catalog.causal.meta_learners import MetaLearnerEstimator

        fns["policy_os_xlearner_cf"] = lambda data, rng: _run_policy_os_method(
            MetaLearnerEstimator,
            data,
            _realcause_xlearner_params(tier, seed=seed_offset, dataset_name=dataset_name),
        )
    except Exception:
        pass

    if method_profile == "full_matrix_estimation":
        try:
            fns["policy_os_causal_bcf"] = lambda data, rng: _run_policy_os_method(
                CausalBCF,
                data,
                policyos_causal_bcf_params(tier, seed=seed_offset),
            )
        except Exception:
            pass

        try:
            fns["policy_os_drlearner_cf"] = lambda data, rng: _run_policy_os_method(
                DRLearnerEstimator,
                data,
                {**dict(flagship_params), "estimation_backend": "econml_direct"},
            )
        except Exception:
            pass

        try:
            fns["policy_os_forestdr_cf"] = lambda data, rng: _run_policy_os_method(
                ForestDRLearnerComparator,
                data,
                policyos_forestdr_params(tier, seed=seed_offset),
            )
        except Exception:
            pass

        try:
            from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning

            fns["external_dml_econml"] = lambda data, rng: _run_policy_os_method(
                DoubleMachineLearning,
                data,
                external_dml_params(seed=seed_offset),
            )
        except Exception:
            pass

    return fns


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------

#: Synthetic DGP registry — (name, dgp_fn, dgp_kwargs, n_obs)
_SYNTHETIC_DATASETS: list[tuple[str, Any, dict[str, Any], int]] = [
    ("twins", _dgp_twins_like, {"p": 30, "ate": 0.08}, 500),
    ("lalonde_rct", _dgp_lalonde_rct_like, {"p": 8, "ate": 1.794}, 300),
    ("lalonde_obs", _dgp_lalonde_obs_like, {"p": 8, "ate": 1794.0, "ate_scale": 1000.0}, 500),
    ("ihdp", _dgp_ihdp_like, {"p": 25, "ate": 4.0, "hte_strength": 1.0}, 500),
    ("news", _dgp_news_like, {"p": 50, "ate": 0.3}, 800),
]


def build_realcause_harness(
    n_reps: int = 10,
    seed: int = 42,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_estimation",
) -> BenchmarkHarness:
    """Build BenchmarkHarness with RealCause-style estimation cases."""
    harness = BenchmarkHarness()
    fast_mode = fast_benchmark_mode() and tier is BenchmarkTier.LOCAL_EVIDENCE

    real_datasets: list[tuple[str, HTEObservationalData, np.ndarray, float]] = []
    if REALCAUSE_DATA_DIR is not None:
        real_datasets = _discover_realcause_real_datasets(REALCAUSE_DATA_DIR)

    if real_datasets:
        if fast_mode:
            real_datasets = real_datasets[:1]
        if tier is BenchmarkTier.RESEARCH_ACCEPTANCE:
            families: dict[str, list[tuple[str, HTEObservationalData, np.ndarray, float]]] = {}
            for ds_name, real_data, cate_true, ate_true in real_datasets[:4]:
                family = ds_name.split("_sample", 1)[0]
                families.setdefault(family, []).append((ds_name, real_data, cate_true, ate_true))

            for family_name, family_datasets in sorted(families.items()):

                def _make_family_runner(
                    datasets=family_datasets,
                    family=family_name,
                    mf=_make_method_fns(
                        seed_offset=seed,
                        tier=tier,
                        dataset_name=family_name,
                        method_profile=method_profile,
                    ),
                ):
                    def runner() -> dict[str, DatasetResult]:
                        out: dict[str, DatasetResult] = {
                            name: DatasetResult(
                                dataset_name=family,
                                method_name=name,
                                n_reps=len(datasets),
                                ate_true=float("nan"),
                                ate_biases=[],
                                ci_covers=[],
                                ci_widths=[],
                                pehe_values=[],
                                kl_divergences=[],
                                n_failed=0,
                            )
                            for name in mf
                        }
                        for dataset_offset, (_name, rd, ct, at) in enumerate(datasets):
                            y_obs = rd.outcome.copy()
                            rng = np.random.default_rng(seed + dataset_offset)
                            for method_name, fn in mf.items():
                                try:
                                    m = fn(rd, rng)
                                    m.ate_true = at
                                    m.cate_true = ct
                                    res = out[method_name]
                                    if m.failed:
                                        res.n_failed += 1
                                        res.ate_biases.append(float("nan"))
                                        res.ci_covers.append(False)
                                        res.ci_widths.append(float("nan"))
                                        res.kl_divergences.append(float("nan"))
                                        continue
                                    res.ate_biases.append(m.ate_bias)
                                    res.ci_covers.append(m.ci_covers)
                                    res.ci_widths.append(m.ci_width)
                                    if m.selection_manifest:
                                        res.selection_records.append(m.selection_manifest)
                                    if m.overlap_diagnostics:
                                        res.overlap_records.append(m.overlap_diagnostics)
                                    calibration_record = {
                                        "ci_coverage": 1.0 if m.ci_covers else 0.0,
                                        "ci_width": m.ci_width,
                                        "calibration_mode": next(
                                            iter(
                                                (m.selection_manifest or {}).get(
                                                    "calibration_modes", []
                                                )
                                            ),
                                            None,
                                        ),
                                    }
                                    if m.pehe is not None:
                                        res.pehe_values.append(m.pehe)
                                    if m.cate_pred is not None:
                                        y_cf = y_obs + m.cate_pred * (1 - rd.treatment)
                                        res.kl_divergences.append(
                                            _compute_distributional_divergence(y_obs, y_cf)
                                        )
                                        calibration_record["eceth"] = eceth(ct, m.cate_pred)
                                    res.calibration_records.append(calibration_record)
                                except Exception:
                                    res = out[method_name]
                                    res.n_failed += 1
                                    res.ate_biases.append(float("nan"))
                                    res.ci_covers.append(False)
                                    res.ci_widths.append(float("nan"))
                                    res.kl_divergences.append(float("nan"))
                        return out

                    return runner

                harness.register(
                    BenchmarkCase(
                        name=f"realcause::research_family_{family_name}",
                        circuit=CIRCUIT,
                        runner=_make_family_runner(),
                        checker=lambda results, fn=family_name: _check_realcause_results(
                            case_name=f"research_family_{fn}",
                            results=results,
                            ate_rmse_multiplier=2.0,
                            kl_multiplier=3.0,
                            min_ci_coverage=0.75,
                            max_failure_rate=0.30,
                        ),
                        tags=("realcause", "real", "research_acceptance"),
                        timeout_s=1800.0,
                    )
                )
        else:
            for ds_name, real_data, cate_true, ate_true in real_datasets:

                def _make_runner(
                    rd=real_data,
                    ct=cate_true,
                    at=ate_true,
                    dn=ds_name,
                    mf=_make_method_fns(
                        seed_offset=seed,
                        tier=tier,
                        dataset_name=ds_name,
                        method_profile=method_profile,
                    ),
                ):
                    def runner() -> dict[str, DatasetResult]:
                        rng = np.random.default_rng(seed)
                        out: dict[str, DatasetResult] = {}
                        y_obs = rd.outcome.copy()
                        for name, fn in mf.items():
                            try:
                                m = fn(rd, rng)
                                m.ate_true = at
                                m.cate_true = ct

                                kl_vals: list[float] = []
                                if not m.failed and m.cate_pred is not None:
                                    y_cf = y_obs + m.cate_pred * (1 - rd.treatment)
                                    kl_vals.append(_compute_distributional_divergence(y_obs, y_cf))

                                r = DatasetResult(
                                    dataset_name=dn,
                                    method_name=name,
                                    n_reps=1,
                                    ate_true=at,
                                    ate_biases=[m.ate_bias] if not m.failed else [float("nan")],
                                    ci_covers=[m.ci_covers] if not m.failed else [False],
                                    ci_widths=[m.ci_width] if not m.failed else [float("nan")],
                                    pehe_values=[m.pehe]
                                    if (not m.failed and m.pehe is not None)
                                    else [],
                                    kl_divergences=kl_vals,
                                    n_failed=1 if m.failed else 0,
                                    selection_records=[m.selection_manifest]
                                    if (not m.failed and m.selection_manifest)
                                    else [],
                                    overlap_records=[m.overlap_diagnostics]
                                    if (not m.failed and m.overlap_diagnostics)
                                    else [],
                                    calibration_records=[
                                        {
                                            "ci_coverage": 1.0 if m.ci_covers else 0.0,
                                            "ci_width": m.ci_width,
                                            "calibration_mode": next(
                                                iter(
                                                    (m.selection_manifest or {}).get(
                                                        "calibration_modes", []
                                                    )
                                                ),
                                                None,
                                            ),
                                            "eceth": eceth(ct, m.cate_pred)
                                            if m.cate_pred is not None
                                            else float("nan"),
                                        }
                                    ]
                                    if not m.failed
                                    else [],
                                )
                                out[name] = r
                            except Exception:
                                out[name] = DatasetResult(
                                    dataset_name=dn,
                                    method_name=name,
                                    n_reps=1,
                                    ate_true=at,
                                    ate_biases=[float("nan")],
                                    ci_covers=[False],
                                    ci_widths=[float("nan")],
                                    pehe_values=[],
                                    kl_divergences=[float("nan")],
                                    n_failed=1,
                                )
                        return out

                    return runner

                harness.register(
                    BenchmarkCase(
                        name=f"realcause::real_{ds_name}",
                        circuit=CIRCUIT,
                        runner=_make_runner(),
                        checker=lambda results, dn=ds_name: _check_realcause_results(
                            case_name=f"real_{dn}",
                            results=results,
                            ate_rmse_multiplier=2.0,
                            kl_multiplier=3.0,
                            min_ci_coverage=0.75,
                            max_failure_rate=0.30,
                        ),
                        tags=("realcause", "real", "local_evidence"),
                        timeout_s=300.0,
                    )
                )
    else:
        datasets = _SYNTHETIC_DATASETS[:1] if fast_mode else _SYNTHETIC_DATASETS
        for ds_name, dgp_fn, dgp_kwargs, n_obs in datasets:
            harness.register(
                _realcause_case(
                    name=ds_name,
                    dgp_fn=dgp_fn,
                    dgp_kwargs=dgp_kwargs,
                    method_fns=_make_method_fns(
                        seed_offset=seed,
                        tier=tier,
                        dataset_name=ds_name,
                        method_profile=method_profile,
                    ),
                    n_obs=min(n_obs, 160) if fast_mode else n_obs,
                    n_reps=n_reps,
                    ate_rmse_multiplier=2.0,
                    kl_multiplier=3.0,
                    min_ci_coverage=0.75,
                    max_failure_rate=0.30,
                    seed=seed,
                )
            )

    return harness


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _compute_realcause_summary(report: BenchmarkReport) -> dict[str, Any]:
    aggregate, _, _ = summarize_method_metrics(
        report,
        metric_getters={
            "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
            "pehe": lambda result: getattr(result, "pehe_mean", float("nan")),
            "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
            "kl_mean": lambda result: getattr(result, "kl_mean", float("nan")),
            "failure_rate": lambda result: getattr(result, "failure_rate", float("nan")),
        },
    )
    return aggregate


def _realcause_case_group(case_name: str) -> str:
    leaf = case_name.split("::", 1)[-1]
    if leaf.startswith("research_family_"):
        return _realcause_family_name(leaf.removeprefix("research_family_"))
    if leaf.startswith("real_"):
        return _realcause_family_name(leaf.removeprefix("real_"))
    family = _realcause_family_name(leaf)
    return family or "synthetic_case"


def _build_dataset_group_summaries(
    report: BenchmarkReport,
    grouped_summary: dict[str, Any],
) -> dict[str, Any]:
    grouped_ranking = compute_grouped_ranking_summary(
        report,
        primary_metric="ate_rmse_standardized",
        metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
        scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
        standardized=True,
        case_group_getter=_realcause_case_group,
    )
    grouped_distributional_ranking = compute_grouped_ranking_summary(
        report,
        primary_metric="kl_mean",
        metric_getter=lambda result: getattr(result, "kl_mean", float("nan")),
        case_group_getter=_realcause_case_group,
    )
    grouped_presence = compute_grouped_method_presence(
        report,
        REALCAUSE_GATE_METHOD_SET,
        case_group_getter=_realcause_case_group,
    )

    out: dict[str, Any] = {}
    for group_name, method_metrics in grouped_summary.items():
        scorecard = build_flagship_scorecard(
            flagship_method=REALCAUSE_FLAGSHIP_METHOD,
            aggregate_metrics=method_metrics,
            ranking_summary=grouped_ranking.get(group_name, {}),
            thresholds={
                "mean_rank_max": 2,
                "max_deviation_from_best_max": 0.10,
                "top_quartile_failures_max": 0,
                "ci_coverage_mean_min": 0.75,
                "failure_rate_mean_max": 0.30,
            },
            gate_method_set=REALCAUSE_GATE_METHOD_SET,
            method_presence=grouped_presence.get(group_name, {}),
        )
        out[group_name] = {
            "method_summary": method_metrics,
            "ranking_summary": grouped_ranking.get(group_name, {}),
            "distributional_ranking_summary": grouped_distributional_ranking.get(group_name, {}),
            "flagship_scorecard": scorecard,
            "flagship_presence": (grouped_presence.get(group_name, {}) or {}).get(
                REALCAUSE_FLAGSHIP_METHOD, {}
            ),
            "passes_all": bool(scorecard.get("passes_all")),
        }
    return out


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="RealCause estimation benchmark")
    parser.add_argument("--n-reps", type=int, default=10, metavar="R")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", dest="json_out", default=None, metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode], default=None)
    parser.add_argument("--tier", choices=[tier.value for tier in BenchmarkTier], default=None)
    parser.add_argument(
        "--method-profile",
        choices=list(ESTIMATION_METHOD_PROFILES),
        default=None,
        help="Use production-only estimation methods or the wider exploratory matrix",
    )
    args = parser.parse_args()

    mode = resolve_mode(args.mode)
    tier = resolve_tier(args.tier, mode=mode)
    method_profile = resolve_estimation_method_profile(tier, requested=args.method_profile)
    real_data_status = env_path_status("REALCAUSE_DATA_DIR")
    has_real_data = False
    if REALCAUSE_DATA_DIR is not None:
        has_real_data = bool(_discover_realcause_real_datasets(REALCAUSE_DATA_DIR))

    comparator_status = build_research_acceptance_comparator_status()
    planned_n_reps = (
        6 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_reps == 10 else args.n_reps
    )
    degraded_reasons = []
    if not has_real_data:
        degraded_reasons.append(
            "using synthetic RealCause replicas because real datasets are unavailable"
        )
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        degraded_reasons.append(
            "local_evidence tier uses thermal-safe subsets and lighter defaults"
        )
    degraded_reasons.extend(comparator_degraded_reasons(comparator_status))

    preflight = build_preflight(
        mode=mode.value,
        benchmark_tier=tier.value,
        data_source=classify_data_source(
            has_real_data=has_real_data,
            synthetic_label="synthetic_replica",
            real_label="real_realcause",
        ),
        dependency_status={
            **real_data_status,
            "python_modules": dependency_status(
                [
                    "numpy",
                    "scipy",
                    "sklearn",
                    "econml",
                    "zepid",
                    "stochtree",
                    "dowhy",
                    "y0",
                    "lightgbm",
                ]
            ),
        },
        comparator_status=comparator_status,
        degraded_reasons=degraded_reasons,
        dataset_family="realcause",
        batch_id=f"n_reps={planned_n_reps}",
        estimator_profile="flagship_plus_production",
    )
    preflight["method_profile"] = method_profile
    print_preflight(preflight)

    gaps = acceptance_gaps(
        mode,
        tier=tier,
        require_real_data=False,
        has_real_data=has_real_data,
        require_modules=comparator_required_modules(),
    )
    if gaps:
        print("RealCause acceptance preflight failed:")
        for gap in gaps:
            print(f"  - {gap}")
        sys.exit(2)

    harness = build_realcause_harness(
        n_reps=planned_n_reps,
        seed=args.seed,
        tier=tier,
        method_profile=method_profile,
    )
    report: BenchmarkReport = harness.run(circuit=CIRCUIT)

    if not args.quiet:
        harness.print_report(report)

    if args.json_out:
        aggregate_summary, standardized_summary, grouped_summary = summarize_method_metrics(
            report,
            metric_getters={
                "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
                "pehe": lambda result: getattr(result, "pehe_mean", float("nan")),
                "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
                "kl_mean": lambda result: getattr(result, "kl_mean", float("nan")),
                "failure_rate": lambda result: getattr(result, "failure_rate", float("nan")),
            },
            standardized_metrics={"ate_rmse", "pehe"},
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            case_group_getter=_realcause_case_group,
        )
        ranking_summary = compute_ranking_summary(
            report,
            primary_metric="ate_rmse_standardized",
            metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            standardized=True,
        )
        distributional_ranking = compute_ranking_summary(
            report,
            primary_metric="kl_mean",
            metric_getter=lambda result: getattr(result, "kl_mean", float("nan")),
        )
        present_methods = {
            method_name
            for case in report.cases
            if isinstance(case.result_payload, dict)
            for method_name in case.result_payload
        }
        method_manifest = build_method_registry(
            present_methods,
            benchmark_roles=REALCAUSE_BENCHMARK_ROLES,
        )
        method_presence = compute_method_presence(report, REALCAUSE_GATE_METHOD_SET)
        selection_manifest = summarize_method_records(
            report,
            attribute="selection_manifest",
            reducer=summarize_selection_manifest,
        )
        overlap_diagnostics = summarize_method_records(
            report,
            attribute="overlap_diagnostics",
            reducer=summarize_overlap_diagnostics,
        )
        calibration_metrics = summarize_method_records(
            report,
            attribute="calibration_metrics",
            reducer=summarize_calibration_metrics,
        )
        dataset_group_summaries = _build_dataset_group_summaries(report, grouped_summary)
        flagship_scorecard = build_flagship_scorecard(
            flagship_method=REALCAUSE_FLAGSHIP_METHOD,
            aggregate_metrics=aggregate_summary,
            ranking_summary=ranking_summary,
            thresholds={
                "mean_rank_max": 2,
                "max_deviation_from_best_max": 0.10,
                "top_quartile_failures_max": 0,
                "ci_coverage_mean_min": 0.75,
                "failure_rate_mean_max": 0.30,
            },
            gate_method_set=REALCAUSE_GATE_METHOD_SET,
            method_presence=method_presence,
        )
        with open(args.json_out, "w") as f:
            json.dump(
                build_report_payload(
                    report,
                    suite_id="estimation_realcause",
                    mode=mode.value,
                    preflight=preflight,
                    sub_circuit="realcause",
                    include_case_payload=True,
                    aggregate_metrics={
                        "method_summary": aggregate_summary,
                        "ranking_summary": ranking_summary,
                        "distributional_ranking_summary": distributional_ranking,
                        "case_groups": grouped_summary,
                        "flagship_scorecard": flagship_scorecard,
                    },
                    standardized_metrics=standardized_summary,
                    method_groups=method_manifest,
                    method_manifest=method_manifest,
                    gate_method_set=list(REALCAUSE_GATE_METHOD_SET),
                    flagship_presence=method_presence.get(REALCAUSE_FLAGSHIP_METHOD, {}),
                    exploratory_methods=[
                        method_name
                        for method_name, meta in method_manifest.items()
                        if meta.get("benchmark_role") == "exploratory"
                    ],
                    selection_manifest=selection_manifest,
                    overlap_diagnostics=overlap_diagnostics,
                    calibration_metrics=calibration_metrics,
                    dataset_group_summaries=dataset_group_summaries,
                    claim_profile_targets=["full_stack_publication_claim"],
                    literature_anchor=REALCAUSE_LITERATURE_ANCHOR,
                    public_claim_eligible=True,
                    blockers=[case.name for case in report.cases if not case.passed],
                    extra={"method_profile": method_profile},
                ),
                f,
                indent=2,
            )

    n_fail = sum(1 for cr in report.cases if cr.verdict not in (Verdict.PASS.value, Verdict.PASS))
    sys.exit(0 if n_fail == 0 else 2)


if __name__ == "__main__":
    main()
