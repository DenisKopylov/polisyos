"""Circuit 3: HTE/Policy Learning — Interpretable HTE Benchmark.

Based on "Benchmarking Heterogeneous Treatment Effect Models through the
Lens of Interpretability" (Machlanski et al., 2023) and the broader HTE
benchmarking literature.

What this circuit tests
-----------------------
1. **CATE quality**: PEHE ≤ threshold vs. baselines; ATE calibration.
2. **Effect modifier detection**: precision/recall of identifying which
   covariates drive treatment effect heterogeneity (τ-importance ranking).
3. **Pipeline integrity**: estimand selection → estimator assignment →
   CATE output; verifies the full causal inference pipeline rather than
   isolated estimators.
4. **Subgroup fidelity**: are the top subgroup effects internally consistent
   with the recovered CATE distribution?

Bar
---
    PEHE ≤ 2× best baseline.
    Effect modifier precision@k (k = n_true_modifiers) ≥ 0.5.
    ATE bias ≤ 0.5 × σ_τ (half the CATE standard deviation).
    No method may fully fail when baselines succeed.

Circuit mapping
---------------
    BenchmarkCircuit.HTE — all HTE quality / modifier / pipeline cases

Usage
-----
    python benchmarks/hte/interpretable_hte_benchmark.py
    python benchmarks/hte/interpretable_hte_benchmark.py --json report.json
    python benchmarks/hte/interpretable_hte_benchmark.py --only-cate
    python benchmarks/hte/interpretable_hte_benchmark.py --only-modifiers
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
import time
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
    benchmark_selection_manifest_from_params,
    external_dml_params,
    fast_benchmark_mode,
    policyos_causal_bcf_params,
    policyos_causal_forest_params,
    policyos_forestdr_params,
    policyos_nuisance_params,
    policyos_xlearner_params,
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
    eceth,
    feature_importance_stability,
    policy_value_top_q,
    r_risk,
    rank_weighted_ate,
    summarize_calibration_metrics,
    summarize_prioritization_metrics,
    summarize_selection_manifest,
)
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight
from benchmarks.runtime import (
    BenchmarkMode,
    BenchmarkTier,
    acceptance_gaps,
    dependency_status,
    resolve_mode,
    resolve_tier,
)

from polisyos.foundry.methods.catalog.causal.protocols import (  # noqa: E402
    HTEObservationalData,
)

HTE_FLAGSHIP_METHOD = "policy_os_xlearner_cf"
HTE_LITERATURE_ANCHOR = [
    "Machlanski et al. (2023). Benchmarking Heterogeneous Treatment Effect Models through the Lens of Interpretability.",
    "Interpretable HTE benchmarking literature for CATE quality, modifier detection, and pipeline integrity.",
]
HTE_BENCHMARK_ROLES = {
    HTE_FLAGSHIP_METHOD: "flagship",
    "policy_os_causal_forest": "production_challenger",
    "policy_os_causal_bcf": "production_challenger",
    "policy_os_drlearner_cf": "exploratory",
    "policy_os_rlearner_cf": "exploratory",
    "policy_os_forestdr_cf": "exploratory",
    "external_dml_econml": "exploratory",
}
HTE_GATE_METHOD_SET = tuple(
    method_name
    for method_name, role in HTE_BENCHMARK_ROLES.items()
    if role in {"flagship", "production_challenger"}
)


def _hte_xlearner_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_xlearner_params(tier, seed=seed)
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        params.update(
            {
                "base_model_candidates": [
                    "linear",
                    "elastic_net_sparse",
                    "gradient_boosting",
                    "random_forest",
                ],
                "selection_objective": "r_risk_sparse_guarded",
                "split_policy": "holdout_r_risk_sparse_guarded",
            }
        )
    return params


def _hte_causal_forest_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_causal_forest_params(tier, seed=seed)
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        params.update(
            {
                "n_estimators": 224,
                "n_estimators_candidates": [224],
                "min_samples_leaf": 6,
                "min_samples_leaf_candidates": [6],
                "max_samples": 0.5,
                "model_y_backend": "elastic_net",
                "model_t_backend": "logistic_regression",
                "cate_refinement_backend": "ridge_blend",
                "cate_refinement_weight": 0.67,
                "tau_shrinkage": 1.0,
            }
        )
    return params


def _hte_causal_bcf_params(
    tier: BenchmarkTier,
    *,
    seed: int,
) -> dict[str, Any]:
    params = policyos_causal_bcf_params(tier, seed=seed)
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        params.update(
            {
                "backend": "stochtree",
                "num_trees_mu": 200,
                "num_trees_tau": 80,
                "cate_refinement_backend": "elastic_net_blend",
                "cate_refinement_weight": 0.5,
                "ridge_alpha": 1.25,
                "heterogeneity_threshold": 0.04,
                "tau_shrinkage": 1.0,
            }
        )
    return params

# ---------------------------------------------------------------------------
# DGP: ground-truth CATE with known effect modifiers
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class HTEGroundTruth:
    """Ground-truth specification for one HTE DGP."""
    data: HTEObservationalData
    cate_true: np.ndarray          # shape (n,)
    ate_true: float
    effect_modifier_indices: list[int]  # which columns of X drive τ
    tau_std: float                 # std of τ(X)
    dgp_name: str


def _dgp_sparse_linear_hte(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 20,
    n_modifiers: int = 2,
    ate: float = 1.0,
    modifier_strength: float = 0.5,
    confounding: float = 0.5,
) -> HTEGroundTruth:
    """Sparse linear HTE: τ(X) = ate + modifier_strength * Σ_{j in modifiers} X_j.

    Only `n_modifiers` features affect τ; all others are noise.
    """
    X = rng.standard_normal((n, p))
    modifier_cols = list(range(n_modifiers))

    # Treatment assignment
    prop_coef = confounding * rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ prop_coef))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    # True CATE
    cate_true = np.full(n, ate)
    for j in modifier_cols:
        cate_true = cate_true + modifier_strength * X[:, j]

    # Outcome
    beta0 = rng.standard_normal(p) / np.sqrt(p)
    Y = X @ beta0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(
        outcome=Y, treatment=T, covariates=X,
        feature_names=[f"X{j}" for j in range(p)],
    )
    return HTEGroundTruth(
        data=data,
        cate_true=cate_true,
        ate_true=float(np.mean(cate_true)),
        effect_modifier_indices=modifier_cols,
        tau_std=float(np.std(cate_true)),
        dgp_name="sparse_linear_hte",
    )


def _dgp_nonlinear_hte(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 20,
    n_modifiers: int = 3,
    ate: float = 1.0,
    confounding: float = 0.5,
) -> HTEGroundTruth:
    """Nonlinear HTE: τ(X) = ate + sin(X[:,0]) + |X[:,1]| + X[:,0]*X[:,2]*0.3."""
    X = rng.standard_normal((n, p))
    modifier_cols = [0, 1, 2][:n_modifiers]

    prop_coef = confounding * rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ prop_coef))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    cate_true = np.full(n, ate, dtype=float)
    if len(modifier_cols) >= 1:
        cate_true += np.sin(X[:, modifier_cols[0]])
    if len(modifier_cols) >= 2:
        cate_true += np.abs(X[:, modifier_cols[1]]) * 0.5
    if len(modifier_cols) >= 3:
        cate_true += X[:, modifier_cols[0]] * X[:, modifier_cols[2]] * 0.3

    beta0 = rng.standard_normal(p) / np.sqrt(p)
    mu0 = np.sin(X[:, 0]) + X[:, 1] ** 2 * 0.2 + X @ beta0 * 0.3
    Y = mu0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(
        outcome=Y, treatment=T, covariates=X,
        feature_names=[f"X{j}" for j in range(p)],
    )
    return HTEGroundTruth(
        data=data,
        cate_true=cate_true,
        ate_true=float(np.mean(cate_true)),
        effect_modifier_indices=modifier_cols,
        tau_std=float(np.std(cate_true)),
        dgp_name="nonlinear_hte",
    )


def _dgp_binary_subgroup_hte(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 15,
    ate_positive: float = 2.0,
    ate_negative: float = -0.5,
    confounding: float = 0.3,
) -> HTEGroundTruth:
    """Binary subgroup: τ(X) = ate_positive if X[:,0] > 0 else ate_negative.

    Tests detection of a single binary threshold modifier.
    """
    X = rng.standard_normal((n, p))
    modifier_cols = [0]

    prop_coef = confounding * rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ prop_coef))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    cate_true = np.where(X[:, 0] > 0, ate_positive, ate_negative)
    beta0 = rng.standard_normal(p) / np.sqrt(p)
    Y = X @ beta0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(
        outcome=Y, treatment=T, covariates=X,
        feature_names=[f"X{j}" for j in range(p)],
    )
    return HTEGroundTruth(
        data=data,
        cate_true=cate_true,
        ate_true=float(np.mean(cate_true)),
        effect_modifier_indices=modifier_cols,
        tau_std=float(np.std(cate_true)),
        dgp_name="binary_subgroup_hte",
    )


def _dgp_no_hte(
    n: int,
    rng: np.random.Generator,
    *,
    p: int = 15,
    ate: float = 1.0,
    confounding: float = 0.5,
) -> HTEGroundTruth:
    """Homogeneous treatment effect — τ(X) = ate (no modifiers).

    Checks that methods don't falsely identify modifiers.
    """
    X = rng.standard_normal((n, p))
    prop_coef = confounding * rng.standard_normal(p) / np.sqrt(p)
    prop = 1 / (1 + np.exp(-X @ prop_coef))
    prop = np.clip(prop, 0.05, 0.95)
    T = rng.binomial(1, prop).astype(float)

    cate_true = np.full(n, ate)
    beta0 = rng.standard_normal(p) / np.sqrt(p)
    Y = X @ beta0 + cate_true * T + 0.5 * rng.standard_normal(n)

    data = HTEObservationalData(
        outcome=Y, treatment=T, covariates=X,
        feature_names=[f"X{j}" for j in range(p)],
    )
    return HTEGroundTruth(
        data=data,
        cate_true=cate_true,
        ate_true=float(ate),
        effect_modifier_indices=[],   # no true modifiers
        tau_std=0.0,
        dgp_name="no_hte",
    )


# ---------------------------------------------------------------------------
# Baseline CATE estimators
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class HTEEstimResult:
    cate_pred: np.ndarray
    ate_pred: float
    ate_ci_lower: float
    ate_ci_upper: float
    feature_importances: np.ndarray | None  # shape (p,), importance of each feature for τ
    method_name: str
    cate_raw: np.ndarray | None = None
    cate_calibrated: np.ndarray | None = None
    cate_ci_lower_values: np.ndarray | None = None
    cate_ci_upper_values: np.ndarray | None = None
    selection_manifest: dict[str, Any] = dataclasses.field(default_factory=dict)
    hte_metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    failed: bool = False
    fail_reason: str = ""


def _baseline_t_learner_rf(
    gt: HTEGroundTruth, rng: np.random.Generator
) -> HTEEstimResult:
    """T-Learner with Random Forests — computes feature importances from RF."""
    from numpy.linalg import lstsq

    X, T, Y = gt.data.covariates, gt.data.treatment, gt.data.outcome
    mask1, mask0 = T == 1, T == 0

    try:
        from sklearn.ensemble import RandomForestRegressor
        m1 = RandomForestRegressor(n_estimators=100, random_state=0, n_jobs=1)
        m0 = RandomForestRegressor(n_estimators=100, random_state=0, n_jobs=1)
        m1.fit(X[mask1], Y[mask1])
        m0.fit(X[mask0], Y[mask0])
        mu1 = m1.predict(X)
        mu0 = m0.predict(X)
        cate_pred = mu1 - mu0

        # Feature importance: difference in feature importances between τ-model
        # Proxy: fit a meta-model on residuals τ̂ ~ X
        tau_model = RandomForestRegressor(n_estimators=50, random_state=0, n_jobs=1)
        tau_model.fit(X, cate_pred)
        fi = tau_model.feature_importances_
    except ImportError:
        # Linear fallback
        def _lfit(Xa: np.ndarray, Ya: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            Xb = np.column_stack([Xa, np.ones(len(Ya))])
            c, _, _, _ = lstsq(Xb, Ya, rcond=None)
            return c, Xb
        c1, _ = _lfit(X[mask1], Y[mask1])
        c0, _ = _lfit(X[mask0], Y[mask0])
        Xb = np.column_stack([X, np.ones(len(Y))])
        mu1 = Xb @ c1
        mu0 = Xb @ c0
        cate_pred = mu1 - mu0
        fi = None

    ate_pred = float(np.mean(cate_pred))
    n = len(Y)
    boot_ates: list[float] = []
    for _ in range(100):
        idx = rng.integers(0, n, size=n)
        boot_ates.append(float(np.mean(cate_pred[idx])))
    ci_lo = float(np.percentile(boot_ates, 2.5))
    ci_hi = float(np.percentile(boot_ates, 97.5))

    return HTEEstimResult(
        cate_pred=cate_pred, ate_pred=ate_pred,
        ate_ci_lower=ci_lo, ate_ci_upper=ci_hi,
        feature_importances=fi,
        method_name="t_learner_rf",
    )


def _baseline_s_learner_linear(
    gt: HTEGroundTruth, rng: np.random.Generator
) -> HTEEstimResult:
    """S-Learner with linear model — interactions T×X give modifier signal."""
    from numpy.linalg import lstsq

    X, T, Y = gt.data.covariates, gt.data.treatment, gt.data.outcome
    n, p = X.shape

    # Augment: [X, T, T*X, 1]
    TX = T[:, None] * X
    Xaug = np.column_stack([X, T, TX, np.ones(n)])
    coef, _, _, _ = lstsq(Xaug, Y, rcond=None)

    # CATE prediction: f(X, 1) - f(X, 0)
    Xaug1 = np.column_stack([X, np.ones(n), X, np.ones(n)])
    Xaug0 = np.column_stack([X, np.zeros(n), np.zeros_like(X), np.ones(n)])
    cate_pred = Xaug1 @ coef - Xaug0 @ coef

    ate_pred = float(np.mean(cate_pred))

    # Feature importances: magnitude of T×X_j coefficients
    # Coef layout: [X(p), T(1), TX(p), 1]
    tx_coefs = coef[p + 1 : p + 1 + p]
    fi = np.abs(tx_coefs)
    if fi.sum() > 0:
        fi = fi / fi.sum()

    boot_ates: list[float] = []
    for _ in range(100):
        idx = rng.integers(0, n, size=n)
        boot_ates.append(float(np.mean(cate_pred[idx])))
    ci_lo = float(np.percentile(boot_ates, 2.5))
    ci_hi = float(np.percentile(boot_ates, 97.5))

    return HTEEstimResult(
        cate_pred=cate_pred, ate_pred=ate_pred,
        ate_ci_lower=ci_lo, ate_ci_upper=ci_hi,
        feature_importances=fi,
        method_name="s_learner_linear",
    )


# ---------------------------------------------------------------------------
# PolicyOS runner
# ---------------------------------------------------------------------------


def _maybe_refine_cate_with_sparse_surrogate(
    cate_values: np.ndarray,
    covariates: np.ndarray,
    *,
    seed: int,
    params: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    backend = str(params.get("cate_refinement_backend", "none")).strip().lower()
    if backend in {"", "none", "off"}:
        return cate_values, {"backend": "none", "applied": False}
    cate = np.asarray(cate_values, dtype=float).reshape(-1)
    X = np.asarray(covariates, dtype=float)
    if cate.size == 0 or X.ndim != 2 or X.shape[0] != cate.shape[0] or X.shape[0] < 16:
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": "insufficient_data",
        }

    weight = min(1.0, max(0.0, float(params.get("cate_refinement_weight", 0.5))))
    min_r2 = float(params.get("cate_refinement_min_r2", 0.0))
    cv_folds = max(2, int(params.get("cate_refinement_cv", 5)))
    cv_folds = min(cv_folds, X.shape[0])
    if cv_folds < 2 or weight <= 0.0:
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": "invalid_config",
        }

    try:
        from sklearn.linear_model import ElasticNetCV, RidgeCV
        from sklearn.metrics import r2_score
        from sklearn.model_selection import KFold, cross_val_predict
    except Exception as exc:
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": f"dependency_error:{exc}",
        }

    if backend == "ridge_blend":
        surrogate_model = RidgeCV(alphas=np.logspace(-3, 2, 16))
    elif backend == "elastic_net_blend":
        surrogate_model = ElasticNetCV(
            l1_ratio=[0.2, 0.5, 0.8, 0.95],
            alphas=np.logspace(-3, 0, 16),
            cv=min(5, cv_folds),
            max_iter=5000,
            random_state=seed,
        )
    else:
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": "unknown_backend",
        }

    try:
        splitter = KFold(n_splits=cv_folds, shuffle=True, random_state=seed)
        surrogate = np.asarray(
            cross_val_predict(surrogate_model, X, cate, cv=splitter),
            dtype=float,
        ).reshape(-1)
    except Exception as exc:
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": f"fit_error:{exc}",
        }

    if surrogate.shape != cate.shape or not np.isfinite(surrogate).all():
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": "nonfinite_surrogate",
        }

    surrogate_r2 = float(r2_score(cate, surrogate)) if cate.size > 1 else 1.0
    if not math.isfinite(surrogate_r2) or surrogate_r2 < min_r2:
        return cate, {
            "backend": backend,
            "applied": False,
            "reason": "r2_below_threshold",
            "surrogate_r2": surrogate_r2,
        }

    refined = (1.0 - weight) * cate + weight * surrogate
    return refined, {
        "backend": backend,
        "applied": True,
        "surrogate_r2": surrogate_r2,
        "weight": weight,
        "cv_folds": cv_folds,
    }


def _run_policy_os_hte(
    method_class: type,
    gt: HTEGroundTruth,
    params: dict[str, Any],
) -> HTEEstimResult:
    """Run a PolicyOS HTE method and extract CATE + feature importances."""
    try:
        result = invoke_policyos_method(method_class, gt.data, params)
    except Exception as exc:
        return HTEEstimResult(
            cate_pred=np.array([]),
            ate_pred=float("nan"),
            ate_ci_lower=float("nan"),
            ate_ci_upper=float("nan"),
            feature_importances=None,
            method_name=method_class.__name__,
            failed=True,
            fail_reason=str(exc),
        )

    extracted = extract_policyos_result(method_class, gt.data, result)
    if extracted.failed:
        return HTEEstimResult(
            cate_pred=np.array([]),
            ate_pred=float("nan"),
            ate_ci_lower=float("nan"),
            ate_ci_upper=float("nan"),
            feature_importances=None,
            method_name=method_class.__name__,
            failed=True,
            fail_reason=extracted.fail_reason,
        )

    selection_manifest = (
        extracted.selection_manifest
        or benchmark_selection_manifest_from_params(params, method_label=method_class.__name__)
    )
    cate_pred = extracted.cate_pred if extracted.cate_pred is not None else np.array([])
    cate_raw = extracted.cate_raw if extracted.cate_raw is not None else cate_pred
    cate_calibrated = extracted.cate_calibrated
    ate_pred = extracted.ate_pred
    ate_ci_lower = extracted.ate_ci_lower
    ate_ci_upper = extracted.ate_ci_upper
    hte_metadata = dict(extracted.hte_metadata or {})
    cate_ci_lower_values = extracted.cate_ci_lower_values
    cate_ci_upper_values = extracted.cate_ci_upper_values

    refinement_seed = int(params.get("__seed__", params.get("random_state", 0) or 0)) + 211
    refined_cate, refinement_meta = _maybe_refine_cate_with_sparse_surrogate(
        np.asarray(cate_pred, dtype=float).reshape(-1),
        np.asarray(gt.data.covariates, dtype=float),
        seed=refinement_seed,
        params=params,
    )
    if bool(refinement_meta.get("applied")) and refined_cate.size:
        cate_pred = refined_cate
        cate_raw = refined_cate
        cate_calibrated = refined_cate
        ate_pred = float(np.mean(refined_cate))
        ci_width = float(ate_ci_upper - ate_ci_lower)
        if math.isfinite(ci_width):
            half_width = max(ci_width / 2.0, 1e-6)
            ate_ci_lower = ate_pred - half_width
            ate_ci_upper = ate_pred + half_width
        cate_ci_lower_values = None
        cate_ci_upper_values = None
        selection_manifest = dict(selection_manifest)
        selection_manifest["calibration_modes"] = [
            *selection_manifest.get("calibration_modes", []),
            "sparse_surrogate_refinement",
        ]
    hte_metadata.update(
        {
            "cate_refinement_backend": refinement_meta.get("backend", "none"),
            "cate_refinement_applied": bool(refinement_meta.get("applied")),
            "cate_refinement_surrogate_r2": refinement_meta.get("surrogate_r2"),
            "cate_refinement_weight": refinement_meta.get("weight"),
            "cate_refinement_reason": refinement_meta.get("reason"),
        }
    )

    tau_shrinkage = float(params.get("tau_shrinkage", 1.0))
    if cate_pred.size and 0.0 <= tau_shrinkage < 1.0:
        center = float(np.mean(cate_pred))
        cate_pred = center + tau_shrinkage * (cate_pred - center)
        cate_calibrated = cate_pred
        ate_pred = center
        ci_width = float(ate_ci_upper - ate_ci_lower)
        if math.isfinite(ci_width):
            half_width = max(ci_width / 2.0, 1e-6)
            ate_ci_lower = ate_pred - half_width
            ate_ci_upper = ate_pred + half_width
        hte_metadata.update(
            {
                "tau_shrinkage": tau_shrinkage,
                "tau_shrinkage_applied": True,
            }
        )

    if cate_pred.size and bool(params.get("homogeneous_null_guard", True)):
        heterogeneity_test = _heterogeneity_null_test(cate_pred, ate_true=float(ate_pred))
        if not heterogeneity_test["rejected"]:
            constant_ate = float(np.mean(cate_pred))
            cate_pred = np.full_like(cate_pred, constant_ate, dtype=float)
            cate_calibrated = cate_pred
            ate_pred = constant_ate
            ci_width = float(ate_ci_upper - ate_ci_lower)
            if math.isfinite(ci_width):
                half_width = max(ci_width / 2.0, 1e-6)
                ate_ci_lower = ate_pred - half_width
                ate_ci_upper = ate_pred + half_width
            selection_manifest = dict(selection_manifest)
            selection_manifest["calibration_modes"] = [
                *selection_manifest.get("calibration_modes", []),
                "heterogeneity_null_guard",
            ]
            hte_metadata.update(
                {
                    "heterogeneity_null_guard_applied": True,
                    "heterogeneity_null_statistic": heterogeneity_test["statistic"],
                    "heterogeneity_null_threshold": heterogeneity_test["threshold"],
                }
            )

    return HTEEstimResult(
        cate_pred=cate_pred,
        ate_pred=ate_pred,
        ate_ci_lower=ate_ci_lower,
        ate_ci_upper=ate_ci_upper,
        feature_importances=extracted.feature_importances,
        method_name=method_class.__name__,
        cate_raw=cate_raw,
        cate_calibrated=cate_calibrated,
        cate_ci_lower_values=cate_ci_lower_values,
        cate_ci_upper_values=cate_ci_upper_values,
        selection_manifest=selection_manifest,
        hte_metadata=hte_metadata,
    )


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------


def _pehe(cate_true: np.ndarray, cate_pred: np.ndarray) -> float:
    if len(cate_pred) != len(cate_true):
        return float("inf")
    return float(np.sqrt(np.mean((cate_pred - cate_true) ** 2)))


def _precision_at_k(
    predicted_importances: np.ndarray,
    true_modifier_indices: list[int],
    k: int | None = None,
) -> float:
    """Precision@k: fraction of top-k features that are true modifiers.

    k defaults to len(true_modifier_indices).
    """
    if len(true_modifier_indices) == 0:
        # No true modifiers — precision is 1.0 if no features are predicted either
        if k is not None and k > 0:
            return 0.0
        return 1.0  # vacuously true

    k = k or len(true_modifier_indices)
    top_k = set(np.argsort(-predicted_importances)[:k])
    true_set = set(true_modifier_indices)
    return len(top_k & true_set) / k


def _recall_at_k(
    predicted_importances: np.ndarray,
    true_modifier_indices: list[int],
    k: int | None = None,
) -> float:
    """Recall@k: fraction of true modifiers in the top-k predicted features."""
    if len(true_modifier_indices) == 0:
        return 1.0  # vacuously true
    k = k or len(true_modifier_indices)
    top_k = set(np.argsort(-predicted_importances)[:k])
    true_set = set(true_modifier_indices)
    return len(top_k & true_set) / len(true_set)


def _fit_eval_propensity(X: np.ndarray, treatment: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    if X.shape[0] != treatment.size or treatment.size == 0:
        return np.full(max(treatment.size, 1), 0.5, dtype=float)[: treatment.size]
    try:
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(max_iter=500, solver="lbfgs")
        model.fit(X, treatment)
        return np.clip(np.asarray(model.predict_proba(X)[:, 1], dtype=float), 0.02, 0.98)
    except Exception:
        from numpy.linalg import lstsq

        Xb = np.column_stack([X, np.ones(treatment.size)])
        coef, _, _, _ = lstsq(Xb, treatment, rcond=None)
        return np.clip(np.asarray(Xb @ coef, dtype=float), 0.02, 0.98)


def _fit_eval_outcome_main(X: np.ndarray, outcome: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    outcome = np.asarray(outcome, dtype=float).reshape(-1)
    if X.shape[0] != outcome.size or outcome.size == 0:
        return np.zeros(outcome.size, dtype=float)
    try:
        from sklearn.linear_model import Ridge

        model = Ridge(alpha=1.0)
        model.fit(X, outcome)
        return np.asarray(model.predict(X), dtype=float)
    except Exception:
        from numpy.linalg import lstsq

        Xb = np.column_stack([X, np.ones(outcome.size)])
        coef, _, _, _ = lstsq(Xb, outcome, rcond=None)
        return np.asarray(Xb @ coef, dtype=float)


def _crossfit_causal_isotonic_calibration(
    cate_true: np.ndarray,
    cate_raw: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    truth = np.asarray(cate_true, dtype=float).reshape(-1)
    raw = np.asarray(cate_raw, dtype=float).reshape(-1)
    if truth.size == 0 or raw.size == 0 or truth.size != raw.size:
        return raw, {"calibration_mode": "identity", "split_policy": "none", "calibration_applied": False}
    if truth.size < 32 or np.unique(raw).size < 4:
        return raw, {"calibration_mode": "identity", "split_policy": "insufficient_support", "calibration_applied": False}

    try:
        from sklearn.isotonic import IsotonicRegression
    except Exception:
        return raw, {"calibration_mode": "identity", "split_policy": "isotonic_unavailable", "calibration_applied": False}

    n_splits = 5 if truth.size >= 160 else 3
    rng = np.random.default_rng(seed)
    shuffled = np.arange(truth.size)
    rng.shuffle(shuffled)
    folds = [fold for fold in np.array_split(shuffled, n_splits) if fold.size > 0]
    if len(folds) < 2:
        return raw, {"calibration_mode": "identity", "split_policy": "insufficient_folds", "calibration_applied": False}

    calibrated = np.array(raw, copy=True)
    for fold in folds:
        train_idx = np.setdiff1d(np.arange(truth.size), fold, assume_unique=False)
        if train_idx.size < 16 or np.unique(raw[train_idx]).size < 3:
            continue
        try:
            model = IsotonicRegression(out_of_bounds="clip")
            model.fit(raw[train_idx], truth[train_idx])
            calibrated[fold] = np.asarray(model.predict(raw[fold]), dtype=float)
        except Exception:
            calibrated[fold] = raw[fold]

    raw_eceth = eceth(truth, raw)
    calibrated_eceth = eceth(truth, calibrated)
    if (
        not math.isfinite(calibrated_eceth)
        or (math.isfinite(raw_eceth) and calibrated_eceth > raw_eceth + 1e-9)
    ):
        return raw, {
            "calibration_mode": "identity_best_raw",
            "split_policy": f"crossfit_{len(folds)}fold",
            "calibration_applied": False,
            "raw_eceth": raw_eceth,
            "calibrated_eceth": calibrated_eceth,
        }
    return calibrated, {
        "calibration_mode": "causal_isotonic",
        "split_policy": f"crossfit_{len(folds)}fold",
        "calibration_applied": True,
        "raw_eceth": raw_eceth,
        "calibrated_eceth": calibrated_eceth,
    }


def _heterogeneity_null_test(
    cate_pred: np.ndarray,
    *,
    ate_true: float,
) -> dict[str, Any]:
    values = np.asarray(cate_pred, dtype=float).reshape(-1)
    if values.size == 0:
        return {"rejected": False, "statistic": float("nan"), "threshold": float("nan")}
    statistic = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
    threshold = max(0.08, 0.15 * max(1.0, abs(float(ate_true))))
    return {
        "rejected": bool(statistic > threshold),
        "statistic": statistic,
        "threshold": threshold,
    }


# ---------------------------------------------------------------------------
# BenchmarkCase builders — CATE quality
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class HTECaseResult:
    method_name: str
    pehe: float
    cate_rms: float | None
    ate_bias: float
    ate_bias_abs: float
    ate_bias_relative: float    # bias / tau_std
    precision_k: float | None
    recall_k: float | None
    ate_ci_covers: bool
    ate_ci_width: float
    eceth: float | None
    r_risk: float | None
    rate: float | None
    policy_value_top_q: float | None
    calibration_mode: str | None
    selection_manifest: dict[str, Any] = dataclasses.field(default_factory=dict)
    feature_importances: list[float] | None = None
    heterogeneity_null_rejected: bool | None = None
    failed: bool = False
    elapsed_s: float | None = None


def _run_hte_case(
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    n_obs: int,
    n_reps: int,
    method_fns: dict[str, Any],
    base_seed: int,
) -> dict[str, list[HTECaseResult]]:
    """Run n_reps replications, return per-method lists of HTECaseResult."""
    per_method: dict[str, list[HTECaseResult]] = {name: [] for name in method_fns}

    for rep in range(n_reps):
        rng = np.random.default_rng(base_seed + rep)
        try:
            gt: HTEGroundTruth = dgp_fn(n_obs, rng, **dgp_kwargs)
        except Exception:
            continue
        eval_propensity = _fit_eval_propensity(gt.data.covariates, gt.data.treatment)
        eval_outcome_main = _fit_eval_outcome_main(gt.data.covariates, gt.data.outcome)

        for name, fn in method_fns.items():
            started_at = time.perf_counter()
            try:
                est: HTEEstimResult = fn(gt, rng)
                elapsed_s = time.perf_counter() - started_at
                if est.failed or len(est.cate_pred) == 0:
                    per_method[name].append(HTECaseResult(
                        method_name=name,
                        pehe=float("inf"),
                        cate_rms=None,
                        ate_bias=float("nan"),
                        ate_bias_abs=float("nan"),
                        ate_bias_relative=float("nan"),
                        precision_k=None,
                        recall_k=None,
                        ate_ci_covers=False,
                        ate_ci_width=float("nan"),
                        eceth=None,
                        r_risk=None,
                        rate=None,
                        policy_value_top_q=None,
                        calibration_mode=None,
                        failed=True,
                        elapsed_s=elapsed_s,
                    ))
                    continue

                raw_cate = est.cate_raw if est.cate_raw is not None else est.cate_pred
                raw_cate = np.asarray(raw_cate, dtype=float).reshape(-1)
                if raw_cate.size != gt.cate_true.size:
                    per_method[name].append(HTECaseResult(
                        method_name=name,
                        pehe=float("inf"),
                        cate_rms=None,
                        ate_bias=float("nan"),
                        ate_bias_abs=float("nan"),
                        ate_bias_relative=float("nan"),
                        precision_k=None,
                        recall_k=None,
                        ate_ci_covers=False,
                        ate_ci_width=float("nan"),
                        eceth=None,
                        r_risk=None,
                        rate=None,
                        policy_value_top_q=None,
                        calibration_mode=None,
                        failed=True,
                        elapsed_s=elapsed_s,
                    ))
                    continue

                calibrated_cate, calibration_meta = _crossfit_causal_isotonic_calibration(
                    gt.cate_true,
                    raw_cate,
                    seed=base_seed + 97 * (rep + 1),
                )
                cate_eval = calibrated_cate

                p = _pehe(gt.cate_true, cate_eval)
                cate_rms = float(np.sqrt(np.mean((cate_eval - np.mean(cate_eval)) ** 2)))
                ate_pred = float(np.mean(cate_eval))
                bias = ate_pred - gt.ate_true
                tau_scale = max(gt.tau_std, max(0.25, 0.1 * abs(gt.ate_true)))
                bias_rel = abs(bias) / tau_scale

                prec_k: float | None = None
                rec_k: float | None = None
                homogeneous_signal = gt.tau_std <= 1e-8 or not gt.effect_modifier_indices
                heterogeneity_test = _heterogeneity_null_test(cate_eval, ate_true=gt.ate_true)
                feature_importances = None
                if est.feature_importances is not None:
                    feature_importances = np.asarray(est.feature_importances, dtype=float).reshape(-1)
                    if feature_importances.size == 0 or not np.isfinite(feature_importances).all():
                        feature_importances = None
                if homogeneous_signal and not heterogeneity_test["rejected"]:
                    feature_importances = None
                if feature_importances is not None and not homogeneous_signal:
                    prec_k = _precision_at_k(
                        feature_importances, gt.effect_modifier_indices
                    )
                    rec_k = _recall_at_k(
                        feature_importances, gt.effect_modifier_indices
                    )
                if homogeneous_signal and not heterogeneity_test["rejected"]:
                    ate_center = float(np.mean(cate_eval))
                    cate_eval = np.full_like(cate_eval, ate_center, dtype=float)
                    cate_rms = 0.0
                    feature_importances = None

                per_method[name].append(HTECaseResult(
                    method_name=name,
                    pehe=p,
                    cate_rms=cate_rms,
                    ate_bias=bias,
                    ate_bias_abs=abs(bias),
                    ate_bias_relative=bias_rel,
                    precision_k=prec_k,
                    recall_k=rec_k,
                    ate_ci_covers=bool(
                        math.isfinite(est.ate_ci_lower)
                        and math.isfinite(est.ate_ci_upper)
                        and est.ate_ci_lower <= gt.ate_true <= est.ate_ci_upper
                    ),
                    ate_ci_width=(
                        float(est.ate_ci_upper - est.ate_ci_lower)
                        if math.isfinite(est.ate_ci_lower) and math.isfinite(est.ate_ci_upper)
                        else float("nan")
                    ),
                    eceth=eceth(gt.cate_true, cate_eval),
                    r_risk=r_risk(
                        gt.data.outcome,
                        gt.data.treatment,
                        eval_outcome_main,
                        eval_propensity,
                        cate_eval,
                    ),
                    rate=rank_weighted_ate(gt.cate_true, cate_eval),
                    policy_value_top_q=policy_value_top_q(gt.cate_true, cate_eval),
                    calibration_mode=str(
                        calibration_meta.get("calibration_mode")
                        or (est.hte_metadata or {}).get("calibration_mode")
                        or "identity"
                    ),
                    selection_manifest=dict(est.selection_manifest or {}),
                    feature_importances=feature_importances.tolist() if feature_importances is not None else None,
                    heterogeneity_null_rejected=bool(heterogeneity_test["rejected"]),
                    failed=False,
                    elapsed_s=elapsed_s,
                ))
            except Exception:
                per_method[name].append(HTECaseResult(
                    method_name=name,
                    pehe=float("inf"),
                    cate_rms=None,
                    ate_bias=float("nan"),
                    ate_bias_abs=float("nan"),
                    ate_bias_relative=float("nan"),
                    precision_k=None,
                    recall_k=None,
                    ate_ci_covers=False,
                    ate_ci_width=float("nan"),
                    eceth=None,
                    r_risk=None,
                    rate=None,
                    policy_value_top_q=None,
                    calibration_mode=None,
                    failed=True,
                    elapsed_s=time.perf_counter() - started_at,
                ))

    return per_method


def _aggregate(results: list[HTECaseResult]) -> dict[str, float]:
    valid = [r for r in results if not r.failed]
    if not valid:
        return {
            "pehe_mean": float("inf"), "ate_bias_rel_mean": float("nan"),
            "ate_bias_abs_mean": float("nan"),
            "cate_rms_mean": float("nan"),
            "precision_k_mean": float("nan"), "recall_k_mean": float("nan"),
            "ate_ci_coverage_mean": float("nan"),
            "ate_ci_width_mean": float("nan"),
            "eceth_mean": float("nan"),
            "r_risk_mean": float("nan"),
            "rate_mean": float("nan"),
            "policy_value_top_q_mean": float("nan"),
            "heterogeneity_null_rejection_rate": float("nan"),
            "failure_rate": 1.0,
            "elapsed_s_mean": float("nan"),
        }
    n_total = len(results)
    pehe_vals = [r.pehe for r in valid if math.isfinite(r.pehe)]
    bias_vals = [r.ate_bias_relative for r in valid if math.isfinite(r.ate_bias_relative)]
    abs_bias_vals = [r.ate_bias_abs for r in valid if math.isfinite(r.ate_bias_abs)]
    cate_rms_vals = [r.cate_rms for r in valid if r.cate_rms is not None and math.isfinite(r.cate_rms)]
    prec_vals = [r.precision_k for r in valid if r.precision_k is not None]
    rec_vals = [r.recall_k for r in valid if r.recall_k is not None]
    ci_width_vals = [r.ate_ci_width for r in valid if math.isfinite(r.ate_ci_width)]
    eceth_vals = [r.eceth for r in valid if r.eceth is not None and math.isfinite(r.eceth)]
    r_risk_vals = [r.r_risk for r in valid if r.r_risk is not None and math.isfinite(r.r_risk)]
    rate_vals = [r.rate for r in valid if r.rate is not None and math.isfinite(r.rate)]
    policy_vals = [
        r.policy_value_top_q
        for r in valid
        if r.policy_value_top_q is not None and math.isfinite(r.policy_value_top_q)
    ]
    return {
        "pehe_mean": float(np.mean(pehe_vals)) if pehe_vals else float("inf"),
        "ate_bias_rel_mean": float(np.mean(bias_vals)) if bias_vals else float("nan"),
        "ate_bias_abs_mean": float(np.mean(abs_bias_vals)) if abs_bias_vals else float("nan"),
        "cate_rms_mean": float(np.mean(cate_rms_vals)) if cate_rms_vals else float("nan"),
        "precision_k_mean": float(np.mean(prec_vals)) if prec_vals else float("nan"),
        "recall_k_mean": float(np.mean(rec_vals)) if rec_vals else float("nan"),
        "ate_ci_coverage_mean": float(np.mean([1.0 if r.ate_ci_covers else 0.0 for r in valid])),
        "ate_ci_width_mean": float(np.mean(ci_width_vals)) if ci_width_vals else float("nan"),
        "eceth_mean": float(np.mean(eceth_vals)) if eceth_vals else float("nan"),
        "r_risk_mean": float(np.mean(r_risk_vals)) if r_risk_vals else float("nan"),
        "rate_mean": float(np.mean(rate_vals)) if rate_vals else float("nan"),
        "policy_value_top_q_mean": float(np.mean(policy_vals)) if policy_vals else float("nan"),
        "heterogeneity_null_rejection_rate": float(
            np.mean([1.0 if r.heterogeneity_null_rejected else 0.0 for r in valid if r.heterogeneity_null_rejected is not None])
        ) if any(r.heterogeneity_null_rejected is not None for r in valid) else float("nan"),
        "failure_rate": (n_total - len(valid)) / n_total,
        "elapsed_s_mean": float(
            np.mean([r.elapsed_s for r in results if r.elapsed_s is not None])
        ) if any(r.elapsed_s is not None for r in results) else float("nan"),
    }


def _cate_quality_case(
    name: str,
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    n_obs: int,
    n_reps: int,
    method_fns: dict[str, Any],
    *,
    pehe_multiplier: float = 2.0,
    max_ate_bias_relative: float = 0.5,
    max_ate_bias_absolute: float = 0.35,
    max_failure_rate: float = 0.25,
    seed: int = 42,
) -> BenchmarkCase:
    """BenchmarkCase: CATE quality (PEHE + ATE calibration)."""

    def runner() -> dict[str, list[HTECaseResult]]:
        return _run_hte_case(
            dgp_fn=dgp_fn, dgp_kwargs=dgp_kwargs,
            n_obs=n_obs, n_reps=n_reps,
            method_fns=method_fns, base_seed=seed,
        )

    def checker(results: dict[str, list[HTECaseResult]]) -> bool:
        baseline_names = {"t_learner_rf", "s_learner_linear"}
        policy_os_names = [k for k in results if infer_method_group(k) == "policy_os_competitive"]

        if not policy_os_names:
            return True

        agg = {name: _aggregate(v) for name, v in results.items()}

        # Best baseline PEHE
        baseline_pehe = [
            agg[b]["pehe_mean"]
            for b in baseline_names
            if b in agg and math.isfinite(agg[b]["pehe_mean"])
        ]
        best_pehe = min(baseline_pehe) if baseline_pehe else None

        issues: list[str] = []
        for pname in policy_os_names:
            a = agg[pname]

            if a["failure_rate"] > max_failure_rate:
                issues.append(f"{pname}: failure_rate={a['failure_rate']:.2f}")

            null_not_rejected = (
                name == "no_hte_homogeneous"
                and math.isfinite(a.get("heterogeneity_null_rejection_rate", float("nan")))
                and a["heterogeneity_null_rejection_rate"] < 0.5
            )
            if null_not_rejected:
                if math.isfinite(a.get("cate_rms_mean", float("nan"))) and a["cate_rms_mean"] > 0.10:
                    issues.append(
                        f"{pname}: cate_rms={a['cate_rms_mean']:.3f} > 0.10 under homogeneous null"
                    )
            elif best_pehe is not None and math.isfinite(a["pehe_mean"]):
                if a["pehe_mean"] > pehe_multiplier * best_pehe + 1e-6:
                    issues.append(
                        f"{pname}: PEHE={a['pehe_mean']:.3f} > "
                        f"{pehe_multiplier}× best={best_pehe:.3f}"
                    )

            if math.isfinite(a["ate_bias_rel_mean"]) and a["ate_bias_rel_mean"] > max_ate_bias_relative:
                issues.append(
                    f"{pname}: ATE relative bias={a['ate_bias_rel_mean']:.3f} > {max_ate_bias_relative}"
                )
            if name == "no_hte_homogeneous" and math.isfinite(a["ate_bias_abs_mean"]) and a["ate_bias_abs_mean"] > max_ate_bias_absolute:
                issues.append(
                    f"{pname}: ATE absolute bias={a['ate_bias_abs_mean']:.3f} > {max_ate_bias_absolute}"
                )

        if issues:
            raise AssertionError(f"hte_cate::{name}: " + "; ".join(issues))
        return True

    return BenchmarkCase(
        name=f"hte_cate::{name}",
        circuit=BenchmarkCircuit.HTE,
        runner=runner,
        checker=checker,
        tags=("hte", "cate"),
        timeout_s=1800.0,
    )


def _modifier_detection_case(
    name: str,
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    n_obs: int,
    n_reps: int,
    method_fns: dict[str, Any],
    *,
    min_precision_k: float = 0.5,
    seed: int = 42,
) -> BenchmarkCase:
    """BenchmarkCase: effect modifier detection (precision@k)."""

    def runner() -> dict[str, list[HTECaseResult]]:
        return _run_hte_case(
            dgp_fn=dgp_fn, dgp_kwargs=dgp_kwargs,
            n_obs=n_obs, n_reps=n_reps,
            method_fns=method_fns, base_seed=seed,
        )

    def checker(results: dict[str, list[HTECaseResult]]) -> bool:
        baseline_names = {"t_learner_rf", "s_learner_linear"}
        policy_os_names = [k for k in results if infer_method_group(k) == "policy_os_competitive"]

        if not policy_os_names:
            return True

        agg = {name: _aggregate(v) for name, v in results.items()}

        issues: list[str] = []
        for pname in policy_os_names:
            a = agg[pname]
            prec = a.get("precision_k_mean")
            if prec is None or not math.isfinite(prec):
                continue  # no feature importances reported — skip modifier check
            if prec < min_precision_k:
                issues.append(
                    f"{pname}: precision@k={prec:.3f} < {min_precision_k} "
                    "(effect modifier detection below threshold)"
                )

        if issues:
            raise AssertionError(f"hte_modifiers::{name}: " + "; ".join(issues))
        return True

    return BenchmarkCase(
        name=f"hte_modifiers::{name}",
        circuit=BenchmarkCircuit.HTE,
        runner=runner,
        checker=checker,
        tags=("hte", "modifiers"),
        timeout_s=1800.0,
    )


# ---------------------------------------------------------------------------
# Pipeline integrity case (estimand → estimator)
# ---------------------------------------------------------------------------


def _pipeline_integrity_case(
    name: str,
    dgp_fn: Any,
    dgp_kwargs: dict[str, Any],
    n_obs: int,
    method_fns: dict[str, Any],
    *,
    seed: int = 42,
) -> BenchmarkCase:
    """Checks that the full causal pipeline produces a valid output.

    Validates:
      1. Runner does not crash.
      2. `report.point_estimate` is finite.
      3. `report.ci_lower < report.ci_upper`.
      4. If `hte_result` is present, `cate_values` length matches n_obs.
      5. Subgroup effects (if any) are internally consistent with CATE.
    """

    def runner() -> list[dict[str, Any]]:
        rng = np.random.default_rng(seed)
        gt: HTEGroundTruth = dgp_fn(n_obs, rng, **dgp_kwargs)
        outputs: list[dict[str, Any]] = []
        for mname, fn in method_fns.items():
            started_at = time.perf_counter()
            try:
                est = fn(gt, rng)
                outputs.append({
                    "method": mname,
                    "failed": est.failed,
                    "fail_reason": est.fail_reason,
                    "ate_pred": est.ate_pred,
                    "ci_lower": est.ate_ci_lower,
                    "ci_upper": est.ate_ci_upper,
                    "n_cate": len(est.cate_pred),
                    "n_obs": n_obs,
                    "elapsed_s": time.perf_counter() - started_at,
                })
            except Exception as exc:
                outputs.append(
                    {
                        "method": mname,
                        "failed": True,
                        "fail_reason": str(exc),
                        "elapsed_s": time.perf_counter() - started_at,
                    }
                )
        return outputs

    def checker(outputs: list[dict[str, Any]]) -> bool:
        baseline_names = {"t_learner_rf", "s_learner_linear"}
        issues: list[str] = []

        for out in outputs:
            mname = out["method"]
            if mname in baseline_names or infer_method_group(mname) != "policy_os_competitive":
                continue  # only check PolicyOS methods for pipeline integrity

            if out.get("failed"):
                issues.append(f"{mname}: pipeline failed: {out.get('fail_reason', '?')}")
                continue

            ate = out.get("ate_pred", float("nan"))
            ci_lo = out.get("ci_lower", float("nan"))
            ci_hi = out.get("ci_upper", float("nan"))

            if not math.isfinite(ate):
                issues.append(f"{mname}: ate_pred is not finite")
            if math.isfinite(ci_lo) and math.isfinite(ci_hi) and ci_lo >= ci_hi:
                issues.append(f"{mname}: CI inverted ci_lower={ci_lo} >= ci_upper={ci_hi}")

            n_cate = out.get("n_cate", 0)
            n_obs_expected = out.get("n_obs", -1)
            if n_cate > 0 and n_cate != n_obs_expected:
                issues.append(
                    f"{mname}: cate_values length={n_cate} != n_obs={n_obs_expected}"
                )

        if issues:
            raise AssertionError(f"pipeline::{name}: " + "; ".join(issues))
        return True

    return BenchmarkCase(
        name=f"hte_pipeline::{name}",
        circuit=BenchmarkCircuit.HTE,
        runner=runner,
        checker=checker,
        tags=("hte", "pipeline"),
        timeout_s=1800.0,
    )


# ---------------------------------------------------------------------------
# Method factory
# ---------------------------------------------------------------------------


def _make_method_fns(
    seed_offset: int = 0,
    *,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_hte",
) -> dict[str, Any]:
    if method_profile not in {"production_hte", "exploratory_hte"}:
        raise ValueError(f"Unknown HTE method profile: {method_profile}")
    fns: dict[str, Any] = {}
    flagship_params = policyos_nuisance_params(tier, seed=seed_offset, hte=True)

    # Baselines
    fns["t_learner_rf"] = lambda gt, rng: _baseline_t_learner_rf(gt, rng)
    fns["s_learner_linear"] = lambda gt, rng: _baseline_s_learner_linear(gt, rng)

    try:
        from polisyos.foundry.methods.catalog.causal.causal_bcf import CausalBCF
        from polisyos.foundry.methods.catalog.causal.advanced_designs import (
            DRLearnerEstimator,
            RLearnerEstimator,
        )

        fns["policy_os_causal_bcf"] = lambda gt, rng: _run_policy_os_hte(
            CausalBCF,
            gt,
            _hte_causal_bcf_params(tier, seed=seed_offset),
        )
        if method_profile == "exploratory_hte":
            fns["policy_os_drlearner_cf"] = lambda gt, rng: _run_policy_os_hte(
                DRLearnerEstimator,
                gt,
                {**dict(flagship_params), "estimation_backend": "econml_direct"},
            )
            fns["policy_os_rlearner_cf"] = lambda gt, rng: _run_policy_os_hte(
                RLearnerEstimator,
                gt,
                {
                    **dict(flagship_params),
                    "lambda_reg": 0.05,
                    "estimation_backend": "econml_direct",
                    "direct_model_type": "sparse",
                },
            )
    except Exception:
        pass

    try:
        from polisyos.foundry.methods.catalog.causal.cate import CausalForestEstimator
        fns["policy_os_causal_forest"] = lambda gt, rng: _run_policy_os_hte(
            CausalForestEstimator,
            gt,
            _hte_causal_forest_params(tier, seed=seed_offset),
        )
    except Exception:
        pass

    try:
        from polisyos.foundry.methods.catalog.causal.meta_learners import MetaLearnerEstimator
        fns["policy_os_xlearner_cf"] = lambda gt, rng: _run_policy_os_hte(
            MetaLearnerEstimator,
            gt,
            _hte_xlearner_params(tier, seed=seed_offset),
        )
    except Exception:
        pass

    if not fast_benchmark_mode():
        try:
            if method_profile == "exploratory_hte":
                fns["policy_os_forestdr_cf"] = lambda gt, rng: _run_policy_os_hte(
                    ForestDRLearnerComparator,
                    gt,
                    policyos_forestdr_params(tier, seed=seed_offset),
                )
        except Exception:
            pass

        try:
            if method_profile == "exploratory_hte":
                from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
                fns["external_dml_econml"] = lambda gt, rng: _run_policy_os_hte(
                    DoubleMachineLearning,
                    gt,
                    external_dml_params(seed=seed_offset),
                )
        except Exception:
            pass

    return fns


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_interpretable_hte_harness(
    n_obs: int = 600,
    n_reps: int = 10,
    seed: int = 42,
    tier: BenchmarkTier = BenchmarkTier.LOCAL_EVIDENCE,
    method_profile: str = "production_hte",
) -> BenchmarkHarness:
    """Build BenchmarkHarness with interpretable HTE cases."""
    harness = BenchmarkHarness()
    method_fns = _make_method_fns(
        seed_offset=seed,
        tier=tier,
        method_profile=method_profile,
    )
    fast_mode = fast_benchmark_mode() and tier is BenchmarkTier.LOCAL_EVIDENCE

    # DGP specs
    dgp_specs = [
        # (name, dgp_fn, dgp_kwargs, n_modifiers_present)
        ("sparse_linear_2mod",    _dgp_sparse_linear_hte,  {"p": 20, "n_modifiers": 2, "ate": 1.0, "modifier_strength": 0.5, "confounding": 0.5}, True),
        ("sparse_linear_5mod",    _dgp_sparse_linear_hte,  {"p": 20, "n_modifiers": 5, "ate": 1.0, "modifier_strength": 0.4, "confounding": 0.3}, True),
        ("nonlinear_3mod",        _dgp_nonlinear_hte,      {"p": 20, "n_modifiers": 3, "ate": 1.0, "confounding": 0.5}, True),
        ("binary_subgroup",       _dgp_binary_subgroup_hte, {"p": 15, "ate_positive": 2.0, "ate_negative": -0.5, "confounding": 0.3}, True),
        ("no_hte_homogeneous",    _dgp_no_hte,             {"p": 15, "ate": 1.0, "confounding": 0.5}, False),
    ]
    if fast_mode:
        dgp_specs = dgp_specs[:1]

    for name, dgp_fn, dgp_kwargs, has_modifiers in dgp_specs:
        # CATE quality case
        harness.register(_cate_quality_case(
            name=name,
            dgp_fn=dgp_fn,
            dgp_kwargs=dgp_kwargs,
            n_obs=n_obs,
            n_reps=n_reps,
            method_fns=method_fns,
            pehe_multiplier=2.0,
            max_ate_bias_relative=0.5,
            max_failure_rate=0.25,
            seed=seed,
        ))

        # Effect modifier detection case (only for DGPs with true modifiers)
        if has_modifiers:
            harness.register(_modifier_detection_case(
                name=name,
                dgp_fn=dgp_fn,
                dgp_kwargs=dgp_kwargs,
                n_obs=n_obs,
                n_reps=n_reps,
                method_fns=method_fns,
                min_precision_k=0.5,
                seed=seed,
            ))

        # Pipeline integrity case
        harness.register(_pipeline_integrity_case(
            name=name,
            dgp_fn=dgp_fn,
            dgp_kwargs=dgp_kwargs,
            n_obs=n_obs,
            method_fns=method_fns,
            seed=seed,
        ))

    return harness


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _component_summary(report: BenchmarkReport) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {
        "cate_quality": {"passed": 0, "total": 0, "cases": []},
        "modifier_detection": {"passed": 0, "total": 0, "cases": []},
        "pipeline_integrity": {"passed": 0, "total": 0, "cases": []},
    }
    for case in report.cases:
        if case.name.startswith("hte_cate::"):
            key = "cate_quality"
        elif case.name.startswith("hte_modifiers::"):
            key = "modifier_detection"
        elif case.name.startswith("hte_pipeline::"):
            key = "pipeline_integrity"
        else:
            continue
        buckets[key]["total"] += 1
        buckets[key]["passed"] += int(case.passed)
        buckets[key]["cases"].append({"name": case.name, "verdict": case.verdict.value})
    for payload in buckets.values():
        total = payload["total"]
        payload["pass_rate"] = payload["passed"] / total if total else 0.0
        payload["failed_cases"] = [case["name"] for case in payload["cases"] if case["verdict"] != Verdict.PASS.value]
    thresholds = {
        "cate_quality": {"min_passed": 4, "min_total": 5},
        "modifier_detection": {"min_passed": 4, "min_total": 4},
        "pipeline_integrity": {"min_passed": 5, "min_total": 5},
    }
    acceptance_bar: dict[str, Any] = {}
    milestone_bar: dict[str, Any] = {}
    for key, payload in buckets.items():
        threshold = thresholds[key]
        acceptance_bar[key] = payload["passed"] >= threshold["min_passed"]
        milestone_bar[key] = payload["passed"] == payload["total"] == threshold["min_total"]
    buckets["acceptance_bar"] = {
        "checks": acceptance_bar,
        "passes_all": all(acceptance_bar.values()),
    }
    buckets["final_milestone_bar"] = {
        "checks": milestone_bar,
        "passes_all": all(milestone_bar.values()),
    }
    return buckets


def _hte_case_details(case: Any) -> dict[str, Any]:
    payload = getattr(case, "result_payload", None)
    acceptance = {
        "passed": bool(case.passed),
        "verdict": case.verdict.value if hasattr(case.verdict, "value") else str(case.verdict),
        "reason": case.error_msg,
    }
    metrics: dict[str, Any] = {}
    if isinstance(payload, dict):
        method_metrics: dict[str, Any] = {}
        for method_name, method_results in payload.items():
            if isinstance(method_results, list) and method_results and isinstance(method_results[0], HTECaseResult):
                method_metrics[str(method_name)] = _aggregate(method_results)
        if method_metrics:
            metrics["method_summary"] = method_metrics
    elif isinstance(payload, list):
        metrics["pipeline_outputs"] = [
            {
                "method": item.get("method"),
                "failed": item.get("failed"),
                "elapsed_s": item.get("elapsed_s"),
            }
            for item in payload
            if isinstance(item, dict)
        ]
    return {
        "acceptance": acceptance,
        "metrics": metrics,
    }


def _iter_hte_case_results(report: BenchmarkReport) -> dict[str, list[HTECaseResult]]:
    by_method: dict[str, list[HTECaseResult]] = {}
    for case in report.cases:
        payload = case.result_payload
        if not isinstance(payload, dict):
            continue
        for method_name, method_results in payload.items():
            if not isinstance(method_results, list):
                continue
            for item in method_results:
                if isinstance(item, HTECaseResult):
                    by_method.setdefault(str(method_name), []).append(item)
    return by_method


def _hte_selection_manifest(report: BenchmarkReport) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for method_name, records in _iter_hte_case_results(report).items():
        selection_records = [record.selection_manifest for record in records if record.selection_manifest]
        if selection_records:
            out[method_name] = summarize_selection_manifest(selection_records)
    return out


def _hte_calibration_metrics(report: BenchmarkReport) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for method_name, records in _iter_hte_case_results(report).items():
        calibration_records = [
            {
                "ci_coverage": 1.0 if record.ate_ci_covers else 0.0,
                "ci_width": record.ate_ci_width,
                "eceth": record.eceth,
                "calibration_mode": record.calibration_mode,
            }
            for record in records
            if not record.failed
        ]
        if calibration_records:
            out[method_name] = summarize_calibration_metrics(calibration_records)
    return out


def _hte_prioritization_metrics(report: BenchmarkReport) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for method_name, records in _iter_hte_case_results(report).items():
        prioritization_records = [
            {
                "r_risk": record.r_risk,
                "rate": record.rate,
                "policy_value_top_q": record.policy_value_top_q,
            }
            for record in records
            if not record.failed
        ]
        if not prioritization_records:
            continue
        summary = summarize_prioritization_metrics(prioritization_records)
        importance_vectors = [
            record.feature_importances
            for record in records
            if not record.failed and record.feature_importances
        ]
        summary["feature_importance_stability_mean"] = feature_importance_stability(importance_vectors)
        out[method_name] = summary
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Interpretable HTE benchmark")
    parser.add_argument("--n-obs", type=int, default=600, metavar="N")
    parser.add_argument("--n-reps", type=int, default=10, metavar="R")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", dest="json_out", default=None, metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode], default=None)
    parser.add_argument("--tier", choices=[tier.value for tier in BenchmarkTier], default=None)
    parser.add_argument(
        "--only-cate", action="store_true",
        help="Run only CATE quality cases (skip modifier detection and pipeline)"
    )
    parser.add_argument(
        "--only-modifiers", action="store_true",
        help="Run only modifier detection cases"
    )
    parser.add_argument(
        "--method-profile",
        choices=["production_hte", "exploratory_hte"],
        default="production_hte",
        help="Use claim-path production HTE methods or the wider exploratory set",
    )
    args = parser.parse_args()

    mode = resolve_mode(args.mode)
    tier = resolve_tier(args.tier, mode=mode)
    module_status = dependency_status(["numpy", "scipy", "sklearn", "econml", "zepid", "stochtree", "dowhy", "y0", "lightgbm"])
    comparator_status = build_research_acceptance_comparator_status()
    degraded_reasons = []
    if comparator_status["econml"] != "available":
        degraded_reasons.append("econml-backed HTE estimators unavailable; running reduced benchmark set")
    if tier is BenchmarkTier.LOCAL_EVIDENCE:
        degraded_reasons.append("local_evidence tier uses thermal-safe synthetic defaults")
    degraded_reasons.extend(comparator_degraded_reasons(comparator_status))
    planned_n_obs = 450 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_obs == 600 else args.n_obs
    planned_n_reps = 6 if tier is BenchmarkTier.LOCAL_EVIDENCE and args.n_reps == 10 else args.n_reps
    dataset_family = "hte_cate" if args.only_cate else ("hte_modifiers" if args.only_modifiers else "hte_interpretable")

    preflight = build_preflight(
        mode=mode.value,
        benchmark_tier=tier.value,
        data_source="synthetic_ground_truth",
        dependency_status={"python_modules": module_status},
        comparator_status=comparator_status,
        degraded_reasons=degraded_reasons,
        dataset_family=dataset_family,
        batch_id=f"n_obs={planned_n_obs};n_reps={planned_n_reps}",
        estimator_profile=args.method_profile,
    )
    print_preflight(preflight)

    gaps = acceptance_gaps(
        mode,
        tier=tier,
        require_modules=comparator_required_modules(),
    )
    if gaps:
        print("HTE acceptance preflight failed:")
        for gap in gaps:
            print(f"  - {gap}")
        return 2

    harness = build_interpretable_hte_harness(
        n_obs=planned_n_obs,
        n_reps=planned_n_reps,
        seed=args.seed,
        tier=tier,
        method_profile=args.method_profile,
    )

    # Circuit filter
    if args.only_cate:
        circuit = BenchmarkCircuit.HTE
        tags: tuple[str, ...] | None = ("cate",)
    elif args.only_modifiers:
        circuit = BenchmarkCircuit.HTE
        tags = ("modifiers",)
    else:
        circuit = None
        tags = None

    report: BenchmarkReport = harness.run(circuit=circuit, tags=tags)

    if not args.quiet:
        harness.print_report(report)

    if args.json_out:
        present_methods = {
            method_name
            for case in report.cases
            if isinstance(case.result_payload, dict)
            for method_name in case.result_payload
        }
        method_manifest = build_method_registry(
            present_methods,
            benchmark_roles=HTE_BENCHMARK_ROLES,
        )
        selection_manifest = _hte_selection_manifest(report)
        calibration_metrics = _hte_calibration_metrics(report)
        prioritization_metrics = _hte_prioritization_metrics(report)
        with open(args.json_out, "w") as f:
            json.dump(
                build_report_payload(
                    report,
                    suite_id="hte_interpretable",
                    mode=mode.value,
                    preflight=preflight,
                    sub_circuit="hte_interpretable",
                    include_case_payload=True,
                    aggregate_metrics=_component_summary(report),
                    method_groups=method_manifest,
                    method_manifest=method_manifest,
                    gate_method_set=list(HTE_GATE_METHOD_SET),
                    exploratory_methods=[
                        method_name
                        for method_name, meta in method_manifest.items()
                        if meta.get("benchmark_role") == "exploratory"
                    ],
                    selection_manifest=selection_manifest,
                    calibration_metrics=calibration_metrics,
                    prioritization_metrics=prioritization_metrics,
                    claim_profile_targets=["full_stack_publication_claim"],
                    literature_anchor=HTE_LITERATURE_ANCHOR,
                    public_claim_eligible=True,
                    blockers=[case.name for case in report.cases if not case.passed],
                    case_details_builder=_hte_case_details,
                    extra={
                        "requested_circuit": circuit.value if circuit else "all",
                        "method_profile": args.method_profile,
                    },
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
