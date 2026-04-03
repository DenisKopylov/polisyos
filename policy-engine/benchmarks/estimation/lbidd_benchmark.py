"""Circuit 2: Effect Estimation — IBM LBIDD semi-synthetic benchmark.

Evaluates individual and average treatment-effect estimation against the
IBM LBIDD (Large-scale Benchmark for Individual treatment-effect estimation
for policy Decision-making) benchmark structure:

    - Real covariates (pop-level demographics) + synthetic outcomes
    - Metrics: PEHE (sqrt(E[(τ̂-τ)²])), ATE bias, CI coverage
    - Varying confounding strengths (ρ = 0.1, 0.3, 0.6, 0.9)
    - Varying signal-to-noise (σ²: 0.5, 1.0, 2.0)

When real LBIDD data is present (set LBIDD_DATA_DIR), those files are loaded.
Otherwise a fully synthetic replication of the LBIDD design is used.

Bar
---
    PEHE ≤ best-baseline × 2.0  (not worse than 2× best among baselines)
    ATE RMSE ≤ threshold (0.4 by default)
    No more than 25% failure rate per DGP

Usage
-----
    python benchmarks/estimation/lbidd_benchmark.py
    python benchmarks/estimation/lbidd_benchmark.py --json report.json
    python benchmarks/estimation/lbidd_benchmark.py --n-obs 1000 --n-reps 5
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

from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
    Verdict,
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
from benchmarks.comparators import (
    ForestDRLearnerComparator,
    build_research_acceptance_comparator_status,
    comparator_degraded_reasons,
    comparator_required_modules,
)
from benchmarks.method_registry import build_method_registry, infer_method_group
from benchmarks.policyos_runner import extract_policyos_result, invoke_policyos_method
from benchmarks.research_metrics import (
    basic_overlap_diagnostics,
    fit_eval_propensity,
    eceth,
    posthoc_cate_calibration,
    policy_value_top_q,
    rank_weighted_ate,
    summarize_calibration_metrics,
    summarize_method_records,
    summarize_overlap_diagnostics,
    summarize_prioritization_metrics,
    summarize_selection_manifest,
)
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
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
    safe_effect_scale,
    summarize_method_metrics,
)

from polisyos.foundry.methods.catalog.causal.protocols import (  # noqa: E402
    HTEObservationalData,
)

CIRCUIT = BenchmarkCircuit.ESTIMATION
LBIDD_FLAGSHIP_METHOD = "policy_os_causal_forest"
LBIDD_LITERATURE_ANCHOR = [
    "Shimoni et al. (2018). Benchmarking Framework for Performance-Evaluation of Causal Inference Analysis.",
    "IBM LBIDD semi-synthetic individual treatment effect benchmark.",
]
LBIDD_BENCHMARK_ROLES = {
    LBIDD_FLAGSHIP_METHOD: "flagship",
    "policy_os_aipw_cf": "production_challenger",
    "policy_os_tmle_cf": "production_challenger",
    "policy_os_xlearner_cf": "production_challenger",
    "policy_os_causal_bcf": "exploratory",
    "policy_os_drlearner_cf": "exploratory",
    "policy_os_forestdr_cf": "exploratory",
    "external_dml_econml": "exploratory",
}
LBIDD_GATE_METHOD_SET = tuple(
    method_name
    for method_name, role in LBIDD_BENCHMARK_ROLES.items()
    if role in {"flagship", "production_challenger"}
)

# Optional real-dataset path
LBIDD_DATA_DIR: Path | None = (
    Path(p) if (p := os.environ.get("LBIDD_DATA_DIR", "")) else None
)


def _lbidd_nuisance_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_nuisance_params(tier, seed=seed, hte=False)
    params.update(
        {
            "propensity_clipping": 0.05 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.025,
            "propensity_trimming": 0.05 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.025,
            "overlap_trim": 0.05 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.025,
            "overlap_guard": 0.18 if tier is BenchmarkTier.LOCAL_EVIDENCE else 0.12,
            "min_effective_sample_size": 64 if tier is BenchmarkTier.LOCAL_EVIDENCE else 96,
        }
    )
    return params


def _lbidd_xlearner_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_xlearner_params(tier, seed=seed)
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        params.update(
            {
                "selection_objective": "r_risk_sparse_guarded",
                "split_policy": "holdout_r_risk_sparse_guarded",
                "base_model_candidates": [
                    "linear",
                    "elastic_net_sparse",
                ],
            }
        )
    else:
        params.update(
            {
                "selection_objective": "r_risk_overlap_guarded",
                "split_policy": "holdout_r_risk_overlap_guarded",
                "base_model_candidates": [
                    "linear",
                    "elastic_net_sparse",
                    "gradient_boosting",
                    "random_forest",
                ],
            }
        )
    return params


def _lbidd_causal_forest_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_causal_forest_params(tier, seed=seed)
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        params.update(
            {
                "min_samples_leaf": 8,
                "min_samples_leaf_candidates": [6, 8, 12],
            }
        )
    return params


# ---------------------------------------------------------------------------
# Estimation metrics (reuse ACIC structure)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class LBIDDMetrics:
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
class LBIDDResult:
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
    prioritization_records: list[dict[str, Any]] = dataclasses.field(default_factory=list)

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
    def failure_rate(self) -> float:
        total = self.n_reps
        return self.n_failed / total if total > 0 else 1.0

    @property
    def selection_manifest(self) -> dict[str, Any]:
        return summarize_selection_manifest(self.selection_records)

    @property
    def overlap_diagnostics(self) -> dict[str, Any]:
        return summarize_overlap_diagnostics(self.overlap_records)

    @property
    def calibration_metrics(self) -> dict[str, Any]:
        return summarize_calibration_metrics(self.calibration_records)

    @property
    def prioritization_metrics(self) -> dict[str, Any]:
        return summarize_prioritization_metrics(self.prioritization_records)


# ---------------------------------------------------------------------------
# LBIDD-style synthetic DGPs
# ---------------------------------------------------------------------------
# The LBIDD benchmark design:
#  - Real covariates drawn from a population distribution (here: Gaussian mixture)
#  - Treatment propensity: e(X) = σ(ρ · Σ_j β_j X_j)  where ρ controls confounding
#  - Outcome:  Y = μ₀(X) + τ(X)·T + ε,  with signal-to-noise param σ_noise
#  - CATE: τ(X) = τ_ATE + δ_HTE · (X[:,0] - E[X[:,0]])
#
# We vary confounding strength ρ ∈ {0.1, 0.3, 0.6, 0.9} and snr ∈ {0.5, 1.0, 2.0}


def _make_population_covariates(
    n: int,
    p: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Gaussian mixture to mimic realistic population covariate distribution."""
    n_components = 3
    means = rng.standard_normal((n_components, p)) * 1.5
    mixing = rng.dirichlet(np.ones(n_components))
    assignments = rng.choice(n_components, size=n, p=mixing)
    X = np.vstack([
        rng.multivariate_normal(means[k], np.eye(p), size=int(np.sum(assignments == k)))
        for k in range(n_components)
    ])
    # Shuffle to break group ordering
    rng.shuffle(X)
    return X[:n]


