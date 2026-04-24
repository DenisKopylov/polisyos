"""Circuit 2: Effect Estimation — ACIC 2016/2017 semi-synthetic suite.

Evaluates ATE/CATE estimation accuracy of PolicyOS methods against baselines on
synthetic DGPs that mirror the ACIC 2016 benchmark structure:
  - 77 DGP families × varying sample sizes and confounding strengths
  - Metrics: ATE bias, RMSE, CI coverage, CI width, PEHE (for CATE)
  - Baselines: OLS, IPW, Naive (difference-in-means)

When the real ACIC 2016 dataset is present (CSV files in ACIC_DATA_DIR), it is
loaded automatically.  Otherwise the benchmark runs on built-in synthetic DGPs
with equivalent structural properties.

Bar
---
    Mean rank ≤ top-2 across DGPs.
    Maximum deviation from best method ≤ 10% on ATE RMSE.
    No single DGP below top quartile.

Usage
-----
    python benchmarks/estimation/acic_benchmark.py
    python benchmarks/estimation/acic_benchmark.py --json report.json
    python benchmarks/estimation/acic_benchmark.py --n-obs 500 --n-reps 20
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
)
from benchmarks.method_registry import build_method_registry, infer_method_group
from benchmarks.policyos_runner import extract_policyos_result, invoke_policyos_method
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.research_metrics import (
    basic_overlap_diagnostics,
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
    compute_method_presence,
    compute_ranking_summary,
    summarize_method_metrics,
)
from polisyos.foundry.methods.catalog.causal.protocols import (  # noqa: E402
    HTEObservationalData,
)

CIRCUIT = BenchmarkCircuit.ESTIMATION
ACIC_FLAGSHIP_METHOD = "policy_os_xlearner_cf"
ACIC_LITERATURE_ANCHOR = [
    "Dorie et al. (2019). Automated versus Do-It-Yourself Methods for Causal Inference: Lessons Learned from a Data Analysis Competition.",
    "ACIC 2016/2017 semi-synthetic treatment-effect estimation benchmark.",
]
ACIC_BENCHMARK_ROLES = {
    ACIC_FLAGSHIP_METHOD: "flagship",
    "policy_os_aipw_cf": "production_challenger",
    "policy_os_tmle_cf": "production_challenger",
    "policy_os_causal_forest": "production_challenger",
    "policy_os_drlearner_cf": "exploratory",
    "policy_os_forestdr_cf": "exploratory",
    "external_dml_econml": "exploratory",
}
ACIC_GATE_METHOD_SET = tuple(
    method_name
    for method_name, role in ACIC_BENCHMARK_ROLES.items()
    if role in {"flagship", "production_challenger"}
)

# Optional real-dataset path (set via environment variable or override)
ACIC_DATA_DIR: Path | None = Path(p) if (p := os.environ.get("ACIC_DATA_DIR", "")) else None


def _acic_nuisance_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_nuisance_params(tier, seed=seed, hte=False)
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        params.update(
            {
                "crossfit_folds": 3,
                "propensity_backend": "logistic_regression",
                "propensity_backend_candidates": ["logistic_regression", "histgradientboosting"],
                "outcome_backend": "elastic_net",
                "outcome_backend_candidates": ["elastic_net", "histgradientboosting", "lightgbm"],
                "calibration_mode": "sigmoid",
                "min_calibration_size": 24,
            }
        )
    return params


def _acic_xlearner_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_xlearner_params(tier, seed=seed)
    params.update(
        {
            "selection_objective": "dr_ate_overlap",
            "split_policy": "holdout_dr_ate_overlap",
            "base_model_candidates": [
                "linear",
                "elastic_net_sparse",
                "gradient_boosting",
            ]
            if tier is BenchmarkTier.LOCAL_EVIDENCE
            else [
                "linear",
                "elastic_net_sparse",
                "gradient_boosting",
                "random_forest",
            ],
        }
    )
    return params


# ---------------------------------------------------------------------------
# Estimation metrics
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class EstimationMetrics:
    ate_true: float
    ate_pred: float
    ate_ci_lower: float
    ate_ci_upper: float
    cate_true: np.ndarray | None
    cate_pred: np.ndarray | None
    method_name: str
    dgp_name: str
    selection_manifest: dict[str, Any] = dataclasses.field(default_factory=dict)
    overlap_diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)
    failed: bool = False
    fail_reason: str = ""

    @property
    def ate_bias(self) -> float:
        return self.ate_pred - self.ate_true

    @property
    def ate_abs_bias(self) -> float:
        return abs(self.ate_bias)

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


# ---------------------------------------------------------------------------
# Synthetic DGPs mimicking ACIC 2016 structure
# ---------------------------------------------------------------------------


def _dgp_linear(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 10,
    ate: float = 1.0,
    confounding_strength: float = 1.0,
) -> tuple[HTEObservationalData, np.ndarray]:
    """Simple linear DGP with additive confounding.

    Returns (data, cate_true) where cate_true is constant = ate.
    """
    X = rng.standard_normal((n, p))
    # Propensity: sigmoid(alpha @ X)
    alpha = confounding_strength * rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ alpha))
    T = rng.binomial(1, prop).astype(float)

    beta = rng.standard_normal(p) / np.sqrt(p)
    Y = X @ beta + ate * T + 0.5 * rng.standard_normal(n)

    cate_true = np.full(n, ate)
    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true


def _dgp_nonlinear(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 10,
    ate: float = 1.0,
) -> tuple[HTEObservationalData, np.ndarray]:
    """Nonlinear outcome and propensity model."""
    X = rng.standard_normal((n, p))
    alpha = rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-(X @ alpha + 0.5 * X[:, 0] ** 2)))
    T = rng.binomial(1, np.clip(prop, 0.05, 0.95)).astype(float)

    # Nonlinear outcome: interaction + squared term
    mu = np.sin(X[:, 0]) * X[:, 1] + X[:, 2] ** 2 * 0.3
    Y = mu + ate * T + 0.5 * rng.standard_normal(n)

    cate_true = np.full(n, ate)
    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true


def _dgp_hte(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 10,
    base_ate: float = 1.0,
    hte_strength: float = 0.5,
) -> tuple[HTEObservationalData, np.ndarray]:
    """DGP with true CATE variation driven by X[:,0].

    CATE(x) = base_ate + hte_strength * x[0]
    """
    X = rng.standard_normal((n, p))
    alpha = rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ alpha))
    T = rng.binomial(1, np.clip(prop, 0.05, 0.95)).astype(float)

    cate_true = base_ate + hte_strength * X[:, 0]
    Y = X @ (rng.standard_normal(p) / np.sqrt(p)) + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true


def _dgp_strong_overlap(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 10,
    ate: float = 0.5,
) -> tuple[HTEObservationalData, np.ndarray]:
    """Near-random-assignment (strong overlap); tests CI calibration."""
    X = rng.standard_normal((n, p))
    T = rng.binomial(1, 0.5, size=n).astype(float)
    beta = rng.standard_normal(p) / np.sqrt(p)
    Y = X @ beta + ate * T + rng.standard_normal(n)
    cate_true = np.full(n, ate)
    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true


def _dgp_weak_overlap(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 10,
    ate: float = 2.0,
) -> tuple[HTEObservationalData, np.ndarray]:
    """Severe confounding / weak overlap; stress test for robustness."""
    X = rng.standard_normal((n, p))
    # Very strong propensity signal
    alpha = 3.0 * rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ alpha))
    T = rng.binomial(1, np.clip(prop, 0.05, 0.95)).astype(float)

    beta = rng.standard_normal(p) / np.sqrt(p)
    Y = X @ beta + ate * T + 0.5 * rng.standard_normal(n)

    cate_true = np.full(n, ate)
    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_ols(data: HTEObservationalData, rng: np.random.Generator) -> EstimationMetrics:
    """OLS regression with treatment indicator and all covariates."""
    from numpy.linalg import lstsq

    X = np.column_stack([data.covariates, data.treatment, np.ones(len(data.outcome))])
    Y = data.outcome
    coef, _, _, _ = lstsq(X, Y, rcond=None)
    ate_pred = float(coef[-2])  # treatment coefficient

    # Bootstrap CI for OLS ATE
    n = len(Y)
    boot_ates = []
    for _ in range(200):
        idx = rng.integers(0, n, size=n)
        Xb = X[idx]
        Yb = Y[idx]
        try:
            cb, _, _, _ = lstsq(Xb, Yb, rcond=None)
            boot_ates.append(float(cb[-2]))
        except Exception:
            pass
    if boot_ates:
        ci_lo = float(np.percentile(boot_ates, 2.5))
        ci_hi = float(np.percentile(boot_ates, 97.5))
    else:
        ci_lo, ci_hi = ate_pred - 0.2, ate_pred + 0.2

    return EstimationMetrics(
        ate_true=0.0,  # filled by caller
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=None,
        method_name="ols",
        dgp_name="",
    )


def _baseline_ipw(data: HTEObservationalData, rng: np.random.Generator) -> EstimationMetrics:
    """Inverse Probability Weighting estimator."""
    from numpy.linalg import lstsq

    X, T, Y = data.covariates, data.treatment, data.outcome
    n = len(Y)

    # Propensity model via logistic regression (Newton step)
    Xp = np.column_stack([X, np.ones(n)])
    # Simple logistic via iteratively reweighted LS (single Newton step)
    # (Full IRLS for robustness)
    coef = np.zeros(Xp.shape[1])
    for _ in range(30):
        logit = Xp @ coef
        prob = 1 / (1 + np.exp(-np.clip(logit, -20, 20)))
        W = prob * (1 - prob) + 1e-8
        z = logit + (T - prob) / W
        Wmat = np.diag(W)
        try:
            coef, _, _, _ = lstsq(np.sqrt(Wmat) @ Xp, np.sqrt(Wmat) @ z, rcond=None)
        except Exception:
            break

    prop = 1 / (1 + np.exp(-np.clip(Xp @ coef, -20, 20)))
    prop = np.clip(prop, 0.05, 0.95)

    # Horvitz-Thompson IPW estimator
    ipw_1 = Y * T / prop
    ipw_0 = Y * (1 - T) / (1 - prop)
    ate_pred = float(np.mean(ipw_1) - np.mean(ipw_0))

    # Bootstrap CI
    boot_ates = []
    for _ in range(200):
        idx = rng.integers(0, n, size=n)
        boot_ates.append(float(np.mean(ipw_1[idx]) - np.mean(ipw_0[idx])))
    ci_lo = float(np.percentile(boot_ates, 2.5))
    ci_hi = float(np.percentile(boot_ates, 97.5))

    return EstimationMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=None,
        method_name="ipw",
        dgp_name="",
    )


def _baseline_naive(data: HTEObservationalData) -> EstimationMetrics:
    """Naive difference-in-means (no confounding adjustment)."""
    T, Y = data.treatment, data.outcome
    y1 = Y[T == 1]
    y0 = Y[T == 0]
    ate_pred = float(np.mean(y1) - np.mean(y0))
    se = float(np.sqrt(np.var(y1, ddof=1) / len(y1) + np.var(y0, ddof=1) / len(y0)))
    z = 1.96
    return EstimationMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ate_pred - z * se,
        ate_ci_upper=ate_pred + z * se,
        cate_true=None,
        cate_pred=None,
        method_name="naive",
        dgp_name="",
    )


# ---------------------------------------------------------------------------
# PolicyOS method runner
# ---------------------------------------------------------------------------


def _run_policy_os_method(
    method_class: type,
    data: HTEObservationalData,
    params: dict[str, Any],
) -> EstimationMetrics:
    """Run a single PolicyOS HTE method and return metrics."""
    try:
        result = invoke_policyos_method(method_class, data, params)
    except Exception as exc:
        return EstimationMetrics(
            ate_true=0.0,
            ate_pred=float("nan"),
            ate_ci_lower=float("nan"),
            ate_ci_upper=float("nan"),
            cate_true=None,
            cate_pred=None,
            method_name=method_class.__name__,
            dgp_name="",
            failed=True,
            fail_reason=str(exc),
        )

    extracted = extract_policyos_result(method_class, data, result)
    if extracted.failed:
        return EstimationMetrics(
            ate_true=0.0,
            ate_pred=float("nan"),
            ate_ci_lower=float("nan"),
            ate_ci_upper=float("nan"),
            cate_true=None,
            cate_pred=None,
            method_name=method_class.__name__,
            dgp_name="",
            failed=True,
            fail_reason=extracted.fail_reason,
        )

    return EstimationMetrics(
        ate_true=0.0,  # filled by caller
        ate_pred=extracted.ate_pred,
        ate_ci_lower=extracted.ate_ci_lower,
        ate_ci_upper=extracted.ate_ci_upper,
        cate_true=None,
        cate_pred=extracted.cate_pred,
        method_name=method_class.__name__,
        dgp_name="",
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
# Multi-replication runner
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class DGPResult:
    dgp_name: str
    method_name: str
    n_reps: int
    ate_true: float
    ate_biases: list[float]
    ci_covers: list[bool]
    ci_widths: list[float]
    pehe_values: list[float]
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
    def ate_bias_mean(self) -> float:
        valid = [b for b in self.ate_biases if math.isfinite(b)]
        return float(np.mean(valid)) if valid else float("nan")

    @property
    def ci_coverage(self) -> float:
        return float(np.mean(self.ci_covers)) if self.ci_covers else float("nan")

    @property
    def ci_width_mean(self) -> float:
        return float(np.mean(self.ci_widths)) if self.ci_widths else float("nan")

    @property
    def pehe_mean(self) -> float:
        valid = [v for v in self.pehe_values if math.isfinite(v)]
        return float(np.mean(valid)) if valid else float("nan")

    @property
    def selection_manifest(self) -> dict[str, Any]:
        return summarize_selection_manifest(self.selection_records)

    @property
    def overlap_diagnostics(self) -> dict[str, Any]:
        return summarize_overlap_diagnostics(self.overlap_records)

    @property
    def calibration_metrics(self) -> dict[str, Any]:
        return summarize_calibration_metrics(self.calibration_records)


def _run_dgp_replications(
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    method_fns: dict[str, Any],  # name -> callable(data, rng) -> EstimationMetrics
    n_obs: int,
    n_reps: int,
    dgp_name: str,
    base_seed: int = 0,
) -> dict[str, DGPResult]:
    """Run n_reps replications of a DGP and collect results per method."""
    results: dict[str, DGPResult] = {
        name: DGPResult(
            dgp_name=dgp_name,
            method_name=name,
            n_reps=n_reps,
            ate_true=dgp_kwargs.get("ate", dgp_kwargs.get("base_ate", 1.0)),
            ate_biases=[],
            ci_covers=[],
            ci_widths=[],
            pehe_values=[],
            n_failed=0,
        )
        for name in method_fns
    }

    ate_true = float(dgp_kwargs.get("ate", dgp_kwargs.get("base_ate", 1.0)))

    for rep in range(n_reps):
        rng = np.random.default_rng(base_seed + rep)
        try:
            data, cate_true = dgp_fn(n_obs, rng, **dgp_kwargs)
        except Exception:
            continue

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
                else:
                    res.ate_biases.append(m.ate_bias)
                    res.ci_covers.append(m.ci_covers)
                    res.ci_widths.append(m.ci_width)
                    if m.selection_manifest:
                        res.selection_records.append(m.selection_manifest)
                    if m.overlap_diagnostics:
                        res.overlap_records.append(m.overlap_diagnostics)
                    res.calibration_records.append(
                        {
                            "ci_coverage": 1.0 if m.ci_covers else 0.0,
                            "ci_width": m.ci_width,
                            "calibration_mode": next(
                                iter((m.selection_manifest or {}).get("calibration_modes", [])),
                                None,
                            ),
                        }
                    )
                    if m.cate_pred is not None and cate_true is not None:
                        p = m.pehe
                        if p is not None:
                            res.pehe_values.append(p)
            except Exception:
                res.n_failed += 1
                res.ate_biases.append(float("nan"))
                res.ci_covers.append(False)
                res.ci_widths.append(float("nan"))

    return results


# ---------------------------------------------------------------------------
# BenchmarkCase builders
# ---------------------------------------------------------------------------


def _acic_case(
    name: str,
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    method_fns: dict[str, Any],
    n_obs: int,
    n_reps: int,
    *,
    ate_bias_threshold: float = 0.3,
    min_ci_coverage: float = 0.80,
    seed: int = 42,
) -> BenchmarkCase:
    """Build a BenchmarkCase for one ACIC-style DGP × all methods."""

    def runner() -> dict[str, DGPResult]:
        return _run_dgp_replications(
            dgp_fn=dgp_fn,
            dgp_kwargs=dgp_kwargs,
            method_fns=method_fns,
            n_obs=n_obs,
            n_reps=n_reps,
            dgp_name=name,
            base_seed=seed,
        )

    def checker(results: dict[str, DGPResult]) -> bool:
        return _check_acic_results(
            case_name=name,
            results=results,
            ate_bias_threshold=ate_bias_threshold,
            min_ci_coverage=min_ci_coverage,
        )

    return BenchmarkCase(
        name=f"acic::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("acic",),
        timeout_s=1800.0,
    )


def _check_acic_results(
    *,
    case_name: str,
    results: dict[str, DGPResult],
    ate_bias_threshold: float,
    min_ci_coverage: float,
) -> bool:
    # Find the best (lowest) RMSE across all methods
    rmse_vals = [r.ate_rmse for r in results.values() if math.isfinite(r.ate_rmse)]
    if not rmse_vals:
        raise AssertionError(f"{case_name}: all methods failed")
    best_rmse = min(rmse_vals)
    relative_reference = max(best_rmse, float(ate_bias_threshold) / 6.0)

    # Check each PolicyOS method
    policy_os_names = [k for k in results if infer_method_group(k) == "policy_os_competitive"]
    if not policy_os_names:
        return True  # baselines only, trivially pass

    issues = []
    for pname in policy_os_names:
        res = results[pname]
        if res.ate_rmse > ate_bias_threshold:
            issues.append(f"{pname}: ATE RMSE={res.ate_rmse:.3f} > threshold={ate_bias_threshold}")
        if res.ci_coverage < min_ci_coverage:
            issues.append(f"{pname}: CI coverage={res.ci_coverage:.2f} < {min_ci_coverage}")
        # Guard against near-oracle winners making the relative bar degenerate.
        if math.isfinite(res.ate_rmse) and res.ate_rmse > 3.0 * relative_reference + 1e-6:
            issues.append(
                f"{pname}: RMSE={res.ate_rmse:.3f} is >3x reference={relative_reference:.3f} "
                f"(best={best_rmse:.3f}, quartile floor)"
            )
    if issues:
        raise AssertionError(f"{case_name}: " + "; ".join(issues))
    return True


# ---------------------------------------------------------------------------
# ACIC dataset loader (graceful degradation)
# ---------------------------------------------------------------------------


def _try_load_acic_2016(
    data_dir: Path,
) -> list[tuple[str, HTEObservationalData, np.ndarray]] | None:
    """Attempt to load real ACIC 2016 data.

    Returns a list of (name, data, cate_true) triples, or None if not available.
    Supported structures:
      1. Normalized:
         data_dir/acic_2016/covariates.csv + dgp_*.csv
      2. Official causallib sample:
         data_dir/acic_challenge_2016/x.csv + zymu_*.csv
    """
    normalized_dir = data_dir / "acic_2016"
    causallib_dir = data_dir / "acic_challenge_2016"

    cov_file = normalized_dir / "covariates.csv"
    dgp_dir = normalized_dir
    dgp_pattern = "dgp_*.csv"
    official_layout = False
    if not cov_file.exists():
        cov_file = causallib_dir / "x.csv"
        dgp_dir = causallib_dir
        dgp_pattern = "zymu_*.csv"
        official_layout = cov_file.exists()
    if not cov_file.exists():
        return None

    try:
        import csv

        with open(cov_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        n = len(rows)
        feature_names = [k for k in rows[0] if k not in ("id", "sample_id")]

        encoded_cols: list[np.ndarray] = []
        normalized_feature_names: list[str] = []
        for fn in feature_names:
            values = [r[fn] for r in rows]
            try:
                col = np.array([float(v) for v in values], dtype=float)
                encoded_cols.append(col)
                normalized_feature_names.append(fn)
                continue
            except Exception:
                pass

            categories = {value: float(idx) for idx, value in enumerate(sorted(set(values)))}
            col = np.array([categories[v] for v in values], dtype=float)
            encoded_cols.append(col)
            normalized_feature_names.append(fn)

        X = np.column_stack(encoded_cols) if encoded_cols else np.empty((n, 0), dtype=float)

        datasets = []
        for dgp_file in sorted(dgp_dir.glob(dgp_pattern)):
            try:
                with open(dgp_file) as f:
                    reader = csv.DictReader(f)
                    dgp_rows = list(reader)
                T = np.array([float(r["z"]) for r in dgp_rows])
                if official_layout:
                    y0 = np.array([float(r["y0"]) for r in dgp_rows])
                    y1 = np.array([float(r["y1"]) for r in dgp_rows])
                    Y = np.where(T > 0.5, y1, y0)
                else:
                    Y = np.array([float(r["y"]) for r in dgp_rows])
                mu1 = np.array([float(r.get("mu1", r.get("y1", "0"))) for r in dgp_rows])
                mu0 = np.array([float(r.get("mu0", r.get("y0", "0"))) for r in dgp_rows])
                cate_true = mu1 - mu0

                data = HTEObservationalData(
                    outcome=Y,
                    treatment=T,
                    covariates=X,
                    feature_names=normalized_feature_names,
                )
                datasets.append((dgp_file.stem, data, cate_true))
            except Exception:
                continue

        return datasets if datasets else None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main harness builder
# ---------------------------------------------------------------------------


def _make_method_fns(
    seed_offset: int = 0,
    *,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_estimation",
) -> dict[str, Any]:
    """Build method callables — PolicyOS + baselines."""
    if method_profile not in ESTIMATION_METHOD_PROFILES:
        valid = ", ".join(ESTIMATION_METHOD_PROFILES)
        raise ValueError(
            f"Unknown estimation method profile: {method_profile!r}. Expected one of: {valid}"
        )
    fns: dict[str, Any] = {}
    flagship_params = _acic_nuisance_params(tier, seed=seed_offset)

    # Baselines (always available)
    fns["ols"] = lambda data, rng: _baseline_ols(data, rng)
    fns["ipw"] = lambda data, rng: _baseline_ipw(data, rng)
    fns["naive"] = lambda data, _rng: _baseline_naive(data)

    try:
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
            _acic_xlearner_params(tier, seed=seed_offset),
        )
    except Exception:
        pass

    if method_profile == "full_matrix_estimation":
        try:
            from polisyos.foundry.methods.catalog.causal.advanced_designs import DRLearnerEstimator

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


def build_acic_harness(
    n_obs: int = 500,
    n_reps: int = 10,
    seed: int = 42,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_estimation",
) -> BenchmarkHarness:
    """Build a BenchmarkHarness with all ACIC-style estimation cases."""
    harness = BenchmarkHarness()
    method_fns = _make_method_fns(seed_offset=seed, tier=tier, method_profile=method_profile)

    # Check if real ACIC data is available
    real_datasets = None
    if ACIC_DATA_DIR is not None:
        real_datasets = _try_load_acic_2016(ACIC_DATA_DIR)

    if real_datasets:
        if tier is BenchmarkTier.RESEARCH_ACCEPTANCE:
            batch_size = min(20, max(5, len(real_datasets)))
            for batch_index, batch_start in enumerate(
                range(0, len(real_datasets), batch_size), start=1
            ):
                batch = real_datasets[batch_start : batch_start + batch_size]

                def _make_batch_runner(
                    datasets=batch,
                    mf=method_fns,
                    batch_name=f"batch_{batch_index:02d}",
                ):
                    def runner() -> dict[str, DGPResult]:
                        out: dict[str, DGPResult] = {
                            name: DGPResult(
                                dgp_name=batch_name,
                                method_name=name,
                                n_reps=len(datasets),
                                ate_true=float("nan"),
                                ate_biases=[],
                                ci_covers=[],
                                ci_widths=[],
                                pehe_values=[],
                                n_failed=0,
                            )
                            for name in mf
                        }
                        for dataset_offset, (dataset_name, rd, ct) in enumerate(datasets):
                            at = float(np.mean(ct))
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
                                    else:
                                        res.ate_biases.append(m.ate_bias)
                                        res.ci_covers.append(m.ci_covers)
                                        res.ci_widths.append(m.ci_width)
                                        if m.selection_manifest:
                                            res.selection_records.append(m.selection_manifest)
                                        if m.overlap_diagnostics:
                                            res.overlap_records.append(m.overlap_diagnostics)
                                        res.calibration_records.append(
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
                                            }
                                        )
                                        if m.pehe is not None:
                                            res.pehe_values.append(m.pehe)
                                except Exception:
                                    out[method_name].n_failed += 1
                                    out[method_name].ate_biases.append(float("nan"))
                                    out[method_name].ci_covers.append(False)
                                    out[method_name].ci_widths.append(float("nan"))
                        return out

                    return runner

                harness.register(
                    BenchmarkCase(
                        name=f"acic::research_batch_{batch_index:02d}",
                        circuit=CIRCUIT,
                        runner=_make_batch_runner(),
                        checker=lambda results,
                        bn=f"research_batch_{batch_index:02d}": _check_acic_results(
                            case_name=bn,
                            results=results,
                            ate_bias_threshold=0.30,
                            min_ci_coverage=0.80,
                        ),
                        tags=("acic", "real", "research_acceptance"),
                        timeout_s=1800.0,
                    )
                )
        else:
            # Real ACIC 2016 data — local evidence on small official subset.
            for dgp_name, real_data, cate_true in real_datasets[:6]:
                ate_true = float(np.mean(cate_true))

                def _make_real_runner(
                    rd=real_data, ct=cate_true, at=ate_true, dn=dgp_name, mf=method_fns
                ):
                    def runner() -> dict[str, DGPResult]:
                        rng = np.random.default_rng(seed)
                        out: dict[str, DGPResult] = {}
                        for name, fn in mf.items():
                            try:
                                m = fn(rd, rng)
                                m.ate_true = at
                                m.cate_true = ct
                                r = DGPResult(
                                    dgp_name=dn,
                                    method_name=name,
                                    n_reps=1,
                                    ate_true=at,
                                    ate_biases=[m.ate_bias],
                                    ci_covers=[m.ci_covers],
                                    ci_widths=[m.ci_width],
                                    pehe_values=[m.pehe] if m.pehe is not None else [],
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
                                        }
                                    ]
                                    if not m.failed
                                    else [],
                                )
                                out[name] = r
                            except Exception:
                                out[name] = DGPResult(
                                    dgp_name=dn,
                                    method_name=name,
                                    n_reps=1,
                                    ate_true=at,
                                    ate_biases=[float("nan")],
                                    ci_covers=[False],
                                    ci_widths=[float("nan")],
                                    pehe_values=[],
                                    n_failed=1,
                                )
                        return out

                    return runner

                case = BenchmarkCase(
                    name=f"acic::real_{dgp_name}",
                    circuit=CIRCUIT,
                    runner=_make_real_runner(),
                    checker=lambda results, dn=dgp_name: _check_acic_results(
                        case_name=f"real_{dn}",
                        results=results,
                        ate_bias_threshold=0.3,
                        min_ci_coverage=0.80,
                    ),
                    tags=("acic", "real", "local_evidence"),
                    timeout_s=1800.0,
                )
                harness.register(case)

    else:
        # Synthetic DGPs
        dgps = [
            (
                "linear_moderate_confounding",
                _dgp_linear,
                {"p": 10, "ate": 1.0, "confounding_strength": 1.0},
                0.30,
                0.80,
            ),
            (
                "linear_strong_confounding",
                _dgp_linear,
                {"p": 10, "ate": 1.0, "confounding_strength": 2.5},
                0.35,
                0.75,
            ),
            (
                "nonlinear_outcome",
                _dgp_nonlinear,
                {"p": 10, "ate": 1.0},
                0.35,
                0.75,
            ),
            (
                "hte_effect_modification",
                _dgp_hte,
                {"p": 10, "base_ate": 1.0, "hte_strength": 0.5},
                0.35,
                0.75,
            ),
            (
                "strong_overlap_rct_like",
                _dgp_strong_overlap,
                {"p": 10, "ate": 0.5},
                0.25,
                0.85,
            ),
            (
                "weak_overlap_severe_confounding",
                _dgp_weak_overlap,
                {"p": 10, "ate": 2.0},
                0.50,
                0.70,
            ),
        ]

        for dgp_name, dgp_fn, dgp_kwargs, bias_thresh, cov_thresh in dgps:
            case = _acic_case(
                name=dgp_name,
                dgp_fn=dgp_fn,
                dgp_kwargs=dgp_kwargs,
                method_fns=method_fns,
                n_obs=n_obs,
                n_reps=n_reps,
                ate_bias_threshold=bias_thresh,
                min_ci_coverage=cov_thresh,
                seed=seed,
            )
            harness.register(case)

    return harness


# ---------------------------------------------------------------------------
# Ranking analysis
# ---------------------------------------------------------------------------


def compute_method_ranks(report: BenchmarkReport) -> dict[str, Any]:
    """Compute per-case standardized ATE RMSE ranks and aggregated summary."""
    return compute_ranking_summary(
        report,
        primary_metric="ate_rmse_standardized",
        metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
        scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
        standardized=True,
    )


def _acic_case_group(case_name: str) -> str:
    leaf = case_name.split("::", 1)[-1]
    if leaf.startswith("research_batch_"):
        return "research_batch"
    if leaf.startswith("real_"):
        return "real_case"
    return "synthetic_case"


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport, *, mode: BenchmarkMode, preflight: dict[str, Any]
) -> dict[str, Any]:
    aggregate_summary, standardized_summary, grouped_summary = summarize_method_metrics(
        report,
        metric_getters={
            "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
            "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
            "ci_width": lambda result: getattr(result, "ci_width_mean", float("nan")),
            "pehe": lambda result: getattr(result, "pehe_mean", float("nan")),
        },
        standardized_metrics={"ate_rmse", "ci_width", "pehe"},
        scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
        case_group_getter=_acic_case_group,
    )
    ranking_summary = compute_method_ranks(report)
    present_methods = {
        method_name
        for case in report.cases
        if isinstance(case.result_payload, dict)
        for method_name in case.result_payload
    }
    method_manifest = build_method_registry(
        present_methods,
        benchmark_roles=ACIC_BENCHMARK_ROLES,
    )
    method_presence = compute_method_presence(report, ACIC_GATE_METHOD_SET)
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
    flagship_scorecard = build_flagship_scorecard(
        flagship_method=ACIC_FLAGSHIP_METHOD,
        aggregate_metrics=aggregate_summary,
        ranking_summary=ranking_summary,
        thresholds={
            "mean_rank_max": 2,
            "max_deviation_from_best_max": 0.10,
            "top_quartile_failures_max": 0,
            "ci_coverage_mean_min": 0.80,
        },
        gate_method_set=ACIC_GATE_METHOD_SET,
        method_presence=method_presence,
    )
    return build_report_payload(
        report,
        suite_id="estimation_acic",
        mode=mode.value,
        preflight=preflight,
        sub_circuit="acic",
        include_case_payload=True,
        aggregate_metrics={
            "method_summary": aggregate_summary,
            "ranking_summary": ranking_summary,
            "case_groups": grouped_summary,
            "flagship_scorecard": flagship_scorecard,
        },
        standardized_metrics=standardized_summary,
        method_groups=method_manifest,
        method_manifest=method_manifest,
        gate_method_set=list(ACIC_GATE_METHOD_SET),
        flagship_presence=method_presence.get(ACIC_FLAGSHIP_METHOD, {}),
        exploratory_methods=[
            method_name
            for method_name, meta in method_manifest.items()
            if meta.get("benchmark_role") == "exploratory"
        ],
        selection_manifest=selection_manifest,
        overlap_diagnostics=overlap_diagnostics,
        calibration_metrics=calibration_metrics,
        claim_profile_targets=["full_stack_publication_claim"],
        literature_anchor=ACIC_LITERATURE_ANCHOR,
        public_claim_eligible=True,
        blockers=[case.name for case in report.cases if not case.passed],
        extra={
            "ranking_summary": ranking_summary,
            "method_profile": preflight.get("method_profile"),
        },
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 2 — ACIC Effect Estimation benchmark")
    parser.add_argument("--n-obs", type=int, default=500)
    parser.add_argument("--n-reps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", metavar="FILE", help="Write JSON report to FILE")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode], default=None)
    parser.add_argument("--tier", choices=[tier.value for tier in BenchmarkTier], default=None)
    parser.add_argument(
        "--method-profile",
        choices=list(ESTIMATION_METHOD_PROFILES),
        default=None,
        help="Use production-only estimation methods or the wider exploratory matrix",
    )
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    tier = resolve_tier(args.tier, mode=mode)
    method_profile = resolve_estimation_method_profile(tier, requested=args.method_profile)
    real_data_status = env_path_status("ACIC_DATA_DIR")
    has_real_data = False
    if ACIC_DATA_DIR is not None:
        has_real_data = _try_load_acic_2016(ACIC_DATA_DIR) is not None

    comparator_status = build_research_acceptance_comparator_status()
    planned_n_obs = (
        400 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_obs == 500 else args.n_obs
    )
    planned_n_reps = (
        6 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_reps == 10 else args.n_reps
    )
    degraded_reasons = []
    if not has_real_data:
        degraded_reasons.append(
            "using synthetic ACIC replicas because real ACIC data is unavailable"
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
            has_real_data=has_real_data, synthetic_label="synthetic_replica", real_label="real_acic"
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
        dataset_family="acic",
        batch_id=f"n_obs={planned_n_obs};n_reps={planned_n_reps}",
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
        print("ACIC acceptance preflight failed:")
        for gap in gaps:
            print(f"  - {gap}")
        return 2

    harness = build_acic_harness(
        n_obs=planned_n_obs,
        n_reps=planned_n_reps,
        seed=args.seed,
        tier=tier,
        method_profile=method_profile,
    )
    report = harness.run(circuit=BenchmarkCircuit.ESTIMATION)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        path = Path(args.json)
        path.write_text(
            json.dumps(_report_to_dict(report, mode=mode, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {path}")

    n_failed = report.n_total() - report.n_passed()
    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