def _dgp_lbidd(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 25,
    tau_ate: float = 0.5,
    delta_hte: float = 0.3,
    confounding_rho: float = 0.3,
    snr: float = 1.0,
) -> tuple[HTEObservationalData, np.ndarray]:
    """LBIDD-style semi-synthetic DGP.

    confounding_rho: strength of confounding (0 = pure random assignment).
    snr: signal-to-noise ratio; higher = less noise.
    """
    X = _make_population_covariates(n, p, rng)

    # Confounded treatment assignment
    prop_coef = confounding_rho * rng.standard_normal(p) / np.sqrt(p)
    logit = X @ prop_coef
    prop = 1 / (1 + np.exp(-logit))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    # Nonlinear baseline outcome
    beta0 = rng.standard_normal(p) / np.sqrt(p)
    mu0 = X @ beta0 + 0.3 * np.sin(X[:, 0] * X[:, 1])

    # Heterogeneous treatment effect
    cate_true = tau_ate + delta_hte * (X[:, 0] - np.mean(X[:, 0]))

    noise_std = np.sqrt(np.var(mu0 + cate_true * T) / snr)
    Y = mu0 + cate_true * T + noise_std * rng.standard_normal(n)

    data = HTEObservationalData(outcome=Y, treatment=T, covariates=X)
    return data, cate_true


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def _baseline_ols(data: HTEObservationalData, rng: np.random.Generator) -> LBIDDMetrics:
    from numpy.linalg import lstsq

    X = np.column_stack([data.covariates, data.treatment, np.ones(len(data.outcome))])
    Y = data.outcome
    coef, _, _, _ = lstsq(X, Y, rcond=None)
    ate_pred = float(coef[-2])

    # Uniform CATE prediction (OLS gives constant estimate)
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
    if boot_ates:
        ci_lo = float(np.percentile(boot_ates, 2.5))
        ci_hi = float(np.percentile(boot_ates, 97.5))
    else:
        ci_lo, ci_hi = ate_pred - 0.2, ate_pred + 0.2

    return LBIDDMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=cate_pred,
        method_name="ols",
        dgp_name="",
    )


def _baseline_t_learner(
    data: HTEObservationalData, rng: np.random.Generator
) -> LBIDDMetrics:
    """T-learner baseline using random forests (pure numpy fallback otherwise)."""
    from numpy.linalg import lstsq

    X, T, Y = data.covariates, data.treatment, data.outcome
    mask1, mask0 = T == 1, T == 0

    try:
        from sklearn.ensemble import RandomForestRegressor

        m1 = RandomForestRegressor(n_estimators=50, random_state=0, n_jobs=1)
        m0 = RandomForestRegressor(n_estimators=50, random_state=0, n_jobs=1)
        m1.fit(X[mask1], Y[mask1])
        m0.fit(X[mask0], Y[mask0])
        mu1 = m1.predict(X)
        mu0 = m0.predict(X)
    except ImportError:
        # Linear fallback
        def _lin_fit(Xa: np.ndarray, Ya: np.ndarray) -> np.ndarray:
            Xa_b = np.column_stack([Xa, np.ones(len(Ya))])
            coef, _, _, _ = lstsq(Xa_b, Ya, rcond=None)
            return coef

        coef1 = _lin_fit(X[mask1], Y[mask1])
        coef0 = _lin_fit(X[mask0], Y[mask0])
        Xb = np.column_stack([X, np.ones(len(Y))])
        mu1 = Xb @ coef1
        mu0 = Xb @ coef0

    cate_pred = mu1 - mu0
    ate_pred = float(np.mean(cate_pred))

    # Bootstrap CI
    n = len(Y)
    boot_ates: list[float] = []
    for _ in range(100):
        idx = rng.integers(0, n, size=n)
        boot_ates.append(float(np.mean(cate_pred[idx])))
    ci_lo = float(np.percentile(boot_ates, 2.5))
    ci_hi = float(np.percentile(boot_ates, 97.5))

    return LBIDDMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=cate_pred,
        method_name="t_learner",
        dgp_name="",
    )


def _baseline_ipw(data: HTEObservationalData, rng: np.random.Generator) -> LBIDDMetrics:
    from numpy.linalg import lstsq

    X, T, Y = data.covariates, data.treatment, data.outcome
    n = len(Y)
    Xp = np.column_stack([X, np.ones(n)])
    coef = np.zeros(Xp.shape[1])
    for _ in range(30):
        logit = Xp @ coef
        prob = 1 / (1 + np.exp(-np.clip(logit, -20, 20)))
        W = prob * (1 - prob) + 1e-8
        z = logit + (T - prob) / W
        sqW = np.sqrt(W)
        try:
            coef, _, _, _ = lstsq((sqW[:, None] * Xp), sqW * z, rcond=None)
        except Exception:
            break
    prop = np.clip(1 / (1 + np.exp(-np.clip(Xp @ coef, -20, 20))), 0.05, 0.95)

    ipw_1 = Y * T / prop
    ipw_0 = Y * (1 - T) / (1 - prop)
    ate_pred = float(np.mean(ipw_1) - np.mean(ipw_0))

    boot_ates: list[float] = []
    for _ in range(200):
        idx = rng.integers(0, n, size=n)
        boot_ates.append(float(np.mean(ipw_1[idx]) - np.mean(ipw_0[idx])))
    ci_lo = float(np.percentile(boot_ates, 2.5))
    ci_hi = float(np.percentile(boot_ates, 97.5))

    return LBIDDMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ci_lo,
        ate_ci_upper=ci_hi,
        cate_true=None,
        cate_pred=None,
        method_name="ipw",
        dgp_name="",
    )


# ---------------------------------------------------------------------------
# PolicyOS method runner
# ---------------------------------------------------------------------------


def _run_policy_os_method(
    method_class: type,
    data: HTEObservationalData,
    params: dict[str, Any],
) -> LBIDDMetrics:
    try:
        result = invoke_policyos_method(method_class, data, params)
    except Exception as exc:
        return LBIDDMetrics(
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
        return LBIDDMetrics(
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

    selection_manifest = (
        extracted.selection_manifest
        or benchmark_selection_manifest_from_params(params, method_label=method_class.__name__)
    )
    cate_pred = extracted.cate_pred
    ate_pred = extracted.ate_pred
    ate_ci_lower = extracted.ate_ci_lower
    ate_ci_upper = extracted.ate_ci_upper
    if cate_pred is not None and cate_pred.size:
        calibrated_cate, calibration_meta = posthoc_cate_calibration(
            data.covariates,
            data.treatment,
            data.outcome,
            cate_pred,
            seed=int(params.get("random_state", params.get("__seed__", 0)) or 0),
            ate_anchor=extracted.ate_pred,
        )
        if calibrated_cate.size == cate_pred.size:
            cate_pred = calibrated_cate
            selection_manifest = dict(selection_manifest)
            selection_manifest["calibration_modes"] = [
                *selection_manifest.get("calibration_modes", []),
                str(calibration_meta.get("calibration_mode", "identity")),
            ]

    return LBIDDMetrics(
        ate_true=0.0,
        ate_pred=ate_pred,
        ate_ci_lower=ate_ci_lower,
        ate_ci_upper=ate_ci_upper,
        cate_true=None,
        cate_pred=cate_pred,
        method_name=method_class.__name__,
        dgp_name="",
        selection_manifest=selection_manifest,
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


def _run_lbidd_replications(
    dgp_kwargs: dict[str, Any],
    method_fns: dict[str, Any],
    n_obs: int,
    n_reps: int,
    dgp_name: str,
    base_seed: int = 0,
) -> dict[str, LBIDDResult]:
    ate_true = float(dgp_kwargs.get("tau_ate", 0.5))
    results: dict[str, LBIDDResult] = {
        name: LBIDDResult(
            dgp_name=dgp_name,
            method_name=name,
            n_reps=n_reps,
            ate_true=ate_true,
            ate_biases=[],
            ci_covers=[],
            ci_widths=[],
            pehe_values=[],
            n_failed=0,
        )
        for name in method_fns
    }

    for rep in range(n_reps):
        rng = np.random.default_rng(base_seed + rep)
        try:
            data, cate_true = _dgp_lbidd(n_obs, rng, **dgp_kwargs)
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
                    calibration_record = {
                        "ci_coverage": 1.0 if m.ci_covers else 0.0,
                        "ci_width": m.ci_width,
                        "calibration_mode": next(
                            iter((m.selection_manifest or {}).get("calibration_modes", [])),
                            None,
                        ),
                    }
                    if m.cate_pred is not None and cate_true is not None:
                        # Use the actual cate_true
                        m.cate_true = cate_true
                        p = m.pehe
                        if p is not None:
                            res.pehe_values.append(p)
                        calibration_record["eceth"] = eceth(cate_true, m.cate_pred)
                        res.prioritization_records.append(
                            {
                                "rate": rank_weighted_ate(cate_true, m.cate_pred),
                                "policy_value_top_q": policy_value_top_q(cate_true, m.cate_pred),
                            }
                        )
                    res.calibration_records.append(calibration_record)
            except Exception:
                res.n_failed += 1
                res.ate_biases.append(float("nan"))
                res.ci_covers.append(False)
                res.ci_widths.append(float("nan"))

    return results


# ---------------------------------------------------------------------------
# BenchmarkCase builder
# ---------------------------------------------------------------------------


def _lbidd_case(
    name: str,
    dgp_kwargs: dict[str, Any],
    method_fns: dict[str, Any],
    n_obs: int,
    n_reps: int,
    *,
    ate_rmse_threshold: float = 0.4,
    pehe_multiplier: float = 2.0,
    max_failure_rate: float = 0.25,
    seed: int = 42,
) -> BenchmarkCase:
    """Build a BenchmarkCase for one LBIDD-style DGP × all methods."""

    def runner() -> dict[str, LBIDDResult]:
        return _run_lbidd_replications(
            dgp_kwargs=dgp_kwargs,
            method_fns=method_fns,
            n_obs=n_obs,
            n_reps=n_reps,
            dgp_name=name,
            base_seed=seed,
        )

    def checker(results: dict[str, LBIDDResult]) -> bool:
        return _check_lbidd_results(
            case_name=name,
            results=results,
            ate_rmse_threshold=ate_rmse_threshold,
            pehe_multiplier=pehe_multiplier,
            max_failure_rate=max_failure_rate,
        )

    return BenchmarkCase(
        name=f"lbidd::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("lbidd",),
        timeout_s=1800.0,
    )


def _check_lbidd_results(
    *,
    case_name: str,
    results: dict[str, LBIDDResult],
    ate_rmse_threshold: float,
    pehe_multiplier: float,
    max_failure_rate: float,
) -> bool:
        baseline_names = ("ols", "t_learner", "ipw")
        policy_os_names = [k for k in results if infer_method_group(k) == "policy_os_competitive"]

        if not policy_os_names:
            return True  # baselines only, trivially pass

        # Best PEHE among baselines (those that produce CATE)
        baseline_pehe_vals = [
            results[b].pehe_mean
            for b in baseline_names
            if b in results and math.isfinite(results[b].pehe_mean)
        ]
        best_baseline_pehe = min(baseline_pehe_vals) if baseline_pehe_vals else None

        issues: list[str] = []
        for pname in policy_os_names:
            res = results[pname]

            # Failure rate check
            if res.failure_rate > max_failure_rate:
                issues.append(
                    f"{pname}: failure_rate={res.failure_rate:.2f} > {max_failure_rate}"
                )

            # ATE RMSE check
            if math.isfinite(res.ate_rmse) and res.ate_rmse > ate_rmse_threshold:
                issues.append(
                    f"{pname}: ATE RMSE={res.ate_rmse:.3f} > threshold={ate_rmse_threshold}"
                )

            # PEHE check vs baselines
            if (
                math.isfinite(res.pehe_mean)
                and best_baseline_pehe is not None
                and res.pehe_mean > pehe_multiplier * best_baseline_pehe
            ):
                issues.append(
                    f"{pname}: PEHE={res.pehe_mean:.3f} > {pehe_multiplier}× "
                    f"best_baseline={best_baseline_pehe:.3f}"
                )

        if issues:
            raise AssertionError(f"lbidd::{case_name}: " + "; ".join(issues))
        return True


# ---------------------------------------------------------------------------
# LBIDD dataset loader (graceful degradation)
# ---------------------------------------------------------------------------


def _try_load_lbidd(
    data_dir: Path,
) -> list[tuple[str, HTEObservationalData, np.ndarray]] | None:
    """Attempt to load real LBIDD data.

    Supported structures:
      1. Normalized:
         data_dir/lbidd/x.csv         — covariates
         data_dir/lbidd/zy_*.csv      — one file per DGP with columns z, y, mu1, mu0
      2. Official IBM sample:
         data_dir/LBIDD/x.csv
         data_dir/LBIDD/scaling/*.csv + *_cf.csv
         data_dir/LBIDD/scaling_params.csv
    """
    normalized_dirs = [data_dir / "lbidd_normalized", data_dir / "lbidd"]
    normalized_cov = next(
        (
            path / "x.csv"
            for path in normalized_dirs
            if (path / "x.csv").exists() and any(path.glob("zy_*.csv"))
        ),
        None,
    )
    if normalized_cov is not None:
        try:
            import csv

            normalized_root = normalized_cov.parent
            with open(normalized_cov) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            feature_names = [k for k in rows[0] if k not in ("id", "sample_id")]
            x_by_id = None
            if "sample_id" in rows[0]:
                x_by_id = {
                    str(row["sample_id"]): np.array([float(row[fn]) for fn in feature_names], dtype=float)
                    for row in rows
                }
            else:
                X = np.array([[float(r[fn]) for fn in feature_names] for r in rows], dtype=float)

            datasets: list[tuple[str, HTEObservationalData, np.ndarray]] = []
            dgp_dir = normalized_root
            for dgp_file in sorted(dgp_dir.glob("zy_*.csv")):
                try:
                    with open(dgp_file) as f:
                        reader = csv.DictReader(f)
                        dgp_rows = list(reader)
                    if x_by_id is not None:
                        dgp_rows = [
                            row for row in dgp_rows if str(row.get("sample_id", "")) in x_by_id
                        ]
                        X = np.vstack([x_by_id[str(row["sample_id"])] for row in dgp_rows])
                    else:
                        X = X[: len(dgp_rows)]
                    T = np.array([float(r["z"]) for r in dgp_rows], dtype=float)
                    Y = np.array([float(r["y"]) for r in dgp_rows], dtype=float)
                    mu1 = np.array([float(r.get("mu1", "0")) for r in dgp_rows], dtype=float)
                    mu0 = np.array([float(r.get("mu0", "0")) for r in dgp_rows], dtype=float)
                    cate_true = mu1 - mu0
                    data = HTEObservationalData(
                        outcome=Y, treatment=T, covariates=X,
                        feature_names=feature_names,
                    )
                    datasets.append((dgp_file.stem, data, cate_true))
                except Exception:
                    continue

            return datasets if datasets else None
        except Exception:
            return None

    official_root = data_dir / "LBIDD"
    if not official_root.exists():
        return None

    try:
        import csv

        cov_file = official_root / "x.csv"
        if not cov_file.exists():
            return None

        with open(cov_file) as f:
            cov_rows = list(csv.DictReader(f))
        feature_names = [k for k in cov_rows[0] if k not in ("id", "sample_id")]
        x_by_id = {
            str(row["sample_id"]): np.array([float(row[fn]) for fn in feature_names], dtype=float)
            for row in cov_rows
            if row.get("sample_id") is not None
        }

        params_by_ufid: dict[str, tuple[float, float]] = {}
        params_file = official_root / "scaling_params.csv"
        if params_file.exists():
            with open(params_file) as f:
                for row in csv.DictReader(f):
                    ufid = row.get("ufid")
                    if not ufid:
                        continue
                    size = float(row.get("size", "inf"))
                    snr = float(row.get("snr", "nan"))
                    params_by_ufid[ufid] = (size, -snr)

        datasets: list[tuple[str, HTEObservationalData, np.ndarray]] = []
        dgp_dir = official_root / "scaling"
        factual_files = [
            path for path in dgp_dir.glob("*.csv")
            if not path.name.endswith("_cf.csv")
        ]
        factual_files.sort(key=lambda path: params_by_ufid.get(path.stem, (float("inf"), 0.0,)))

        for dgp_file in factual_files:
            try:
                cf_file = dgp_dir / f"{dgp_file.stem}_cf.csv"
                if not cf_file.exists():
                    continue
                with open(dgp_file) as f:
                    factual_rows = list(csv.DictReader(f))
                with open(cf_file) as f:
                    cf_rows = {
                        str(row["sample_id"]): row
                        for row in csv.DictReader(f)
                    }

                X_rows: list[np.ndarray] = []
                T_vals: list[float] = []
                Y_vals: list[float] = []
                mu0_vals: list[float] = []
                mu1_vals: list[float] = []
                for row in factual_rows:
                    sample_id = str(row.get("sample_id", ""))
                    if sample_id not in x_by_id or sample_id not in cf_rows:
                        continue
                    cf_row = cf_rows[sample_id]
                    X_rows.append(x_by_id[sample_id])
                    T_vals.append(float(row["z"]))
                    Y_vals.append(float(row["y"]))
                    mu0_vals.append(float(cf_row["y0"]))
                    mu1_vals.append(float(cf_row["y1"]))

                if not X_rows:
                    continue

                X = np.vstack(X_rows)
                T = np.array(T_vals, dtype=float)
                Y = np.array(Y_vals, dtype=float)
                mu0 = np.array(mu0_vals, dtype=float)
                mu1 = np.array(mu1_vals, dtype=float)
                cate_true = mu1 - mu0
                data = HTEObservationalData(
                    outcome=Y, treatment=T, covariates=X,
                    feature_names=feature_names,
                )
                datasets.append((dgp_file.stem, data, cate_true))
            except Exception:
                continue

        return datasets if datasets else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Method factory
# ---------------------------------------------------------------------------


def _make_method_fns(
    seed_offset: int = 0,
    *,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_estimation",
) -> dict[str, Any]:
    if method_profile not in ESTIMATION_METHOD_PROFILES:
        valid = ", ".join(ESTIMATION_METHOD_PROFILES)
        raise ValueError(f"Unknown estimation method profile: {method_profile!r}. Expected one of: {valid}")
    fns: dict[str, Any] = {}
    flagship_params = _lbidd_nuisance_params(tier, seed=seed_offset)

    # Baselines
    fns["ols"] = lambda data, rng: _baseline_ols(data, rng)
    fns["t_learner"] = lambda data, rng: _baseline_t_learner(data, rng)
    fns["ipw"] = lambda data, rng: _baseline_ipw(data, rng)

    try:
        from polisyos.foundry.methods.catalog.causal.causal_bcf import CausalBCF
        from polisyos.foundry.methods.catalog.causal.advanced_designs import DRLearnerEstimator
        from polisyos.foundry.methods.catalog.causal.treatment_effects import (
            AIPWEstimator,
            TMLEEstimator,
        )

        fns["policy_os_aipw_cf"] = lambda data, rng: _run_policy_os_method(
            AIPWEstimator,
            data,
            {**dict(flagship_params), "estimation_backend": "econml_direct", "direct_model_type": "linear"},
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
            _lbidd_causal_forest_params(tier, seed=seed_offset),
        )
    except Exception:
        pass

    try:
        from polisyos.foundry.methods.catalog.causal.meta_learners import MetaLearnerEstimator

        fns["policy_os_xlearner_cf"] = lambda data, rng: _run_policy_os_method(
            MetaLearnerEstimator,
            data,
            _lbidd_xlearner_params(tier, seed=seed_offset),
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
# Main harness builder
# ---------------------------------------------------------------------------


def build_lbidd_harness(
    n_obs: int = 1000,
    n_reps: int = 10,
    seed: int = 42,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_estimation",
) -> BenchmarkHarness:
    """Build BenchmarkHarness with LBIDD-style cases."""
    harness = BenchmarkHarness()
    method_fns = _make_method_fns(seed_offset=seed, tier=tier, method_profile=method_profile)
    fast_mode = fast_benchmark_mode() and tier is BenchmarkTier.LOCAL_EVIDENCE

    # Check for real data
    real_datasets = None
    if LBIDD_DATA_DIR is not None:
        real_datasets = _try_load_lbidd(LBIDD_DATA_DIR)

    if real_datasets:
        if fast_mode:
            real_datasets = real_datasets[:1]
        if tier is BenchmarkTier.RESEARCH_ACCEPTANCE:
            batch_size = min(12, max(4, len(real_datasets)))
            for batch_index, batch_start in enumerate(range(0, len(real_datasets), batch_size), start=1):
                batch = real_datasets[batch_start : batch_start + batch_size]

                def _make_batch_runner(
                    datasets=batch,
                    mf=method_fns,
                    batch_name=f"batch_{batch_index:02d}",
                ):
                    def runner() -> dict[str, LBIDDResult]:
                        out: dict[str, LBIDDResult] = {
                            name: LBIDDResult(
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
                        for dataset_offset, (_dataset_name, rd, ct) in enumerate(datasets):
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
                                        calibration_record = {
                                            "ci_coverage": 1.0 if m.ci_covers else 0.0,
                                            "ci_width": m.ci_width,
                                            "calibration_mode": next(
                                                iter((m.selection_manifest or {}).get("calibration_modes", [])),
                                                None,
                                            ),
                                        }
                                        if m.pehe is not None:
                                            res.pehe_values.append(m.pehe)
                                            calibration_record["eceth"] = eceth(ct, m.cate_pred) if m.cate_pred is not None else float("nan")
                                            res.prioritization_records.append(
                                                {
                                                    "rate": rank_weighted_ate(ct, m.cate_pred) if m.cate_pred is not None else float("nan"),
                                                    "policy_value_top_q": policy_value_top_q(ct, m.cate_pred) if m.cate_pred is not None else float("nan"),
                                                }
                                            )
                                        res.calibration_records.append(calibration_record)
                                except Exception:
                                    out[method_name].n_failed += 1
                                    out[method_name].ate_biases.append(float("nan"))
                                    out[method_name].ci_covers.append(False)
                                    out[method_name].ci_widths.append(float("nan"))
                        return out

                    return runner

                harness.register(
                    BenchmarkCase(
                        name=f"lbidd::research_batch_{batch_index:02d}",
                        circuit=CIRCUIT,
                        runner=_make_batch_runner(),
                        checker=lambda results, bn=f"research_batch_{batch_index:02d}": _check_lbidd_results(
                            case_name=bn,
                            results=results,
                            ate_rmse_threshold=0.4,
                            pehe_multiplier=2.0,
                            max_failure_rate=0.25,
                        ),
                        tags=("lbidd", "real", "research_acceptance"),
                        timeout_s=1800.0,
                    )
                )
        else:
            for dgp_name, real_data, cate_true in real_datasets[:5]:
                ate_true = float(np.mean(cate_true))

                def _make_runner(rd=real_data, ct=cate_true, at=ate_true, dn=dgp_name, mf=method_fns):
                    def runner() -> dict[str, LBIDDResult]:
                        rng = np.random.default_rng(seed)
                        out: dict[str, LBIDDResult] = {}
                        for name, fn in mf.items():
                            try:
                                m = fn(rd, rng)
                                m.ate_true = at
                                m.cate_true = ct
                                r = LBIDDResult(
                                    dgp_name=dn,
                                    method_name=name,
                                    n_reps=1,
                                    ate_true=at,
                                    ate_biases=[m.ate_bias] if not m.failed else [float("nan")],
                                    ci_covers=[m.ci_covers] if not m.failed else [False],
                                    ci_widths=[m.ci_width] if not m.failed else [float("nan")],
                                    pehe_values=[m.pehe] if (not m.failed and m.pehe is not None) else [],
                                    n_failed=1 if m.failed else 0,
                                    selection_records=[m.selection_manifest] if (not m.failed and m.selection_manifest) else [],
                                    overlap_records=[m.overlap_diagnostics] if (not m.failed and m.overlap_diagnostics) else [],
                                    calibration_records=[
                                        {
                                            "ci_coverage": 1.0 if m.ci_covers else 0.0,
                                            "ci_width": m.ci_width,
                                            "calibration_mode": next(
                                                iter((m.selection_manifest or {}).get("calibration_modes", [])),
                                                None,
                                            ),
                                            "eceth": eceth(ct, m.cate_pred) if m.cate_pred is not None else float("nan"),
                                        }
                                    ] if not m.failed else [],
                                    prioritization_records=[
                                        {
                                            "rate": rank_weighted_ate(ct, m.cate_pred) if m.cate_pred is not None else float("nan"),
                                            "policy_value_top_q": policy_value_top_q(ct, m.cate_pred) if m.cate_pred is not None else float("nan"),
                                        }
                                    ] if (not m.failed and m.cate_pred is not None) else [],
                                )
                                out[name] = r
                            except Exception:
                                out[name] = LBIDDResult(
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

                harness.register(BenchmarkCase(
                    name=f"lbidd::real_{dgp_name}",
                    circuit=CIRCUIT,
                    runner=_make_runner(),
                    checker=lambda results, dn=dgp_name: _check_lbidd_results(
                        case_name=f"real_{dn}",
                        results=results,
                        ate_rmse_threshold=0.4,
                        pehe_multiplier=2.0,
                        max_failure_rate=0.25,
                    ),
                    tags=("lbidd", "real", "local_evidence"),
                    timeout_s=1800.0,
                ))
    else:
        # Synthetic LBIDD-style DGPs — varying confounding and SNR
        dgp_grid = [
            # (name_suffix, confounding_rho, snr)
            ("low_confounding_high_snr",    0.1, 2.0),
            ("medium_confounding_high_snr", 0.3, 2.0),
            ("high_confounding_high_snr",   0.6, 2.0),
            ("high_confounding_med_snr",    0.6, 1.0),
            ("high_confounding_low_snr",    0.6, 0.5),
            ("very_high_confounding",       0.9, 1.0),
            ("hte_only",                    0.1, 1.0),
            ("hte_strong_confounding",      0.6, 1.0),
        ]
        if fast_mode:
            dgp_grid = dgp_grid[:1]

        for suffix, rho, snr in dgp_grid:
            dgp_kwargs = {
                "p": 25,
                "tau_ate": 0.5,
                "delta_hte": 0.3,
                "confounding_rho": rho,
                "snr": snr,
            }
            harness.register(_lbidd_case(
                name=suffix,
                dgp_kwargs=dgp_kwargs,
                method_fns=method_fns,
                n_obs=n_obs,
                n_reps=n_reps,
                ate_rmse_threshold=0.4,
                pehe_multiplier=2.0,
                max_failure_rate=0.25,
                seed=seed,
            ))

    return harness


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _compute_lbidd_summary(report: BenchmarkReport) -> dict[str, Any]:
    aggregate, _, _ = summarize_method_metrics(
        report,
        metric_getters={
            "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
            "pehe": lambda result: getattr(result, "pehe_mean", float("nan")),
            "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
            "failure_rate": lambda result: getattr(result, "failure_rate", float("nan")),
        },
    )
    return aggregate


def _lbidd_case_group(case_name: str) -> str:
    leaf = case_name.split("::", 1)[-1]
    if leaf.startswith("research_batch_"):
        return "research_batch"
    if leaf.startswith("real_"):
        return "real_case"
    if "high_snr" in leaf:
        return "snr_high"
    if "med_snr" in leaf:
        return "snr_medium"
    if "low_snr" in leaf:
        return "snr_low"
    if "very_high_confounding" in leaf:
        return "confounding_very_high"
    if "high_confounding" in leaf or "strong_confounding" in leaf:
        return "confounding_high"
    if "medium_confounding" in leaf:
        return "confounding_medium"
    if "low_confounding" in leaf:
        return "confounding_low"
    return "synthetic_case"


def _lbidd_joint_score(result: Any) -> float:
    scale = safe_effect_scale(getattr(result, "ate_true", float("nan")))
    ate_rmse = getattr(result, "ate_rmse", float("nan"))
    pehe = getattr(result, "pehe_mean", float("nan"))
    pieces = [
        value / scale
        for value in (ate_rmse, pehe)
        if math.isfinite(value)
    ]
    return float(np.mean(pieces)) if pieces else float("nan")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="LBIDD estimation benchmark")
    parser.add_argument("--n-obs", type=int, default=1000, metavar="N")
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
    real_data_status = env_path_status("LBIDD_DATA_DIR")
    has_real_data = False
    if LBIDD_DATA_DIR is not None:
        has_real_data = _try_load_lbidd(LBIDD_DATA_DIR) is not None

    comparator_status = build_research_acceptance_comparator_status()
    planned_n_obs = 700 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_obs == 1000 else args.n_obs
    planned_n_reps = 5 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_reps == 10 else args.n_reps
    degraded_reasons = []
    if not has_real_data:
        degraded_reasons.append("using synthetic LBIDD replicas because real LBIDD data is unavailable")
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        degraded_reasons.append("local_evidence tier uses thermal-safe subsets and lighter defaults")
    degraded_reasons.extend(comparator_degraded_reasons(comparator_status))

    preflight = build_preflight(
        mode=mode.value,
        benchmark_tier=tier.value,
        data_source=classify_data_source(has_real_data=has_real_data, synthetic_label="synthetic_replica", real_label="real_lbidd"),
        dependency_status={
            **real_data_status,
            "python_modules": dependency_status(["numpy", "scipy", "sklearn", "econml", "zepid", "stochtree", "dowhy", "y0", "lightgbm"]),
        },
        comparator_status=comparator_status,
        degraded_reasons=degraded_reasons,
        dataset_family="lbidd",
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
        print("LBIDD acceptance preflight failed:")
        for gap in gaps:
            print(f"  - {gap}")
        sys.exit(2)

    harness = build_lbidd_harness(
        n_obs=planned_n_obs,
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
                "failure_rate": lambda result: getattr(result, "failure_rate", float("nan")),
            },
            standardized_metrics={"ate_rmse", "pehe"},
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            case_group_getter=_lbidd_case_group,
        )
        ranking_summary = compute_ranking_summary(
            report,
            primary_metric="joint_score_standardized",
            metric_getter=_lbidd_joint_score,
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
        )
        present_methods = {
            method_name
            for case in report.cases
            if isinstance(case.result_payload, dict)
            for method_name in case.result_payload
        }
        method_manifest = build_method_registry(
            present_methods,
            benchmark_roles=LBIDD_BENCHMARK_ROLES,
        )
        method_presence = compute_method_presence(report, LBIDD_GATE_METHOD_SET)
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
        prioritization_metrics = summarize_method_records(
            report,
            attribute="prioritization_metrics",
            reducer=summarize_prioritization_metrics,
        )
        flagship_scorecard = build_flagship_scorecard(
            flagship_method=LBIDD_FLAGSHIP_METHOD,
            aggregate_metrics=aggregate_summary,
            ranking_summary=ranking_summary,
            thresholds={
                "mean_rank_max": 2,
                "max_deviation_from_best_max": 0.10,
                "top_quartile_failures_max": 0,
                "failure_rate_mean_max": 0.25,
            },
            gate_method_set=LBIDD_GATE_METHOD_SET,
            method_presence=method_presence,
        )
        with open(args.json_out, "w") as f:
            json.dump(
                build_report_payload(
                    report,
                    suite_id="estimation_lbidd",
                    mode=mode.value,
                    preflight=preflight,
                    sub_circuit="lbidd",
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
                    gate_method_set=list(LBIDD_GATE_METHOD_SET),
                    flagship_presence=method_presence.get(LBIDD_FLAGSHIP_METHOD, {}),
                    exploratory_methods=[
                        method_name
                        for method_name, meta in method_manifest.items()
                        if meta.get("benchmark_role") == "exploratory"
                    ],
                    selection_manifest=selection_manifest,
                    overlap_diagnostics=overlap_diagnostics,
                    calibration_metrics=calibration_metrics,
                    prioritization_metrics=prioritization_metrics,
                    claim_profile_targets=["full_stack_publication_claim"],
                    literature_anchor=LBIDD_LITERATURE_ANCHOR,
                    public_claim_eligible=True,
                    blockers=[case.name for case in report.cases if not case.passed],
                    extra={"method_profile": method_profile},
                ),
                f,
                indent=2,
            )

    n_fail = sum(
        1 for cr in report.cases if cr.verdict not in (Verdict.PASS.value, Verdict.PASS)
    )
    sys.exit(0 if n_fail == 0 else 2)


if __name__ == "__main__":
    main()
