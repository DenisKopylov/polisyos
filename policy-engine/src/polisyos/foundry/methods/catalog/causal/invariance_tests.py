"""invariance_tests — distribution invariance tests between domains.

Two methods for checking whether feature distributions are stable across
environments/domains, a prerequisite for causal transportability:

* **KSInvarianceTest**: Kolmogorov-Smirnov test applied per feature and domain
  pair, with Bonferroni or Benjamini-Hochberg multiple-comparison correction.
* **ICPInvarianceTest**: Invariant Causal Prediction style test — checks whether
  the conditional distribution Y | S is stable across domains via an F-test on
  regression coefficient heterogeneity.

Both return a unified dict with passed, n_rejected, rejected_variables, and
per-variable p-values.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import combinations
from typing import Any, ClassVar

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
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicBlockSpec,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.invariance import (
    RegimeShiftCandidateSetPlan,
    RegimeShiftComputationalFeasibility,
    RegimeShiftDataSignature,
    RegimeShiftEnvironmentRecord,
    RegimeShiftIdentificationCertificate,
    RegimeShiftIdentifiabilityWitness,
    RegimeShiftInformativeness,
    RegimeShiftInvarianceTesting,
    RegimeShiftMECContraction,
    RegimeShiftMECContractionEdgeUpdates,
    RegimeShiftMECContractionSummary,
    RegimeShiftProducedBy,
    RegimeShiftSetTestResult,
    RegimeShiftStabilityMetrics,
    RegimeShiftTrack7InteractionStats,
    RegimeShiftTrack7Revalidation,
    RegimeShiftTargetResult,
    RegimeShiftTypeAssessment,
    ShiftTypeAlphaSplit,
    ShiftTypeAssumptions,
    ShiftTypeCertificationLevel,
    ShiftTypeContextExogeneity,
    ShiftTypeGlobalShiftTest,
    ShiftTypeObservedSelectionSufficiency,
    ShiftTypeOverallLabel,
    ShiftTypeOverlapStatus,
    ShiftTypePipelineAction,
    ShiftTypeSelectionOnlyWitness,
    ShiftTypeStructuralOnlyWitness,
    ShiftTypeWitnessBundle,
    ShiftTypeWitnessStatus,
)
from polisyos.ir.analytics.literature import EnvironmentAuditReport

_EPS = 1e-12
_TRACK7_FAMILY_NAMES = frozenset(
    {
        AlgebraicConstraintFamily.TETRAD.value,
        AlgebraicConstraintFamily.OVERCOMPLETE.value,
        AlgebraicConstraintFamily.TREK_RANK.value,
    }
)


# ---------------------------------------------------------------------------
# Private statistical helpers
# ---------------------------------------------------------------------------


def _ks_statistic(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample KS statistic (pure numpy)."""
    a_sorted = np.sort(a)
    b_sorted = np.sort(b)
    n_a, n_b = len(a_sorted), len(b_sorted)
    combined = np.concatenate([a_sorted, b_sorted])
    combined.sort()
    cdf_a = np.searchsorted(a_sorted, combined, side="right") / n_a
    cdf_b = np.searchsorted(b_sorted, combined, side="right") / n_b
    return float(np.max(np.abs(cdf_a - cdf_b)))


def _ks_pvalue(d: float, n1: int, n2: int) -> float:
    """Approximate p-value for two-sample KS test (Kolmogorov distribution)."""
    n_eff = (n1 * n2) / (n1 + n2)
    z = d * math.sqrt(n_eff)
    # Kolmogorov distribution CDF via series truncation
    if z <= 0.0:
        return 1.0
    # P(D > d) ≈ 2 * Σ_{k=1}^{K} (-1)^{k+1} exp(-2k²z²)
    p = 0.0
    for k in range(1, 50):
        term = (-1.0) ** (k + 1) * math.exp(-2.0 * k * k * z * z)
        p += term
        if abs(term) < 1e-10:
            break
    return min(max(2.0 * p, 0.0), 1.0)


def _bh_correction(p_values: np.ndarray, alpha: float) -> np.ndarray:
    """Benjamini-Hochberg FDR correction. Returns adjusted p-values."""
    n = len(p_values)
    order = np.argsort(p_values)
    ranks = np.empty(n, dtype=int)
    ranks[order] = np.arange(1, n + 1)
    adjusted = np.minimum(1.0, p_values * n / ranks)
    # Enforce monotonicity: adj[i] <= adj[j] for i < j in original order
    sorted_adj = adjusted[order]
    for i in range(n - 2, -1, -1):
        sorted_adj[i] = min(sorted_adj[i], sorted_adj[i + 1])
    result = np.empty(n)
    result[order] = sorted_adj
    return result


def _bonferroni_correction(p_values: np.ndarray) -> np.ndarray:
    """Bonferroni correction: multiply by number of tests."""
    return np.minimum(p_values * len(p_values), 1.0)


def _holm_correction(p_values: np.ndarray) -> np.ndarray:
    """Holm step-down family-wise correction."""
    if len(p_values) == 0:
        return np.asarray([], dtype=float)
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        candidate = float(p_values[idx]) * float(len(p_values) - rank)
        running = max(running, candidate)
        adjusted[idx] = min(running, 1.0)
    return adjusted


def _classify_numeric_series(values: np.ndarray) -> str:
    """Heuristic numeric-series classifier for Stage 16.1 routing."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return "discrete"
    rounded = np.unique(np.round(arr, decimals=10))
    if len(rounded) >= max(8, min(32, len(arr) // 8)):
        return "continuous"
    return "discrete"


def _all_columns_continuous(data: np.ndarray, cols: list[int]) -> bool:
    return all(_classify_numeric_series(data[:, col]) == "continuous" for col in cols)


def _resolve_regime_model_family(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_cols: list[int],
    model_family: str | None,
) -> dict[str, Any]:
    requested = str(model_family or "auto").strip().lower()
    if requested not in {"auto", "linear", "nonlinear"}:
        raise ValueError(
            "build_regime_shift_identification_certificate: "
            "model_family must be one of auto, linear, nonlinear"
        )

    candidate_cols = sorted({idx for idx in range(data.shape[1]) if idx not in set(target_cols)})
    required_cols = sorted(set(target_cols) | set(candidate_cols))
    n_environments = len(np.unique(domain_labels))
    all_continuous = _all_columns_continuous(data, required_cols)
    nonlinear_eligible = n_environments >= 3 and all_continuous

    resolved = requested
    warnings: list[str] = []
    notes: list[str] = []
    if requested == "auto":
        resolved = "nonlinear" if nonlinear_eligible else "linear"
        if resolved == "linear":
            warnings.append("nonlinear_route_fallback_to_linear_ols")
            notes.append(
                "Auto Stage 16.1 routing fell back to linear OLS because at least one "
                "variable looked non-continuous or fewer than three environments were available."
            )
    elif requested == "nonlinear" and not nonlinear_eligible:
        resolved = "linear"
        warnings.append("requested_nonlinear_route_fallback_to_linear_ols")
        notes.append(
            "Requested nonlinear additive-noise ICP could not be certified because the "
            "data were not fully continuous or fewer than three environments were available."
        )

    return {
        "requested": requested,
        "resolved": resolved,
        "nonlinear_eligible": nonlinear_eligible,
        "all_continuous": all_continuous,
        "n_environments": n_environments,
        "notes": tuple(notes),
        "warnings": tuple(warnings),
    }


def _ols_fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """OLS: returns (coefficients, residual_variance)."""
    n = X.shape[0]
    Xaug = np.column_stack([np.ones(n), X])
    try:
        beta, residuals, _, _ = np.linalg.lstsq(Xaug, y, rcond=None)
    except np.linalg.LinAlgError:
        beta = np.zeros(Xaug.shape[1])
        residuals = np.array([float(np.var(y)) * n])
    if len(residuals) == 0:
        y_hat = Xaug @ beta
        res_var = float(np.mean((y - y_hat) ** 2))
    else:
        res_var = float(residuals[0]) / max(n - Xaug.shape[1], 1)
    return beta, max(res_var, _EPS)


def _f_test_heterogeneity(
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    feature_cols: list[int],
) -> tuple[float, float]:
    """F-test for heterogeneous regression coefficients across domains.

    Compares restricted model (pooled) vs unrestricted (per-domain intercepts).
    Returns (F_statistic, p_value).
    """
    y = data[:, target_col]
    X = data[:, feature_cols] if feature_cols else np.zeros((len(y), 0))
    unique_domains = np.unique(domain_labels)
    n_domains = len(unique_domains)
    n = len(y)

    if n_domains < 2:
        return 0.0, 1.0

    # Restricted model: pooled OLS
    n_feat = X.shape[1]
    if n_feat > 0:
        X_pooled = np.column_stack([np.ones(n), X])
    else:
        X_pooled = np.ones((n, 1))
    try:
        beta_r, _, _, _ = np.linalg.lstsq(X_pooled, y, rcond=None)
    except np.linalg.LinAlgError:
        return 0.0, 1.0
    res_r = y - X_pooled @ beta_r
    ss_r = float(np.sum(res_r ** 2))
    df_r = n - X_pooled.shape[1]

    # Unrestricted model: per-domain intercepts (domain fixed effects)
    domain_dummies = np.zeros((n, n_domains - 1))
    for k, d in enumerate(unique_domains[1:]):
        domain_dummies[:, k] = (domain_labels == d).astype(float)

    if n_feat > 0:
        X_unres = np.column_stack([np.ones(n), X, domain_dummies])
    else:
        X_unres = np.column_stack([np.ones(n), domain_dummies])

    try:
        beta_u, _, _, _ = np.linalg.lstsq(X_unres, y, rcond=None)
    except np.linalg.LinAlgError:
        return 0.0, 1.0
    res_u = y - X_unres @ beta_u
    ss_u = float(np.sum(res_u ** 2))
    df_u = n - X_unres.shape[1]

    df_diff = df_r - df_u
    if df_diff <= 0 or df_u <= 0:
        return 0.0, 1.0

    f_stat = ((ss_r - ss_u) / df_diff) / max((ss_u / df_u), _EPS)

    # F-distribution p-value via regularised incomplete beta approximation
    p_value = _f_pvalue(f_stat, df_diff, df_u)
    return float(f_stat), float(p_value)


def _standardize_features(
    X: np.ndarray,
    *,
    mean: np.ndarray | None = None,
    scale: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if X.ndim != 2:
        raise ValueError("feature matrix must be 2d")
    if X.shape[1] == 0:
        empty = np.zeros((X.shape[0], 0), dtype=float)
        return empty, np.zeros(0, dtype=float), np.ones(0, dtype=float)
    resolved_mean = np.asarray(mean if mean is not None else np.mean(X, axis=0), dtype=float)
    resolved_scale = np.asarray(scale if scale is not None else np.std(X, axis=0), dtype=float)
    resolved_scale = np.where(resolved_scale < _EPS, 1.0, resolved_scale)
    standardized = (X - resolved_mean) / resolved_scale
    return standardized, resolved_mean, resolved_scale


def _fit_polynomial_sieve_transformer(
    X: np.ndarray,
    *,
    degree: int = 3,
) -> dict[str, Any]:
    standardized, mean, scale = _standardize_features(X)
    interaction_pairs = [
        (left, right)
        for left in range(standardized.shape[1])
        for right in range(left + 1, standardized.shape[1])
    ]
    return {
        "degree": degree,
        "mean": mean,
        "scale": scale,
        "interaction_pairs": tuple(interaction_pairs),
    }


def _apply_polynomial_sieve_transformer(
    X: np.ndarray,
    transformer: Mapping[str, Any],
) -> np.ndarray:
    standardized, _, _ = _standardize_features(
        X,
        mean=np.asarray(transformer["mean"], dtype=float),
        scale=np.asarray(transformer["scale"], dtype=float),
    )
    if standardized.shape[1] == 0:
        return np.zeros((standardized.shape[0], 0), dtype=float)
    terms = [standardized]
    degree = int(transformer.get("degree", 3))
    if degree >= 2:
        squared = standardized**2
        terms.append(squared - np.mean(squared, axis=0, keepdims=True))
    if degree >= 3:
        cubed = standardized**3
        terms.append(cubed - np.mean(cubed, axis=0, keepdims=True))
    for left, right in transformer.get("interaction_pairs", ()):
        terms.append((standardized[:, left] * standardized[:, right])[:, None])
    return np.concatenate(terms, axis=1)


def _ridge_fit_predict(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    *,
    penalty: float = 1e-3,
) -> np.ndarray:
    X_train_aug = np.column_stack([np.ones(len(X_train)), X_train])
    X_test_aug = np.column_stack([np.ones(len(X_test)), X_test])
    regularizer = np.eye(X_train_aug.shape[1], dtype=float) * float(penalty)
    regularizer[0, 0] = 0.0
    gram = X_train_aug.T @ X_train_aug + regularizer
    rhs = X_train_aug.T @ y_train
    try:
        beta = np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(gram) @ rhs
    return X_test_aug @ beta


def _stratified_kfold_indices(
    *,
    domain_labels: np.ndarray,
    n_folds: int,
    seed: int = 0,
) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    fold_buckets: list[list[int]] = [[] for _ in range(max(2, int(n_folds)))]
    for env in np.unique(domain_labels):
        env_indices = np.where(domain_labels == env)[0]
        shuffled = env_indices[rng.permutation(len(env_indices))]
        for fold_idx, split in enumerate(np.array_split(shuffled, len(fold_buckets))):
            fold_buckets[fold_idx].extend(int(idx) for idx in split.tolist())
    return tuple(
        np.asarray(sorted(bucket), dtype=int)
        for bucket in fold_buckets
        if bucket
    )


def _cross_fitted_polynomial_sieve_residuals(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    feature_cols: list[int],
    degree: int = 3,
    penalty: float = 1e-3,
    seed: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    y = data[:, target_col]
    X = data[:, feature_cols] if feature_cols else np.zeros((len(y), 0), dtype=float)
    min_env_size = min(
        int(np.sum(domain_labels == env))
        for env in np.unique(domain_labels)
    )
    n_folds = 3 if min_env_size >= 3 else 2
    folds = _stratified_kfold_indices(domain_labels=domain_labels, n_folds=n_folds, seed=seed)
    residuals = np.zeros(len(y), dtype=float)

    for fold_idx, test_idx in enumerate(folds):
        train_mask = np.ones(len(y), dtype=bool)
        train_mask[test_idx] = False
        train_idx = np.where(train_mask)[0]
        transformer = _fit_polynomial_sieve_transformer(X[train_idx], degree=degree)
        design_train = _apply_polynomial_sieve_transformer(X[train_idx], transformer)
        design_test = _apply_polynomial_sieve_transformer(X[test_idx], transformer)
        predictions = _ridge_fit_predict(
            design_train,
            y[train_idx],
            design_test,
            penalty=penalty,
        )
        residuals[test_idx] = y[test_idx] - predictions

    return residuals, {
        "cross_fit_folds": len(folds),
        "degree": degree,
        "ridge_penalty": penalty,
    }


def _deterministic_subsample(values: np.ndarray, *, max_size: int = 96) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if len(arr) <= max_size:
        return arr
    order = np.argsort(arr)
    positions = np.linspace(0, len(arr) - 1, max_size).round().astype(int)
    return arr[order[positions]]


def _mean_pairwise_absolute_distance(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) == 0 or len(y) == 0:
        return 0.0
    return float(np.mean(np.abs(x[:, None] - y[None, :])))


def _energy_distance_statistic(x: np.ndarray, y: np.ndarray) -> float:
    left = _deterministic_subsample(np.asarray(x, dtype=float))
    right = _deterministic_subsample(np.asarray(y, dtype=float))
    if len(left) == 0 or len(right) == 0:
        return 0.0
    cross = _mean_pairwise_absolute_distance(left, right)
    within_left = _mean_pairwise_absolute_distance(left, left)
    within_right = _mean_pairwise_absolute_distance(right, right)
    return max(0.0, 2.0 * cross - within_left - within_right)


def _energy_distance_p_value(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_permutations: int = 48,
) -> tuple[float, float]:
    left = _deterministic_subsample(np.asarray(x, dtype=float))
    right = _deterministic_subsample(np.asarray(y, dtype=float))
    observed = _energy_distance_statistic(left, right)
    if observed <= _EPS:
        return 1.0, 0.0
    pooled = np.concatenate([left, right])
    rng = np.random.default_rng(len(left) * 101 + len(right) * 17)
    exceedances = 1
    for _ in range(n_permutations):
        permuted = pooled[rng.permutation(len(pooled))]
        alt_left = permuted[: len(left)]
        alt_right = permuted[len(left) :]
        if _energy_distance_statistic(alt_left, alt_right) >= observed - 1e-12:
            exceedances += 1
    return exceedances / float(n_permutations + 1), observed


def _variance_ratio_guard_p_value(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    left = np.asarray(x, dtype=float)
    right = np.asarray(y, dtype=float)
    if len(left) < 2 or len(right) < 2:
        return 1.0, 1.0
    var_left = float(np.var(left, ddof=1))
    var_right = float(np.var(right, ddof=1))
    ratio = max(var_left, var_right) / max(min(var_left, var_right), _EPS)
    n_eff = max((len(left) * len(right)) / max(len(left) + len(right), 1), 1.0)
    p_value = math.exp(-0.5 * math.sqrt(n_eff) * abs(math.log(max(ratio, _EPS))))
    return min(max(float(p_value), 0.0), 1.0), float(ratio)


def _nonlinear_candidate_set_family_test(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    feature_cols: list[int],
) -> tuple[float, dict[str, Any]]:
    residuals, fit_diag = _cross_fitted_polynomial_sieve_residuals(
        data=data,
        domain_labels=domain_labels,
        target_col=target_col,
        feature_cols=feature_cols,
    )
    unique_domains = np.unique(domain_labels)
    pairwise_pvalues: dict[str, float] = {}
    energy_pvalues: dict[str, float] = {}
    variance_pvalues: dict[str, float] = {}
    max_energy = 0.0
    max_variance_ratio = 1.0

    for left_idx in range(len(unique_domains)):
        for right_idx in range(left_idx + 1, len(unique_domains)):
            left = unique_domains[left_idx]
            right = unique_domains[right_idx]
            left_residuals = residuals[domain_labels == left]
            right_residuals = residuals[domain_labels == right]
            energy_p, energy_stat = _energy_distance_p_value(left_residuals, right_residuals)
            variance_p, variance_ratio = _variance_ratio_guard_p_value(
                left_residuals,
                right_residuals,
            )
            pair_key = f"{left}|{right}"
            pairwise_pvalues[pair_key] = min(energy_p, variance_p)
            energy_pvalues[pair_key] = energy_p
            variance_pvalues[pair_key] = variance_p
            max_energy = max(max_energy, energy_stat)
            max_variance_ratio = max(max_variance_ratio, variance_ratio)

    family_p_value = _combine_family_p_value(list(pairwise_pvalues.values()))
    return (
        1.0 if family_p_value is None else float(family_p_value),
        {
            "test": "cross_fitted_residual_energy_distance_variance_guard",
            "pairwise_p_values": pairwise_pvalues,
            "energy_distance_p_values": energy_pvalues,
            "variance_guard_p_values": variance_pvalues,
            "max_energy_distance": max_energy,
            "max_variance_ratio": max_variance_ratio,
            **fit_diag,
        },
    )


def _evaluate_parent_set_holdout_p_value(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    feature_cols: list[int],
    model_family: str,
) -> float:
    if model_family == "nonlinear":
        p_value, _ = _nonlinear_candidate_set_family_test(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            feature_cols=feature_cols,
        )
        return float(p_value)
    _, p_value = _f_test_heterogeneity(
        data=data,
        domain_labels=domain_labels,
        target_col=target_col,
        feature_cols=feature_cols,
    )
    return float(p_value)


def _f_pvalue(f: float, df1: int, df2: int) -> float:
    """Approximate upper-tail p-value for F(df1, df2) via beta function."""
    if f <= 0.0:
        return 1.0
    # Transform to Beta: x = df2 / (df2 + df1 * F)
    x = df2 / (df2 + df1 * f)
    # regularised incomplete beta via continued fraction (Numerical Recipes)
    p = _regularised_beta(x, df2 / 2.0, df1 / 2.0)
    return min(max(float(p), 0.0), 1.0)


def _regularised_beta(x: float, a: float, b: float, max_iter: int = 200) -> float:
    """Regularised incomplete beta function I_x(a,b) via continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    threshold = (a + 1.0) / (a + b + 2.0)
    if x < threshold:
        value = bt * _beta_continued_fraction(a, b, x, max_iter=max_iter) / a
    else:
        value = 1.0 - bt * _beta_continued_fraction(b, a, 1.0 - x, max_iter=max_iter) / b
    if not math.isfinite(value):
        return 1.0
    return min(max(float(value), 0.0), 1.0)


def _beta_continued_fraction(a: float, b: float, x: float, max_iter: int = 200) -> float:
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _EPS:
        d = _EPS
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _EPS:
            d = _EPS
        c = 1.0 + aa / c
        if abs(c) < _EPS:
            c = _EPS
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _EPS:
            d = _EPS
        c = 1.0 + aa / c
        if abs(c) < _EPS:
            c = _EPS
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-10:
            break
    return float(h)


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.diagnostics.invariance",
    version="1.0.0",
    tags={"causal", "diagnostics", "invariance", "ks-test", "multi-domain", "cross-section"},
)
class KSInvarianceTest:
    """Kolmogorov-Smirnov distribution invariance test across domains.

    For each feature and each pair of domains, computes the KS statistic and
    p-value.  Applies Bonferroni or Benjamini-Hochberg correction for the
    n_features × n_domain_pairs simultaneous tests.

    H₀: feature j has the same distribution in all domains.
    Rejection indicates a distribution shift that may violate transportability.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ks_invariance",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "data",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec(
                    "domain_labels",
                    SlotType.VECTOR,
                    Unit("domain", "label"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(
                name="correction",
                default="bonferroni",
                description="Multiple comparison correction: 'bonferroni' or 'bh'.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "KS distribution invariance test: checks whether each feature has the same "
            "distribution in all domains. Multiple-comparison corrected."
        ),
        tags=frozenset(
            {"causal", "diagnostics", "invariance", "ks-test", "multi-domain", "transportability"}
        ),
        citations=(
            "Kolmogorov, A.N. (1933). Sulla determinazione empirica di una legge di distribuzione.",
            "Benjamini, Y., Hochberg, Y. (1995). Controlling the false discovery rate.",
        ),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Check covariate distribution stability before cross-domain estimation or "
            "transportability analysis."
        ),
        when_not_to_use="Does not test conditional distributions — use ICPInvarianceTest for that.",
        typical_min_obs=20,
        output_interpretation=(
            "passed=True: no feature showed significant distribution shift. "
            "rejected_variables: list of feature indices with significant shifts."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = np.asarray(state["data"], dtype=float)
        domain_labels = np.asarray(state["domain_labels"])

        if data.ndim == 1:
            data = data[:, None]

        n_obs, n_features = data.shape
        if len(domain_labels) != n_obs:
            raise ValueError("KSInvarianceTest: domain_labels length must equal n_obs")

        alpha: float = float(params.get("alpha", 0.05))
        correction: str = str(params.get("correction", "bonferroni"))

        unique_domains = np.unique(domain_labels)
        n_domains = len(unique_domains)

        if n_domains < 2:
            return {
                "result": {
                    "passed": True,
                    "n_rejected": 0,
                    "rejected_variables": [],
                    "p_values_matrix": {},
                    "correction_method": correction,
                    "metadata": {"n_domains": n_domains, "note": "single domain, no test"},
                }
            }

        domain_pairs = [
            (unique_domains[i], unique_domains[j])
            for i in range(n_domains)
            for j in range(i + 1, n_domains)
        ]
        n_pairs = len(domain_pairs)
        n_tests = n_features * n_pairs

        raw_pvalues = np.ones(n_tests)
        ks_stats = np.zeros(n_tests)
        idx = 0
        for feat in range(n_features):
            for d1, d2 in domain_pairs:
                a = data[domain_labels == d1, feat]
                b = data[domain_labels == d2, feat]
                if len(a) < 2 or len(b) < 2:
                    idx += 1
                    continue
                ks = _ks_statistic(a, b)
                pval = _ks_pvalue(ks, len(a), len(b))
                raw_pvalues[idx] = pval
                ks_stats[idx] = ks
                idx += 1

        if correction == "bh":
            adj_pvalues = _bh_correction(raw_pvalues, alpha)
        else:
            adj_pvalues = _bonferroni_correction(raw_pvalues)

        rejected = adj_pvalues < alpha
        n_rejected = int(np.sum(rejected))

        rejected_variables: list[int] = []
        p_values_matrix: dict[str, float] = {}
        for feat in range(n_features):
            for k, (d1, d2) in enumerate(domain_pairs):
                flat_idx = feat * n_pairs + k
                key = f"feature_{feat}_domain_{d1}_vs_{d2}"
                p_values_matrix[key] = float(adj_pvalues[flat_idx])
                if rejected[flat_idx] and feat not in rejected_variables:
                    rejected_variables.append(feat)

        passed = n_rejected == 0

        return {
            "result": {
                "passed": passed,
                "n_rejected": n_rejected,
                "rejected_variables": sorted(rejected_variables),
                "p_values_matrix": p_values_matrix,
                "correction_method": correction,
                "metadata": {
                    "n_obs": n_obs,
                    "n_features": n_features,
                    "n_domains": n_domains,
                    "n_tests": n_tests,
                    "alpha": alpha,
                },
            }
        }


@foundry_method(
    namespace="causal.diagnostics.invariance",
    version="1.0.0",
    tags={"causal", "diagnostics", "invariance", "icp", "multi-domain", "cross-section"},
)
class ICPInvarianceTest:
    """Invariant Causal Prediction (ICP)-style invariance test.

    Tests whether the conditional distribution Y | features is stable across
    domains via an F-test on regression coefficient heterogeneity.

    For each candidate feature subset (simplified: single features and empty
    set), fits OLS Y ~ S in each domain and tests if coefficients are
    homogeneous across domains.  The invariant set is those features whose
    conditional distribution of Y is stable.

    H₀: β_d is the same for all domains d.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="icp_invariance",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "data",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec(
                    "domain_labels",
                    SlotType.VECTOR,
                    Unit("domain", "label"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "target_col",
                    SlotType.SCALAR,
                    Unit("index", "column"),
                ),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(
                name="correction",
                default="bh",
                description="Multiple comparison correction: 'bonferroni' or 'bh'.",
            ),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "ICP-style invariance test: checks whether the conditional distribution "
            "Y | features is stable across domains via F-test for coefficient heterogeneity."
        ),
        tags=frozenset(
            {"causal", "diagnostics", "invariance", "icp", "multi-domain", "transportability"}
        ),
        citations=(
            "Peters, J., Bühlmann, P., Meinshausen, N. (2016). Causal inference by using "
            "invariant prediction: identification and confidence intervals.",
        ),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Identify which features have a stable conditional effect on Y across environments. "
            "Use as a check before causal discovery or transfer."
        ),
        when_not_to_use=(
            "Full ICP requires exhaustive subset search — this implementation tests individual "
            "features for tractability. Not suitable as a replacement for full ICP."
        ),
        typical_min_obs=30,
        output_interpretation=(
            "invariant_features: feature indices where Y | feature is stable across domains. "
            "passed=True: no feature showed significant heterogeneity."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = np.asarray(state["data"], dtype=float)
        domain_labels = np.asarray(state["domain_labels"])
        target_col = int(state["target_col"])

        if data.ndim == 1:
            data = data[:, None]

        n_obs, n_features = data.shape
        if len(domain_labels) != n_obs:
            raise ValueError("ICPInvarianceTest: domain_labels length must equal n_obs")
        if not (0 <= target_col < n_features):
            raise ValueError(
                f"ICPInvarianceTest: target_col={target_col} out of range [0, {n_features})"
            )

        alpha: float = float(params.get("alpha", 0.05))
        correction: str = str(params.get("correction", "bh"))

        feature_cols = [c for c in range(n_features) if c != target_col]
        n_tests = len(feature_cols)

        if n_tests == 0:
            return {
                "result": {
                    "passed": True,
                    "n_rejected": 0,
                    "invariant_features": [],
                    "variant_features": [],
                    "p_values": {},
                    "correction_method": correction,
                    "metadata": {"n_obs": n_obs, "note": "no features to test"},
                }
            }

        raw_pvalues = np.ones(n_tests)
        f_stats = np.zeros(n_tests)
        for i, feat in enumerate(feature_cols):
            f_stat, p_val = _f_test_heterogeneity(
                data=data,
                domain_labels=domain_labels,
                target_col=target_col,
                feature_cols=[feat],
            )
            raw_pvalues[i] = p_val
            f_stats[i] = f_stat

        if correction == "bh":
            adj_pvalues = _bh_correction(raw_pvalues, alpha)
        else:
            adj_pvalues = _bonferroni_correction(raw_pvalues)

        rejected = adj_pvalues < alpha
        n_rejected = int(np.sum(rejected))

        invariant_features = [feature_cols[i] for i in range(n_tests) if not rejected[i]]
        variant_features = [feature_cols[i] for i in range(n_tests) if rejected[i]]
        p_values = {f"feature_{feature_cols[i]}": float(adj_pvalues[i]) for i in range(n_tests)}

        passed = n_rejected == 0

        return {
            "result": {
                "passed": passed,
                "n_rejected": n_rejected,
                "invariant_features": invariant_features,
                "variant_features": variant_features,
                "p_values": p_values,
                "correction_method": correction,
                "metadata": {
                    "n_obs": n_obs,
                    "n_features": n_features,
                    "target_col": target_col,
                    "n_tests": n_tests,
                    "alpha": alpha,
                    "f_statistics": {
                        f"feature_{feature_cols[i]}": float(f_stats[i])
                        for i in range(n_tests)
                    },
                },
            }
        }


def _as_2d_float_array(data: Any, *, caller: str) -> np.ndarray:
    data_array = np.asarray(data, dtype=float)
    if data_array.ndim == 1:
        data_array = data_array[:, None]
    if data_array.ndim != 2:
        raise ValueError(f"{caller}: data must be 2D")
    if not np.isfinite(data_array).all():
        raise ValueError(f"{caller}: data contains non-finite values")
    return data_array


def _normalize_variable_names(
    *,
    n_features: int,
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> list[str]:
    raw_names = state.get("variable_names", params.get("variable_names"))
    if raw_names is None:
        return [f"X{i}" for i in range(n_features)]
    names = [str(item).strip() for item in raw_names]
    if len(names) != n_features or any(not item for item in names):
        raise ValueError(
            "InvariantDiscoveryFromRegimes: variable_names must match data width"
        )
    if len(set(names)) != len(names):
        raise ValueError("InvariantDiscoveryFromRegimes: variable_names must be unique")
    return names


def _normalize_target_cols(
    *,
    variable_names: list[str],
    params: Mapping[str, Any],
    state: Mapping[str, Any],
) -> list[int]:
    raw_targets = params.get("target_cols", params.get("targets", state.get("target_cols")))
    if raw_targets is None:
        return list(range(len(variable_names)))
    if isinstance(raw_targets, (str, int)):
        raw_targets = [raw_targets]
    target_cols: list[int] = []
    name_to_idx = {name: idx for idx, name in enumerate(variable_names)}
    for raw_target in raw_targets:
        if isinstance(raw_target, str) and not raw_target.isdigit():
            if raw_target not in name_to_idx:
                raise ValueError(
                    f"InvariantDiscoveryFromRegimes: unknown target {raw_target!r}"
                )
            target_cols.append(name_to_idx[raw_target])
        else:
            target_col = int(raw_target)
            if not (0 <= target_col < len(variable_names)):
                raise ValueError(
                    f"InvariantDiscoveryFromRegimes: target_col={target_col} out of range"
                )
            target_cols.append(target_col)
    if len(set(target_cols)) != len(target_cols):
        raise ValueError("InvariantDiscoveryFromRegimes: duplicate target columns")
    return target_cols


def _normalize_super_structure(
    *,
    raw_super_structure: Any,
) -> CausalGraphModel | None:
    if raw_super_structure is None:
        return None
    if isinstance(raw_super_structure, CausalGraphModel):
        return raw_super_structure
    return CausalGraphModel.model_validate(raw_super_structure)


def _normalize_algebraic_blocks(raw_blocks: Any) -> list[AlgebraicBlockSpec]:
    if raw_blocks in (None, ""):
        return []
    if isinstance(raw_blocks, AlgebraicBlockSpec):
        return [raw_blocks]
    return [AlgebraicBlockSpec.model_validate(item) for item in raw_blocks]


def _normalize_algebraic_reports(raw_reports: Any) -> tuple[AlgebraicConstraintReport, ...]:
    if raw_reports in (None, ""):
        return ()
    if isinstance(raw_reports, (list, tuple)):
        items = raw_reports
    else:
        items = [raw_reports]
    return tuple(
        item
        if isinstance(item, AlgebraicConstraintReport)
        else AlgebraicConstraintReport.model_validate(item)
        for item in items
    )


def _append_fallback_reason(existing: str | None, new_reason: str | None) -> str | None:
    if not new_reason:
        return existing
    if not existing:
        return new_reason
    reasons = [reason for reason in existing.split(";") if reason]
    if new_reason in reasons:
        return existing
    reasons.append(new_reason)
    return ";".join(reasons)


def _extract_track7_blocker_families_from_reports(
    reports: tuple[AlgebraicConstraintReport, ...],
) -> tuple[str, ...]:
    blocker_families: set[str] = set()
    for report in reports:
        for family_name, blocked in report.blocker_conditions_met_by_family.items():
            if family_name in _TRACK7_FAMILY_NAMES and bool(blocked):
                blocker_families.add(str(family_name))
        for violation in report.violated_constraints_preview:
            family_name = (
                violation.family.value
                if hasattr(violation.family, "value")
                else str(violation.family)
            )
            if family_name in _TRACK7_FAMILY_NAMES and violation.severity == "blocker":
                blocker_families.add(family_name)
    return tuple(sorted(blocker_families))


def _graph_edge_allows_parent(
    *,
    graph: CausalGraphModel,
    parent: str,
    target: str,
) -> bool:
    for edge in graph.edges:
        if {edge.src, edge.dst} != {parent, target}:
            continue
        if edge.src == parent:
            return edge.mark_src is not EdgeMark.ARROW
        return edge.mark_dst is not EdgeMark.ARROW
    return False


def _candidate_parent_pool_for_target(
    *,
    variable_names: list[str],
    target_col: int,
    super_structure: CausalGraphModel | None,
) -> list[int]:
    if super_structure is None:
        return [idx for idx in range(len(variable_names)) if idx != target_col]
    target = variable_names[target_col]
    name_to_idx = {name: idx for idx, name in enumerate(variable_names)}
    candidates: list[int] = []
    for name, idx in name_to_idx.items():
        if idx == target_col:
            continue
        if _graph_edge_allows_parent(graph=super_structure, parent=name, target=target):
            candidates.append(idx)
    if candidates:
        return sorted(candidates)
    return [idx for idx in range(len(variable_names)) if idx != target_col]


def _measurement_like_block(block: AlgebraicBlockSpec) -> bool:
    return block.family in {
        AlgebraicConstraintFamily.TETRAD,
        AlgebraicConstraintFamily.OVERCOMPLETE,
        AlgebraicConstraintFamily.TREK_RANK,
    }


def _track7_prune_candidate_pool(
    *,
    target: str,
    candidate_cols: list[int],
    variable_names: list[str],
    algebraic_blocks: list[AlgebraicBlockSpec],
) -> tuple[list[int], tuple[str, ...], tuple[tuple[str, ...], ...], tuple[tuple[str, str], ...]]:
    if not algebraic_blocks:
        return candidate_cols, (), (), ()

    suppressed_names: set[str] = set()
    mutually_exclusive_groups: set[tuple[str, ...]] = set()
    hard_forbidden_edges: set[tuple[str, str]] = set()
    candidate_name_set = {variable_names[idx] for idx in candidate_cols}

    for block in algebraic_blocks:
        if not _measurement_like_block(block):
            continue
        block_variables = tuple(name for name in block.variables if name in set(variable_names))
        if len(block_variables) < 2:
            continue
        for src in block_variables:
            for dst in block_variables:
                if src != dst:
                    hard_forbidden_edges.add((src, dst))
        block_candidate_names = tuple(
            sorted(name for name in block_variables if name in candidate_name_set)
        )
        if target in block_variables:
            suppressed_names.update(name for name in block_variables if name != target)
            continue
        if len(block_candidate_names) >= 2:
            mutually_exclusive_groups.add(block_candidate_names)

    pruned_cols = [
        idx for idx in candidate_cols if variable_names[idx] not in suppressed_names
    ]
    return (
        pruned_cols,
        tuple(sorted(suppressed_names)),
        tuple(sorted(mutually_exclusive_groups)),
        tuple(sorted(hard_forbidden_edges)),
    )


def _rank_candidate_parent_cols(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    candidate_cols: list[int],
) -> list[int]:
    y = data[:, target_col]
    if np.std(y) <= _EPS:
        return list(candidate_cols)
    scored: list[tuple[float, float, int]] = []
    for col in candidate_cols:
        _, p_value = _f_test_heterogeneity(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            feature_cols=[col],
        )
        x = data[:, col]
        corr = 0.0 if np.std(x) <= _EPS else abs(float(np.corrcoef(x, y)[0, 1]))
        scored.append((float(p_value), corr, col))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[2] for item in scored]


def _screen_candidate_parent_cols(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    candidate_cols: list[int],
    screening: str | None,
    max_candidate_parents: int | None,
) -> tuple[list[int], str | None]:
    if max_candidate_parents is None or max_candidate_parents <= 0:
        return list(candidate_cols), screening

    resolved_screening = screening or "auto"
    if len(candidate_cols) <= max_candidate_parents and resolved_screening == "auto":
        return list(candidate_cols), "auto"
    if resolved_screening in {"none", "off"}:
        return list(candidate_cols), resolved_screening

    ranked = _rank_candidate_parent_cols(
        data=data,
        domain_labels=domain_labels,
        target_col=target_col,
        candidate_cols=candidate_cols,
    )
    return sorted(ranked[:max_candidate_parents]), resolved_screening


def _candidate_sets_for_target(
    *,
    candidate_parent_cols: list[int],
    max_set_size: int,
    mutually_exclusive_groups: tuple[tuple[str, ...], ...] = (),
    variable_names: list[str],
) -> list[tuple[int, ...]]:
    bounded_size = min(max_set_size, len(candidate_parent_cols))
    group_lookup: dict[int, int] = {}
    for group_idx, group in enumerate(mutually_exclusive_groups):
        for variable in group:
            variable_idx = variable_names.index(variable)
            group_lookup[variable_idx] = group_idx

    candidate_sets: list[tuple[int, ...]] = [()]
    for size in range(1, bounded_size + 1):
        for combo in combinations(candidate_parent_cols, size):
            group_ids = {group_lookup.get(col, -col - 1) for col in combo}
            if len(group_ids) != len(combo):
                continue
            candidate_sets.append(tuple(combo))
    return candidate_sets


def _correct_p_values(raw_pvalues: np.ndarray, correction: str, alpha: float) -> np.ndarray:
    if correction == "bh":
        return _bh_correction(raw_pvalues, alpha)
    if correction == "holm":
        return _holm_correction(raw_pvalues)
    if correction == "bonferroni":
        return _bonferroni_correction(raw_pvalues)
    return raw_pvalues


def _evaluate_candidate_sets(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    candidate_sets: list[tuple[int, ...]],
    variable_names: list[str],
    alpha: float,
    correction: str,
    model_family: str,
) -> tuple[tuple[RegimeShiftSetTestResult, ...], tuple[RegimeShiftSetTestResult, ...]]:
    unique_domains = np.unique(domain_labels)
    if len(unique_domains) < 2:
        raise ValueError(
            "InvariantDiscoveryFromRegimes: at least two environments are required"
        )
    raw_pvalues = np.ones(len(candidate_sets), dtype=float)
    diagnostics: list[dict[str, Any]] = []
    for idx, candidate_set in enumerate(candidate_sets):
        if model_family == "nonlinear":
            p_value, diagnostic = _nonlinear_candidate_set_family_test(
                data=data,
                domain_labels=domain_labels,
                target_col=target_col,
                feature_cols=list(candidate_set),
            )
        else:
            f_stat, p_value = _f_test_heterogeneity(
                data=data,
                domain_labels=domain_labels,
                target_col=target_col,
                feature_cols=list(candidate_set),
            )
            diagnostic = {
                "test": "pooled_vs_environment_fixed_effect_f_test",
                "f_statistic": f_stat,
                "raw_p_value": p_value,
            }
        raw_pvalues[idx] = p_value
        diagnostics.append(diagnostic)
    adjusted_pvalues = _correct_p_values(raw_pvalues, correction, alpha)

    accepted: list[RegimeShiftSetTestResult] = []
    rejected: list[RegimeShiftSetTestResult] = []
    for idx, candidate_set in enumerate(candidate_sets):
        result = RegimeShiftSetTestResult(
            S=tuple(variable_names[col] for col in candidate_set),
            p_value=float(adjusted_pvalues[idx]),
            diagnostics=diagnostics[idx],
        )
        if adjusted_pvalues[idx] >= alpha:
            accepted.append(result)
        else:
            rejected.append(result)
    return tuple(accepted), tuple(rejected)


def _accepted_intersection(accepted_sets: tuple[RegimeShiftSetTestResult, ...]) -> tuple[str, ...]:
    if not accepted_sets:
        return ()
    intersection = set(accepted_sets[0].S)
    for result in accepted_sets[1:]:
        intersection &= set(result.S)
    return tuple(sorted(intersection))


def _minimal_accepted_set(
    accepted_sets: tuple[RegimeShiftSetTestResult, ...],
) -> tuple[str, ...]:
    if not accepted_sets:
        return ()
    best = min(
        accepted_sets,
        key=lambda result: (
            len(result.S),
            -(result.p_value if result.p_value is not None else 0.0),
            tuple(result.S),
        ),
    )
    return tuple(best.S)


def _stability_ratio(
    *,
    accepted_sets: tuple[RegimeShiftSetTestResult, ...],
    candidate_variables: tuple[str, ...],
) -> dict[str, float]:
    if not accepted_sets:
        return dict.fromkeys(candidate_variables, 0.0)
    denominator = float(len(accepted_sets))
    return {
        variable: sum(1 for result in accepted_sets if variable in result.S) / denominator
        for variable in candidate_variables
    }


def _leave_one_out_parent_changes(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    target_col: int,
    candidate_sets: list[tuple[int, ...]],
    variable_names: list[str],
    baseline_parents: tuple[str, ...],
    baseline_minimal_set: tuple[str, ...],
    alpha: float,
    correction: str,
    model_family: str,
    environment_patterns: Mapping[str, tuple[Any, ...]],
) -> tuple[dict[str, bool], dict[str, bool], tuple[str, ...]]:
    parent_changes: dict[str, bool] = {}
    minimal_set_changes: dict[str, bool] = {}
    redundant_envs: list[str] = []
    baseline = set(baseline_parents)
    baseline_minimal = tuple(baseline_minimal_set)
    pattern_counts: dict[tuple[Any, ...], int] = {}
    for pattern in environment_patterns.values():
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    for env in np.unique(domain_labels):
        env_id = str(env)
        mask = domain_labels != env
        if len(np.unique(domain_labels[mask])) < 2:
            parent_changes[env_id] = True
            minimal_set_changes[env_id] = True
            continue
        accepted, _ = _evaluate_candidate_sets(
            data=data[mask],
            domain_labels=domain_labels[mask],
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            alpha=alpha,
            correction=correction,
            model_family=model_family,
        )
        changed = set(_accepted_intersection(accepted)) != baseline
        minimal_changed = _minimal_accepted_set(accepted) != baseline_minimal
        parent_changes[env_id] = changed
        minimal_set_changes[env_id] = minimal_changed
        pattern = environment_patterns.get(env_id, ())
        adds_new_pattern = pattern_counts.get(pattern, 0) <= 1
        if not changed and not minimal_changed and not adds_new_pattern:
            redundant_envs.append(env_id)
    return parent_changes, minimal_set_changes, tuple(redundant_envs)


def _build_environment_shift_summaries(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    variable_names: list[str],
    target_cols: list[int],
) -> dict[str, dict[str, Any]]:
    target_idx_set = set(target_cols)
    summaries: dict[str, dict[str, Any]] = {}
    for env in np.unique(domain_labels):
        env_id = str(env)
        env_mask = domain_labels == env
        rest_mask = domain_labels != env
        env_mean = np.mean(data[env_mask], axis=0)
        if np.any(rest_mask):
            rest_mean = np.mean(data[rest_mask], axis=0)
            rest_std = np.std(data[rest_mask], axis=0)
        else:
            rest_mean = np.mean(data, axis=0)
            rest_std = np.std(data, axis=0)
        rest_std = np.where(rest_std < _EPS, 1.0, rest_std)
        shift_scores = np.abs(env_mean - rest_mean) / rest_std
        detected_covariate_shifts = tuple(
            variable_names[idx]
            for idx in range(len(variable_names))
            if idx not in target_idx_set and shift_scores[idx] >= 0.5
        )
        detected_target_shift_flags = {
            variable_names[idx]: bool(shift_scores[idx] >= 0.5)
            for idx in target_cols
        }
        summaries[env_id] = {
            "detected_covariate_shifts": detected_covariate_shifts,
            "detected_target_shift_flags": detected_target_shift_flags,
            "pattern": (
                detected_covariate_shifts,
                tuple(
                    sorted(
                        target
                        for target, shifted in detected_target_shift_flags.items()
                        if shifted
                    )
                ),
            ),
        }
    return summaries


def _build_identifiability_witness(
    *,
    env_ids: list[str],
    target_results: list[RegimeShiftTargetResult],
    resolved_model_family: str,
    shift_type_assessment: RegimeShiftTypeAssessment,
) -> RegimeShiftIdentifiabilityWitness:
    informative_envs: set[str] = set()
    redundant_env_sets: list[set[str]] = []
    for target in target_results:
        redundant_env_sets.append(set(target.informativeness.redundant_envs))
        for env_id, changed in target.informativeness.leave_one_out_parent_changes.items():
            if changed or target.informativeness.leave_one_out_minimal_set_changes.get(env_id, False):
                informative_envs.add(env_id)

    redundant_envs = (
        set.intersection(*redundant_env_sets)
        if redundant_env_sets
        else set()
    )
    if resolved_model_family == "nonlinear":
        min_envs = 3
        min_informative = 2
        theorem_slice = "phase1_nonlinear_additive_noise_icp_v1"
        assumptions = (
            "continuous target and candidate variables",
            "additive-noise nonlinear mechanisms approximable by degree-3 polynomial sieve",
            "cross-fitted residuals are exchangeable across informative environments for accepted parent sets",
            "at least two informative non-redundant environments are required for phase-closing promotion",
        )
        diversity_requirements = (
            "at least three environments",
            "at least two informative environments",
            "informative environments must survive shift-type screening for ICP contraction",
        )
    else:
        min_envs = 2
        min_informative = 1
        theorem_slice = "phase1_linear_icp_fallback_v1"
        assumptions = (
            "linear conditional mean specification",
            "environment fixed-effect F-test is used as a conservative fallback only",
            "this fallback does not satisfy the archival nonlinear sufficient result on its own",
        )
        diversity_requirements = (
            "at least two environments",
            "used only as backward-compatible fallback when nonlinear routing is unavailable",
        )

    diversity_satisfied = (
        shift_type_assessment.pipeline_action.allow_icp_graph_contraction
        and len(env_ids) >= min_envs
        and len(informative_envs) >= min_informative
        and (
            resolved_model_family != "nonlinear"
            or len(informative_envs - redundant_envs) >= min_informative
        )
    )
    if resolved_model_family == "nonlinear" and diversity_satisfied:
        identification_scope = "phase_closing_nonlinear_additive_noise_icp"
    elif resolved_model_family == "nonlinear":
        identification_scope = "nonlinear_slice_present_but_not_phase_closing"
    else:
        identification_scope = "linear_fallback_only_not_phase_closing"

    return RegimeShiftIdentifiabilityWitness(
        theorem_slice=theorem_slice,
        model_class=(
            "nonlinear_additive_noise_sieve"
            if resolved_model_family == "nonlinear"
            else "linear_ols"
        ),
        assumptions=assumptions,
        min_environments_required=min_envs,
        min_informative_environments_required=min_informative,
        environment_diversity_requirements=diversity_requirements,
        informative_envs=tuple(sorted(informative_envs)),
        redundant_envs=tuple(sorted(redundant_envs)),
        diversity_satisfied=diversity_satisfied,
        identification_scope=identification_scope,
    )


def _build_candidate_component_adjacency(
    *,
    candidate_parent_names_by_target: Mapping[str, tuple[str, ...]],
    forced_orientations: tuple[tuple[str, str], ...] = (),
) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {}

    def _ensure(node: str) -> None:
        adjacency.setdefault(node, set())

    for target, parents in candidate_parent_names_by_target.items():
        _ensure(target)
        for parent in parents:
            _ensure(parent)
            adjacency[target].add(parent)
            adjacency[parent].add(target)
    for src, dst in forced_orientations:
        _ensure(src)
        _ensure(dst)
        adjacency[src].add(dst)
        adjacency[dst].add(src)
    return adjacency


def _connected_components(adjacency: Mapping[str, set[str]]) -> list[tuple[str, ...]]:
    remaining = set(adjacency)
    components: list[tuple[str, ...]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = {start}
        while stack:
            node = stack.pop()
            for neighbor in adjacency.get(node, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(tuple(sorted(component)))
    components.sort(key=lambda comp: (-len(comp), comp))
    return components


def _treewidth_upper_bound(
    adjacency: Mapping[str, set[str]],
    component: tuple[str, ...],
) -> int:
    working = {
        node: set(neighbor for neighbor in adjacency.get(node, set()) if neighbor in component)
        for node in component
    }
    width = 0
    while working:
        node = min(working, key=lambda item: (len(working[item]), item))
        neighbors = set(working[node])
        width = max(width, len(neighbors))
        for left in neighbors:
            for right in neighbors:
                if left == right:
                    continue
                working[left].add(right)
        for neighbor in neighbors:
            working[neighbor].discard(node)
        del working[node]
    return width


def _selected_parent_map_is_acyclic(parent_map: Mapping[str, tuple[str, ...]]) -> bool:
    adjacency: dict[str, set[str]] = {}
    for target, parents in parent_map.items():
        adjacency.setdefault(target, set())
        for parent in parents:
            adjacency.setdefault(parent, set()).add(target)
            adjacency.setdefault(target, set())

    visiting: set[str] = set()
    visited: set[str] = set()

    def _dfs(node: str) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for neighbor in adjacency.get(node, set()):
            if not _dfs(neighbor):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    return all(_dfs(node) for node in list(adjacency))


def _exact_reconcile_parent_sets(
    *,
    target_results: list[RegimeShiftTargetResult],
    component_sizes: tuple[int, ...],
    treewidth_upper_bounds: tuple[int, ...],
    exact_component_cap: int,
    exact_treewidth_cap: int,
) -> tuple[dict[str, tuple[str, ...]], tuple[tuple[str, str], ...], str | None]:
    candidate_parent_names_by_target = {
        target.target: tuple(
            sorted(
                {
                    variable
                    for result in target.accepted_sets
                    for variable in result.S
                }
            )
        )
        for target in target_results
    }
    adjacency = _build_candidate_component_adjacency(
        candidate_parent_names_by_target=candidate_parent_names_by_target
    )
    components = _connected_components(adjacency)
    if not components:
        return {}, (), None
    if any(size > exact_component_cap for size in component_sizes):
        return {}, (), f"component_size_cap_exceeded>{exact_component_cap}"
    if any(bound > exact_treewidth_cap for bound in treewidth_upper_bounds):
        return {}, (), f"treewidth_cap_exceeded>{exact_treewidth_cap}"

    targets_by_name = {target.target: target for target in target_results}
    selected_parent_sets: dict[str, tuple[str, ...]] = {}
    forced_edges: set[tuple[str, str]] = set()

    for component in components:
        component_targets = [
            targets_by_name[name] for name in component if name in targets_by_name
        ]
        if not component_targets:
            continue
        if any(not target.accepted_sets for target in component_targets):
            return {}, (), "accepted_set_missing_for_exact_component"

        ordered_targets = sorted(
            component_targets,
            key=lambda target: (len(target.accepted_sets), target.target),
        )
        best_edge_count: int | None = None
        best_score: float | None = None
        optimal_solutions: list[dict[str, tuple[str, ...]]] = []
        search_budget = 4096
        n_evaluated = 0

        def _backtrack(index: int, current: dict[str, tuple[str, ...]], score: float) -> bool:
            nonlocal best_edge_count, best_score, n_evaluated
            if index >= len(ordered_targets):
                n_evaluated += 1
                edge_count = sum(len(parents) for parents in current.values())
                if best_edge_count is None or edge_count < best_edge_count:
                    best_edge_count = edge_count
                    best_score = score
                    optimal_solutions.clear()
                    optimal_solutions.append(dict(current))
                elif edge_count == best_edge_count:
                    if best_score is None or score > best_score + 1e-12:
                        best_score = score
                        optimal_solutions.clear()
                        optimal_solutions.append(dict(current))
                    elif best_score is not None and abs(score - best_score) <= 1e-12:
                        optimal_solutions.append(dict(current))
                return n_evaluated <= search_budget

            target = ordered_targets[index]
            for accepted_set in target.accepted_sets:
                current[target.target] = tuple(sorted(accepted_set.S))
                if _selected_parent_map_is_acyclic(current):
                    p_value = float(accepted_set.p_value or 0.0)
                    if not _backtrack(index + 1, current, score + p_value):
                        return False
                current.pop(target.target, None)
            return True

        completed = _backtrack(0, {}, 0.0)
        if not completed:
            return {}, (), "exact_search_budget_exhausted"
        if not optimal_solutions:
            return {}, (), "no_acyclic_assignment_found"

        common_parent_sets: dict[str, set[str]] = {}
        for target in ordered_targets:
            common_parent_sets[target.target] = set(optimal_solutions[0].get(target.target, ()))
            for solution in optimal_solutions[1:]:
                common_parent_sets[target.target] &= set(solution.get(target.target, ()))

        for target_name, parents in common_parent_sets.items():
            selected_parent_sets[target_name] = tuple(sorted(parents))
            for parent in parents:
                forced_edges.add((parent, target_name))

    return selected_parent_sets, tuple(sorted(forced_edges)), None


def _build_revalidation_parent_map(
    *,
    target_results: list[RegimeShiftTargetResult],
) -> dict[str, tuple[str, ...]]:
    return {
        target.target: tuple(sorted(target.estimated_parents))
        for target in target_results
        if target.estimated_parents
    }


def _build_track7_revalidation_graph(
    *,
    variable_names: list[str],
    parent_map: Mapping[str, tuple[str, ...]],
    algebraic_blocks: list[AlgebraicBlockSpec],
) -> CausalGraphModel:
    edges = [
        CausalEdge(
            src=parent,
            dst=target,
            mark_src=EdgeMark.TAIL,
            mark_dst=EdgeMark.ARROW,
        )
        for target, parents in sorted(parent_map.items())
        for parent in parents
    ]
    metadata = {
        "stage": "16.3",
        "track7_revalidation": True,
        "algebraic_blocks": [block.model_dump(mode="json") for block in algebraic_blocks],
    }
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=list(variable_names),
        edges=edges,
        discovery_method="regime_shift_track7_revalidation",
        metadata=metadata,
    )


def _summarize_track7_revalidation(
    report: AlgebraicConstraintReport,
) -> RegimeShiftTrack7Revalidation:
    violated_by_family = {
        str(family_name): int(count)
        for family_name, count in report.violated_by_family.items()
        if str(family_name) in _TRACK7_FAMILY_NAMES and int(count) > 0
    }
    blocker_families = {
        str(family_name)
        for family_name, blocked in report.blocker_conditions_met_by_family.items()
        if str(family_name) in _TRACK7_FAMILY_NAMES and bool(blocked)
    }
    blocker_families.update(
        (
            violation.family.value
            if hasattr(violation.family, "value")
            else str(violation.family)
        )
        for violation in report.violated_constraints_preview
        if (
            (
                violation.family.value
                if hasattr(violation.family, "value")
                else str(violation.family)
            )
            in _TRACK7_FAMILY_NAMES
            and violation.severity == "blocker"
        )
    )
    if blocker_families:
        severity: str | None = "blocker"
    elif violated_by_family:
        severity = "warning"
    else:
        severity = "info"
    return RegimeShiftTrack7Revalidation(
        performed=True,
        severity=severity,
        violated_by_family=violated_by_family,
        blocker_families=tuple(sorted(blocker_families)),
        warnings=tuple(report.warnings),
        exact_certificate_valid=not blocker_families,
    )


def _run_track7_revalidation(
    *,
    data: np.ndarray,
    variable_names: list[str],
    target_results: list[RegimeShiftTargetResult],
    algebraic_blocks: list[AlgebraicBlockSpec],
    alpha: float,
    seed: int,
) -> RegimeShiftTrack7Revalidation:
    if not algebraic_blocks:
        return RegimeShiftTrack7Revalidation()
    parent_map = _build_revalidation_parent_map(target_results=target_results)
    graph = _build_track7_revalidation_graph(
        variable_names=variable_names,
        parent_map=parent_map,
        algebraic_blocks=algebraic_blocks,
    )
    from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
        _run_algebraic_constraint_audit,
    )

    try:
        report = _run_algebraic_constraint_audit(
            graph=graph,
            data=data,
            variable_names=variable_names,
            significance_level=alpha,
            seed=seed,
            readiness_target="diagnostic",
        )
    except Exception as exc:  # noqa: BLE001
        return RegimeShiftTrack7Revalidation(
            performed=False,
            warnings=(f"track7_revalidation_failed:{type(exc).__name__}:{exc}",),
            exact_certificate_valid=False,
        )
    return _summarize_track7_revalidation(report)


def _combine_family_p_value(p_values: list[float] | np.ndarray) -> float | None:
    finite = [
        min(max(float(value), 0.0), 1.0)
        for value in p_values
        if value is not None and np.isfinite(value)
    ]
    if not finite:
        return None
    return min(1.0, min(finite) * len(finite))


def _normalize_variable_subset(
    *,
    variable_names: list[str],
    raw_subset: Any,
    label: str,
) -> list[int] | None:
    if raw_subset is None:
        return None
    if isinstance(raw_subset, str):
        raw_subset = [item.strip() for item in raw_subset.split(",") if item.strip()]
    elif isinstance(raw_subset, (int, np.integer)):
        raw_subset = [int(raw_subset)]
    indices: list[int] = []
    name_to_idx = {name: idx for idx, name in enumerate(variable_names)}
    for raw_item in raw_subset:
        if isinstance(raw_item, str) and not raw_item.isdigit():
            idx = name_to_idx.get(raw_item)
            if idx is None:
                raise ValueError(f"{label}: unknown variable {raw_item!r}")
            indices.append(idx)
        else:
            idx = int(raw_item)
            if not (0 <= idx < len(variable_names)):
                raise ValueError(f"{label}: index {idx} out of range")
            indices.append(idx)
    if len(set(indices)) != len(indices):
        raise ValueError(f"{label}: duplicate variables are not allowed")
    return indices


def _run_global_shift_test(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    alpha: float,
    correction: str,
) -> tuple[ShiftTypeGlobalShiftTest, bool]:
    unique_domains = np.unique(domain_labels)
    if len(unique_domains) < 2:
        return ShiftTypeGlobalShiftTest(method="aggregated_ks_proxy", p_value=1.0), False

    variable_p_values: list[float] = []
    max_effect = 0.0
    for col_idx in range(data.shape[1]):
        pairwise_p_values: list[float] = []
        for domain_a, domain_b in combinations(unique_domains, 2):
            sample_a = data[domain_labels == domain_a, col_idx]
            sample_b = data[domain_labels == domain_b, col_idx]
            if len(sample_a) == 0 or len(sample_b) == 0:
                continue
            effect = _ks_statistic(sample_a, sample_b)
            p_value = _ks_pvalue(effect, len(sample_a), len(sample_b))
            max_effect = max(max_effect, effect)
            pairwise_p_values.append(p_value)
        variable_p_values.append(min(pairwise_p_values) if pairwise_p_values else 1.0)

    adjusted = _correct_p_values(np.asarray(variable_p_values, dtype=float), correction, alpha)
    significant = bool(np.any(adjusted < alpha))
    return (
        ShiftTypeGlobalShiftTest(
            method="aggregated_ks_proxy",
            p_value=_combine_family_p_value(adjusted.tolist()) or 1.0,
            effect_size=max_effect,
        ),
        significant,
    )


def _stratified_three_way_split(
    *,
    domain_labels: np.ndarray,
    seed: int,
    selection_fraction: float = 0.5,
    calibration_fraction: float = 0.25,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    unique_domains = np.unique(domain_labels)
    rng = np.random.default_rng(seed)
    select_indices: list[np.ndarray] = []
    calib_indices: list[np.ndarray] = []
    test_indices: list[np.ndarray] = []

    for env in unique_domains:
        env_indices = np.flatnonzero(domain_labels == env)
        if len(env_indices) < 6:
            return None
        shuffled = np.asarray(env_indices, dtype=int).copy()
        rng.shuffle(shuffled)
        n_obs = len(shuffled)
        n_select = max(1, int(round(n_obs * selection_fraction)))
        n_calib = max(1, int(round(n_obs * calibration_fraction)))
        while n_select + n_calib >= n_obs and n_calib > 1:
            n_calib -= 1
        while n_select + n_calib >= n_obs and n_select > 1:
            n_select -= 1
        n_test = n_obs - n_select - n_calib
        if n_test < 1:
            return None
        select_indices.append(shuffled[:n_select])
        calib_indices.append(shuffled[n_select : n_select + n_calib])
        test_indices.append(shuffled[n_select + n_calib :])

    return (
        np.concatenate(select_indices),
        np.concatenate(calib_indices),
        np.concatenate(test_indices),
    )


def _selection_candidate_sets(
    *,
    allowed_feature_cols: list[int],
    max_set_size: int,
) -> list[tuple[int, ...]]:
    bounded_size = min(max_set_size, len(allowed_feature_cols))
    candidate_sets: list[tuple[int, ...]] = [()]
    for size in range(1, bounded_size + 1):
        candidate_sets.extend(tuple(combo) for combo in combinations(allowed_feature_cols, size))
    return candidate_sets


def _conditional_domain_pvalues(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    conditioning_cols: tuple[int, ...],
    tested_cols: list[int],
    variable_names: list[str],
    alpha: float,
    correction: str,
) -> tuple[dict[str, float], float | None]:
    if not tested_cols:
        return {}, 1.0
    raw = np.ones(len(tested_cols), dtype=float)
    for idx, target_col in enumerate(tested_cols):
        _, p_value = _f_test_heterogeneity(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            feature_cols=list(conditioning_cols),
        )
        raw[idx] = p_value
    adjusted = _correct_p_values(raw, correction, alpha)
    per_variable = {
        variable_names[target_col]: float(adjusted[idx])
        for idx, target_col in enumerate(tested_cols)
    }
    return per_variable, _combine_family_p_value(adjusted.tolist())


def _environment_association_score(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    feature_cols: tuple[int, ...],
) -> float:
    if not feature_cols:
        return 0.0
    unique_domains = np.unique(domain_labels)
    score = 0.0
    for feature_col in feature_cols:
        pairwise_min_p = 1.0
        for domain_a, domain_b in combinations(unique_domains, 2):
            sample_a = data[domain_labels == domain_a, feature_col]
            sample_b = data[domain_labels == domain_b, feature_col]
            if len(sample_a) == 0 or len(sample_b) == 0:
                continue
            effect = _ks_statistic(sample_a, sample_b)
            p_value = _ks_pvalue(effect, len(sample_a), len(sample_b))
            pairwise_min_p = min(pairwise_min_p, p_value)
        score += max(0.0, -math.log10(max(pairwise_min_p, 1e-12)))
    return score


def _selection_overlap_metrics(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    conditioning_cols: tuple[int, ...],
) -> tuple[ShiftTypeOverlapStatus, float, float]:
    n_obs = len(domain_labels)
    unique_domains = np.unique(domain_labels)
    n_envs = len(unique_domains)
    if n_obs == 0 or n_envs < 2:
        return ShiftTypeOverlapStatus.FAILED, 0.0, float("inf")

    if not conditioning_cols:
        env_frequencies = {env: np.mean(domain_labels == env) for env in unique_domains}
        assigned_prob = np.asarray(
            [env_frequencies[env] for env in domain_labels],
            dtype=float,
        )
    else:
        X = data[:, list(conditioning_cols)]
        X_aug = np.column_stack([np.ones(n_obs), X])
        scores = np.zeros((n_obs, n_envs), dtype=float)
        for env_idx, env in enumerate(unique_domains):
            indicator = (domain_labels == env).astype(float)
            try:
                beta, _ = _ols_fit(X, indicator)
                scores[:, env_idx] = np.clip(X_aug @ beta, 1e-3, None)
            except Exception:  # noqa: BLE001
                scores[:, env_idx] = 1.0
        row_sums = scores.sum(axis=1, keepdims=True)
        bad_rows = row_sums[:, 0] <= _EPS
        if np.any(bad_rows):
            scores[bad_rows, :] = 1.0
            row_sums = scores.sum(axis=1, keepdims=True)
        probs = np.clip(scores / row_sums, 1e-3, 1.0)
        probs = probs / probs.sum(axis=1, keepdims=True)
        env_index = {env: idx for idx, env in enumerate(unique_domains)}
        assigned_prob = np.asarray(
            [probs[row_idx, env_index[env]] for row_idx, env in enumerate(domain_labels)],
            dtype=float,
        )

    assigned_prob = np.clip(assigned_prob, 0.01, 1.0)
    weights = 1.0 / assigned_prob
    weight_sum = float(np.sum(weights))
    ess = (
        (weight_sum * weight_sum) / float(np.sum(weights**2))
        if weight_sum > 0.0
        else 0.0
    )
    max_weight = float(np.max(weights)) if len(weights) else 0.0

    if ess < max(20.0, 0.2 * n_obs) or max_weight > 20.0:
        status = ShiftTypeOverlapStatus.FAILED
    elif ess < max(50.0, 0.5 * n_obs) or max_weight > 10.0:
        status = ShiftTypeOverlapStatus.WEAK
    else:
        status = ShiftTypeOverlapStatus.OK
    return status, ess, max_weight


def _build_selection_only_witness(
    *,
    select_data: np.ndarray,
    select_domain_labels: np.ndarray,
    calib_data: np.ndarray,
    calib_domain_labels: np.ndarray,
    test_data: np.ndarray,
    test_domain_labels: np.ndarray,
    variable_names: list[str],
    target_cols: list[int],
    baseline_covariate_cols: list[int] | None,
    alpha: float,
    correction: str,
    max_set_size: int,
) -> tuple[
    ShiftTypeSelectionOnlyWitness,
    ShiftTypeObservedSelectionSufficiency,
    ShiftTypeOverlapStatus,
]:
    if baseline_covariate_cols is None:
        return (
            ShiftTypeSelectionOnlyWitness(status=ShiftTypeWitnessStatus.UNTESTABLE),
            ShiftTypeObservedSelectionSufficiency.UNTESTED,
            ShiftTypeOverlapStatus.OK,
        )

    candidate_sets = _selection_candidate_sets(
        allowed_feature_cols=baseline_covariate_cols,
        max_set_size=max_set_size,
    )
    target_idx_set = set(target_cols)
    best_payload: dict[str, Any] | None = None

    for conditioning_cols in candidate_sets:
        tested_cols = [
            idx
            for idx in range(len(variable_names))
            if idx not in conditioning_cols
        ]
        if not tested_cols:
            continue
        per_variable_p_values, family_p_value = _conditional_domain_pvalues(
            data=select_data,
            domain_labels=select_domain_labels,
            conditioning_cols=conditioning_cols,
            tested_cols=tested_cols,
            variable_names=variable_names,
            alpha=alpha,
            correction=correction,
        )
        rejection_count = sum(
            1 for value in per_variable_p_values.values() if value < alpha
        )
        target_rejection_count = sum(
            1
            for idx in target_idx_set
            if variable_names[idx] in per_variable_p_values
            and per_variable_p_values[variable_names[idx]] < alpha
        )
        payload = {
            "conditioning_cols": conditioning_cols,
            "p_value": family_p_value,
            "rejection_count": rejection_count,
            "target_rejection_count": target_rejection_count,
            "association_score": _environment_association_score(
                data=select_data,
                domain_labels=select_domain_labels,
                feature_cols=conditioning_cols,
            ),
        }
        if best_payload is None:
            best_payload = payload
            continue
        current_rank = (
            payload["target_rejection_count"],
            payload["rejection_count"],
            -(payload["p_value"] or 0.0),
            -payload["association_score"],
            len(payload["conditioning_cols"]),
        )
        best_rank = (
            best_payload["target_rejection_count"],
            best_payload["rejection_count"],
            -(best_payload["p_value"] or 0.0),
            -best_payload["association_score"],
            len(best_payload["conditioning_cols"]),
        )
        if current_rank < best_rank:
            best_payload = payload

    if best_payload is None:
        return (
            ShiftTypeSelectionOnlyWitness(status=ShiftTypeWitnessStatus.UNTESTABLE),
            ShiftTypeObservedSelectionSufficiency.UNTESTED,
            ShiftTypeOverlapStatus.OK,
        )

    selected_conditioning_cols = tuple(best_payload["conditioning_cols"])
    tested_cols = [
        idx for idx in range(len(variable_names)) if idx not in selected_conditioning_cols
    ]
    per_variable_p_values, family_p_value = _conditional_domain_pvalues(
        data=test_data,
        domain_labels=test_domain_labels,
        conditioning_cols=selected_conditioning_cols,
        tested_cols=tested_cols,
        variable_names=variable_names,
        alpha=alpha,
        correction=correction,
    )
    local_overlap, ess, max_weight = _selection_overlap_metrics(
        data=calib_data,
        domain_labels=calib_domain_labels,
        conditioning_cols=selected_conditioning_cols,
    )
    target_rejection_count = sum(
        1
        for idx in target_idx_set
        if variable_names[idx] in per_variable_p_values
        and per_variable_p_values[variable_names[idx]] < alpha
    )
    rejection_count = sum(1 for value in per_variable_p_values.values() if value < alpha)
    status = (
        ShiftTypeWitnessStatus.NOT_REJECTED
        if rejection_count == 0
        and target_rejection_count == 0
        and local_overlap != ShiftTypeOverlapStatus.FAILED
        else ShiftTypeWitnessStatus.REJECTED
    )
    sufficiency = (
        ShiftTypeObservedSelectionSufficiency.SUPPORTED
        if status is ShiftTypeWitnessStatus.NOT_REJECTED
        else ShiftTypeObservedSelectionSufficiency.UNSUPPORTED
    )
    return (
        ShiftTypeSelectionOnlyWitness(
            status=status,
            balancing_set=tuple(
                variable_names[idx] for idx in selected_conditioning_cols
            ),
            p_value=family_p_value,
            per_variable_p_values=per_variable_p_values,
            max_weight=max_weight,
            ess_min=ess,
        ),
        sufficiency,
        local_overlap,
    )


def _build_structural_only_witness(
    *,
    select_data: np.ndarray,
    select_domain_labels: np.ndarray,
    test_data: np.ndarray,
    test_domain_labels: np.ndarray,
    variable_names: list[str],
    target_cols: list[int],
    alpha: float,
    correction: str,
    max_set_size: int,
    model_family: str,
) -> ShiftTypeStructuralOnlyWitness:
    accepted_parent_sets: dict[str, tuple[str, ...]] = {}
    per_target_p_values: dict[str, float] = {}
    targets_tested: list[str] = []
    informative_target_count = 0

    for target_col in target_cols:
        target = variable_names[target_col]
        targets_tested.append(target)
        candidate_sets = _candidate_sets_for_target(
            candidate_parent_cols=[
                idx for idx in range(select_data.shape[1]) if idx != target_col
            ],
            max_set_size=max_set_size,
            variable_names=variable_names,
        )
        accepted, _ = _evaluate_candidate_sets(
            data=select_data,
            domain_labels=select_domain_labels,
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            alpha=alpha,
            correction=correction,
            model_family=model_family,
        )
        if not accepted:
            continue
        parents = _accepted_intersection(accepted)
        if not parents:
            representative_set = max(
                accepted,
                key=lambda item: item.p_value if item.p_value is not None else -1.0,
            )
            parents = representative_set.S
        test_p_value = _evaluate_parent_set_holdout_p_value(
            data=test_data,
            domain_labels=test_domain_labels,
            target_col=target_col,
            feature_cols=[variable_names.index(parent) for parent in parents],
            model_family=model_family,
        )
        per_target_p_values[target] = float(test_p_value)
        if test_p_value < alpha:
            continue
        if parents:
            informative_target_count += 1
        accepted_parent_sets[target] = tuple(parents)

    if len(accepted_parent_sets) != len(target_cols):
        status = ShiftTypeWitnessStatus.REJECTED
    elif informative_target_count == 0:
        status = ShiftTypeWitnessStatus.UNTESTABLE
    else:
        status = ShiftTypeWitnessStatus.NOT_REJECTED

    return ShiftTypeStructuralOnlyWitness(
        status=status,
        targets_tested=tuple(targets_tested),
        accepted_parent_sets=accepted_parent_sets,
        p_value=_combine_family_p_value(list(per_target_p_values.values())),
        per_target_p_values=per_target_p_values,
    )


def _build_shift_type_assessment(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    variable_names: list[str],
    target_cols: list[int],
    alpha: float,
    correction: str,
    context_exogeneity: ShiftTypeContextExogeneity,
    baseline_covariate_cols: list[int] | None,
    selection_max_set_size: int,
    max_set_size: int,
    model_family: str,
    random_seed: int,
    repro_splits: int,
) -> tuple[RegimeShiftTypeAssessment, dict[str, Any]]:
    def _build_once(split_seed: int) -> tuple[RegimeShiftTypeAssessment, bool]:
        split_indices = _stratified_three_way_split(
            domain_labels=domain_labels,
            seed=split_seed,
        )
        split_confirmation_used = split_indices is not None
        if split_indices is None:
            select_data = data
            select_domain_labels = domain_labels
            calib_data = data
            calib_domain_labels = domain_labels
            test_data = data
            test_domain_labels = domain_labels
        else:
            select_idx, calib_idx, test_idx = split_indices
            select_data = data[select_idx]
            select_domain_labels = domain_labels[select_idx]
            calib_data = data[calib_idx]
            calib_domain_labels = domain_labels[calib_idx]
            test_data = data[test_idx]
            test_domain_labels = domain_labels[test_idx]

        alpha_split = ShiftTypeAlphaSplit(
            shift=alpha / 3.0,
            selection=alpha / 3.0,
            structural=alpha / 3.0,
        )
        global_shift_test, shift_detected = _run_global_shift_test(
            data=data,
            domain_labels=domain_labels,
            alpha=alpha_split.shift,
            correction=correction,
        )
        structural_witness = _build_structural_only_witness(
            select_data=select_data,
            select_domain_labels=select_domain_labels,
            test_data=test_data,
            test_domain_labels=test_domain_labels,
            variable_names=variable_names,
            target_cols=target_cols,
            alpha=alpha_split.structural,
            correction=correction,
            max_set_size=max_set_size,
            model_family=model_family,
        )
        selection_witness, observed_selection_sufficiency, overlap = (
            _build_selection_only_witness(
                select_data=select_data,
                select_domain_labels=select_domain_labels,
                calib_data=calib_data,
                calib_domain_labels=calib_domain_labels,
                test_data=test_data,
                test_domain_labels=test_domain_labels,
                variable_names=variable_names,
                target_cols=target_cols,
                baseline_covariate_cols=baseline_covariate_cols,
                alpha=alpha_split.selection,
                correction=correction,
                max_set_size=selection_max_set_size,
            )
        )

        if not shift_detected:
            overall_label = ShiftTypeOverallLabel.UNINFORMATIVE_SHIFT
        elif (
            structural_witness.status is ShiftTypeWitnessStatus.NOT_REJECTED
            and selection_witness.status is ShiftTypeWitnessStatus.REJECTED
            and context_exogeneity in {
                ShiftTypeContextExogeneity.DECLARED,
                ShiftTypeContextExogeneity.DESIGN_BASED,
            }
        ):
            overall_label = ShiftTypeOverallLabel.STRUCTURAL_ONLY_CONSISTENT
        elif (
            selection_witness.status is ShiftTypeWitnessStatus.NOT_REJECTED
            and structural_witness.status is ShiftTypeWitnessStatus.REJECTED
        ):
            overall_label = ShiftTypeOverallLabel.SELECTION_ONLY_CONSISTENT
        elif (
            selection_witness.status is ShiftTypeWitnessStatus.REJECTED
            and structural_witness.status is ShiftTypeWitnessStatus.REJECTED
        ):
            overall_label = ShiftTypeOverallLabel.MIXED_OR_LATENT_SUSPECTED
        else:
            overall_label = ShiftTypeOverallLabel.AMBIGUOUS

        if overall_label is ShiftTypeOverallLabel.STRUCTURAL_ONLY_CONSISTENT:
            if context_exogeneity is ShiftTypeContextExogeneity.DESIGN_BASED:
                certification_level = ShiftTypeCertificationLevel.CERTIFIED
            else:
                certification_level = ShiftTypeCertificationLevel.PROVISIONAL
        elif overall_label is ShiftTypeOverallLabel.SELECTION_ONLY_CONSISTENT:
            if (
                observed_selection_sufficiency
                is ShiftTypeObservedSelectionSufficiency.SUPPORTED
                and overlap is ShiftTypeOverlapStatus.OK
            ):
                certification_level = ShiftTypeCertificationLevel.CERTIFIED
            else:
                certification_level = ShiftTypeCertificationLevel.PROVISIONAL
        else:
            certification_level = ShiftTypeCertificationLevel.SCREEN_ONLY

        if overall_label is ShiftTypeOverallLabel.STRUCTURAL_ONLY_CONSISTENT:
            pipeline_action = ShiftTypePipelineAction(
                allow_icp_graph_contraction=True,
            )
            narrative_summary = (
                "Global environment shifts were detected, the structural-only invariant-parent "
                "witness was not rejected on holdout, and the observed selection-only witness "
                "was rejected."
            )
        elif overall_label is ShiftTypeOverallLabel.SELECTION_ONLY_CONSISTENT:
            pipeline_action = ShiftTypePipelineAction(
                allow_selection_transport_path=True,
                block_reason="selection_only_consistent",
            )
            narrative_summary = (
                "Observed shifts are compatible with a selection-only witness on holdout and "
                "should be routed to a transportability-style path instead of ICP graph contraction."
            )
        elif overall_label is ShiftTypeOverallLabel.MIXED_OR_LATENT_SUSPECTED:
            pipeline_action = ShiftTypePipelineAction(
                route_to_latent_aware_discovery=True,
                block_reason="mixed_or_latent_suspected",
            )
            narrative_summary = (
                "Both simple witnesses were rejected on holdout, so regime labels are unsafe "
                "for ICP-style contraction and should be treated as mixed or latent-confounded."
            )
        elif overall_label is ShiftTypeOverallLabel.UNINFORMATIVE_SHIFT:
            pipeline_action = ShiftTypePipelineAction(
                block_reason="uninformative_shift",
            )
            narrative_summary = (
                "No stable global shift signal was detected across environments, so the regime "
                "labels do not add identification leverage."
            )
        else:
            pipeline_action = ShiftTypePipelineAction(
                block_reason="ambiguous_shift_type",
            )
            narrative_summary = (
                "The available witnesses do not cleanly separate structural shifts from selection "
                "or latent confounding, so the safe outcome is ambiguous."
            )
        if not split_confirmation_used:
            narrative_summary += " Sample-split confirmation was skipped because some environments were too small."

        return (
            RegimeShiftTypeAssessment(
                overall_label=overall_label,
                certification_level=certification_level,
                alpha_total=alpha,
                alpha_split=alpha_split,
                assumptions=ShiftTypeAssumptions(
                    context_exogeneity=context_exogeneity,
                    observed_selection_sufficiency=observed_selection_sufficiency,
                    overlap=overlap,
                ),
                witnesses=ShiftTypeWitnessBundle(
                    global_shift_test=global_shift_test,
                    selection_only_witness=selection_witness,
                    structural_only_witness=structural_witness,
                ),
                pipeline_action=pipeline_action,
                narrative_summary=narrative_summary,
            ),
            split_confirmation_used,
        )

    assessment, split_confirmation_used = _build_once(random_seed)
    label_counts: dict[str, int] = {assessment.overall_label.value: 1}
    agreement = 1.0
    seeds_used = [random_seed]
    if repro_splits > 1:
        matching = 1
        for offset in range(1, repro_splits):
            alt_seed = random_seed + offset
            alt_assessment, _ = _build_once(alt_seed)
            label_counts[alt_assessment.overall_label.value] = (
                label_counts.get(alt_assessment.overall_label.value, 0) + 1
            )
            seeds_used.append(alt_seed)
            if alt_assessment.overall_label is assessment.overall_label:
                matching += 1
        agreement = matching / float(repro_splits)

    certification_level = assessment.certification_level
    narrative_summary = assessment.narrative_summary
    pipeline_action = assessment.pipeline_action
    if agreement < 1.0 and certification_level is not ShiftTypeCertificationLevel.SCREEN_ONLY:
        certification_level = ShiftTypeCertificationLevel.SCREEN_ONLY
        narrative_summary += (
            f" Reproducibility check downgraded certification because the label only "
            f"reproduced on {int(round(agreement * repro_splits))}/{repro_splits} split seeds."
        )
    elif repro_splits > 1:
        narrative_summary += (
            f" Reproducibility check matched on {int(round(agreement * repro_splits))}/{repro_splits} split seeds."
        )
    if not split_confirmation_used and certification_level is not ShiftTypeCertificationLevel.SCREEN_ONLY:
        certification_level = ShiftTypeCertificationLevel.SCREEN_ONLY
        narrative_summary += " Certification was downgraded because split confirmation was unavailable."
    if (
        certification_level is ShiftTypeCertificationLevel.SCREEN_ONLY
        and assessment.overall_label
        in {
            ShiftTypeOverallLabel.STRUCTURAL_ONLY_CONSISTENT,
            ShiftTypeOverallLabel.SELECTION_ONLY_CONSISTENT,
        }
    ):
        pipeline_action = ShiftTypePipelineAction(
            block_reason="screen_only_shift_type_assessment",
        )
        narrative_summary += " Screen-only assessments are retained as weak evidence and do not unlock strong pipeline routes."

    updated_assessment = assessment.model_copy(
        update={
            "certification_level": certification_level,
            "pipeline_action": pipeline_action,
            "narrative_summary": narrative_summary,
        }
    )
    reproducibility_metadata = {
        "agreement": agreement,
        "n_splits": repro_splits,
        "label_counts": label_counts,
        "seeds": seeds_used,
        "split_confirmation_used": split_confirmation_used,
    }
    return updated_assessment, reproducibility_metadata


def _build_regime_shift_certificate(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    variable_names: list[str],
    target_cols: list[int],
    alpha: float,
    correction: str,
    max_set_size: int,
    model_family: str,
    screening: str | None,
    dataset_ref: str | None,
    context_exogeneity: ShiftTypeContextExogeneity,
    baseline_covariate_cols: list[int] | None,
    selection_max_set_size: int,
    shift_type_random_seed: int,
    shift_type_repro_splits: int,
    super_structure: Any | None,
    algebraic_blocks: Any,
    prior_algebraic_reports: Any,
    max_candidate_parents: int,
    local_separator_cap: int | None,
    exact_component_cap: int,
    exact_treewidth_cap: int,
) -> RegimeShiftIdentificationCertificate:
    unique_domains, counts = np.unique(domain_labels, return_counts=True)
    env_ids = [str(env) for env in unique_domains]
    env_counts = {
        str(env): int(count) for env, count in zip(unique_domains, counts, strict=True)
    }
    route_resolution = _resolve_regime_model_family(
        data=data,
        domain_labels=domain_labels,
        target_cols=target_cols,
        model_family=model_family,
    )
    resolved_model_family = str(route_resolution["resolved"])
    n_environment_pairs = max(1, len(env_ids) * (len(env_ids) - 1) // 2)
    environment_shift_summaries = _build_environment_shift_summaries(
        data=data,
        domain_labels=domain_labels,
        variable_names=variable_names,
        target_cols=target_cols,
    )
    environments = tuple(
        RegimeShiftEnvironmentRecord(
            env_id=env_id,
            regime_id=env_id,
            shift_summary={
                "detected_covariate_shifts": environment_shift_summaries[env_id][
                    "detected_covariate_shifts"
                ],
                "detected_target_shift_flags": environment_shift_summaries[env_id][
                    "detected_target_shift_flags"
                ],
            },
        )
        for env_id in env_ids
    )
    super_structure_graph = _normalize_super_structure(raw_super_structure=super_structure)
    resolved_algebraic_blocks = _normalize_algebraic_blocks(algebraic_blocks)
    resolved_prior_algebraic_reports = _normalize_algebraic_reports(prior_algebraic_reports)
    prior_track7_blocker_families = _extract_track7_blocker_families_from_reports(
        resolved_prior_algebraic_reports
    )

    target_results: list[RegimeShiftTargetResult] = []
    forced_orientations: list[tuple[str, str]] = []
    forbidden_orientations: list[tuple[str, str]] = []
    all_warnings: list[str] = []
    all_warnings.extend(route_resolution["warnings"])
    candidate_parent_sizes: dict[str, int] = {}
    candidate_parent_names_by_target: dict[str, tuple[str, ...]] = {}
    suppressed_candidates_by_target: dict[str, tuple[str, ...]] = {}
    mutually_exclusive_groups_by_target: dict[str, tuple[tuple[str, ...], ...]] = {}
    track7_forbidden_edges: set[tuple[str, str]] = set()
    expected_test_count = 0

    for target_col in target_cols:
        target = variable_names[target_col]
        candidate_parent_cols = _candidate_parent_pool_for_target(
            variable_names=variable_names,
            target_col=target_col,
            super_structure=super_structure_graph,
        )
        (
            candidate_parent_cols,
            suppressed_candidates,
            mutually_exclusive_groups,
            target_track7_forbidden_edges,
        ) = _track7_prune_candidate_pool(
            target=target,
            candidate_cols=candidate_parent_cols,
            variable_names=variable_names,
            algebraic_blocks=resolved_algebraic_blocks,
        )
        if suppressed_candidates:
            suppressed_candidates_by_target[target] = suppressed_candidates
        if mutually_exclusive_groups:
            mutually_exclusive_groups_by_target[target] = mutually_exclusive_groups
        track7_forbidden_edges.update(target_track7_forbidden_edges)
        candidate_parent_cols, resolved_screening = _screen_candidate_parent_cols(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            candidate_cols=candidate_parent_cols,
            screening=screening,
            max_candidate_parents=max_candidate_parents,
        )
        candidate_parent_names = tuple(
            variable_names[idx] for idx in sorted(candidate_parent_cols)
        )
        candidate_parent_names_by_target[target] = candidate_parent_names
        candidate_parent_sizes[target] = len(candidate_parent_cols)
        candidate_sets = _candidate_sets_for_target(
            candidate_parent_cols=candidate_parent_cols,
            max_set_size=max_set_size,
            mutually_exclusive_groups=mutually_exclusive_groups,
            variable_names=variable_names,
        )
        expected_test_count += len(candidate_sets) * n_environment_pairs
        accepted, rejected = _evaluate_candidate_sets(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            alpha=alpha,
            correction=correction,
            model_family=resolved_model_family,
        )
        parents = _accepted_intersection(accepted)
        minimal_accepted_set = _minimal_accepted_set(accepted)
        empty_set_stable = any(len(result.S) == 0 for result in accepted)
        parent_changes, minimal_set_changes, redundant_envs = _leave_one_out_parent_changes(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            baseline_parents=parents,
            baseline_minimal_set=minimal_accepted_set,
            alpha=alpha,
            correction=correction,
            model_family=resolved_model_family,
            environment_patterns={
                env_id: environment_shift_summaries[env_id]["pattern"] for env_id in env_ids
            },
        )
        warnings: list[str] = []
        if not accepted:
            warnings.extend(
                [
                    "possible_intervention_on_target_detected",
                    "no_invariant_parent_set_accepted",
                ]
            )
        if empty_set_stable:
            warnings.append("regimes_redundant_for_target")
        if max_set_size > 2:
            warnings.append("low_power_parent_set_size>2")
        if suppressed_candidates:
            warnings.append("track7_candidate_suppression_applied")
        if mutually_exclusive_groups:
            warnings.append("track7_block_lifting_applied")
        all_warnings.extend(warnings)

        candidate_variables = candidate_parent_names
        target_results.append(
            RegimeShiftTargetResult(
                target=target,
                envs_used=tuple(env_ids),
                candidate_sets_tested=RegimeShiftCandidateSetPlan(
                    enumeration=(
                        "screened_subsets_upto_k"
                        if resolved_screening not in (None, "none", "off")
                        or mutually_exclusive_groups
                        else "all_subsets_upto_k"
                    ),
                    max_set_size=max_set_size,
                    screening=resolved_screening,
                ),
                accepted_sets=accepted,
                rejected_sets=rejected,
                estimated_parents=parents,
                stability_metrics=RegimeShiftStabilityMetrics(
                    accepted_set_count=len(accepted),
                    intersection_size=len(parents),
                    stability_ratio=_stability_ratio(
                        accepted_sets=accepted,
                        candidate_variables=candidate_variables,
                    ),
                ),
                informativeness=RegimeShiftInformativeness(
                    empty_set_stable=empty_set_stable,
                    redundant_envs=redundant_envs,
                    leave_one_out_parent_changes=parent_changes,
                    leave_one_out_minimal_set_changes=minimal_set_changes,
                ),
                warnings=tuple(warnings),
            )
        )

        if accepted and not empty_set_stable:
            for parent in parents:
                forced_orientations.append((parent, target))
                forbidden_orientations.append((target, parent))

    baseline_target_results = list(target_results)
    baseline_forced_orientations = list(forced_orientations)
    baseline_forbidden_orientations = list(forbidden_orientations)
    if prior_track7_blocker_families:
        all_warnings.append(
            "track7_prior_blocker_conflicts:" + ",".join(prior_track7_blocker_families)
        )

    component_adjacency = _build_candidate_component_adjacency(
        candidate_parent_names_by_target=candidate_parent_names_by_target
    )
    components = _connected_components(component_adjacency)
    component_sizes = tuple(len(component) for component in components)
    treewidth_upper_bounds = tuple(
        _treewidth_upper_bound(component_adjacency, component) for component in components
    )
    max_candidates_observed = max(candidate_parent_sizes.values(), default=0)
    largest_component = max(component_sizes, default=0)
    max_treewidth = max(treewidth_upper_bounds, default=0)
    feasibility_reasons: list[str] = []
    if largest_component <= 0:
        feasibility_reasons.append("empty_candidate_super_structure")
    if largest_component > exact_component_cap:
        feasibility_reasons.append(f"component_size_cap_exceeded>{exact_component_cap}")
    if max_treewidth > exact_treewidth_cap:
        feasibility_reasons.append(f"treewidth_cap_exceeded>{exact_treewidth_cap}")
    if max_candidates_observed > max_candidate_parents:
        feasibility_reasons.append(f"candidate_parent_cap_exceeded>{max_candidate_parents}")
    if prior_track7_blocker_families:
        feasibility_reasons.append(
            "track7_prior_blocker_conflict:" + ",".join(prior_track7_blocker_families)
        )
    exact_mode_possible = not feasibility_reasons

    selected_parent_sets: dict[str, tuple[str, ...]] = {}
    exact_forced_orientations: tuple[tuple[str, str], ...] = ()
    exact_fallback_reason: str | None = ";".join(feasibility_reasons) or None
    if exact_mode_possible:
        (
            selected_parent_sets,
            exact_forced_orientations,
            exact_fallback_reason,
        ) = _exact_reconcile_parent_sets(
            target_results=target_results,
            component_sizes=component_sizes,
            treewidth_upper_bounds=treewidth_upper_bounds,
            exact_component_cap=exact_component_cap,
            exact_treewidth_cap=exact_treewidth_cap,
        )

    exact_mode_applied = exact_mode_possible and exact_fallback_reason is None
    if exact_mode_applied:
        forced_orientations = list(exact_forced_orientations)
        forbidden_orientations = [(dst, src) for src, dst in forced_orientations]
        target_results = [
            target.model_copy(
                update={
                    "estimated_parents": selected_parent_sets.get(target.target, target.estimated_parents)
                }
            )
            for target in target_results
        ]

    track7_revalidation = _run_track7_revalidation(
        data=data,
        variable_names=variable_names,
        target_results=target_results,
        algebraic_blocks=resolved_algebraic_blocks,
        alpha=alpha,
        seed=shift_type_random_seed,
    )
    if track7_revalidation.warnings:
        all_warnings.extend(track7_revalidation.warnings)
    if track7_revalidation.performed and track7_revalidation.blocker_families:
        blocker_reason = "track7_revalidation_blocker:" + ",".join(
            track7_revalidation.blocker_families
        )
        all_warnings.append(blocker_reason)
        exact_fallback_reason = _append_fallback_reason(exact_fallback_reason, blocker_reason)
        if exact_mode_applied:
            target_results = list(baseline_target_results)
            forced_orientations = list(baseline_forced_orientations)
            forbidden_orientations = list(baseline_forbidden_orientations)
            selected_parent_sets = {}
        exact_mode_applied = False
    elif not track7_revalidation.exact_certificate_valid:
        failure_reason = "track7_revalidation_missing_or_failed"
        all_warnings.append(failure_reason)
        exact_fallback_reason = _append_fallback_reason(exact_fallback_reason, failure_reason)
        if exact_mode_applied:
            target_results = list(baseline_target_results)
            forced_orientations = list(baseline_forced_orientations)
            forbidden_orientations = list(baseline_forbidden_orientations)
            selected_parent_sets = {}
        exact_mode_applied = False

    estimated_runtime_seconds = float(
        round(
            0.002 * expected_test_count
            + 0.01 * sum(2 ** min(size, 10) for size in component_sizes),
            6,
        )
    )
    estimated_memory_mb = float(
        round(
            8.0
            + 0.05 * expected_test_count
            + 0.5 * sum(treewidth_upper_bounds),
            6,
        )
    )
    track7_stats = RegimeShiftTrack7InteractionStats(
        candidate_suppression_applied=bool(suppressed_candidates_by_target),
        block_lifting_applied=bool(mutually_exclusive_groups_by_target),
        suppressed_candidates_by_target=suppressed_candidates_by_target,
        mutually_exclusive_candidate_groups_by_target=mutually_exclusive_groups_by_target,
        hard_forbidden_edges=tuple(sorted(track7_forbidden_edges)),
        prior_blocker_families=prior_track7_blocker_families,
        revalidation_required=bool(resolved_algebraic_blocks),
        revalidation=track7_revalidation,
    )
    computational_feasibility = RegimeShiftComputationalFeasibility(
        mode="exact" if exact_mode_applied else "partial",
        n_variables=len(variable_names),
        n_targets=len(target_cols),
        n_environments=len(env_ids),
        n_environment_pairs=n_environment_pairs,
        conditioning_cap_q=max_set_size,
        local_separator_cap_eta=local_separator_cap,
        candidate_parent_sizes=candidate_parent_sizes,
        max_candidate_parents=max_candidates_observed,
        expected_test_count=expected_test_count,
        component_sizes=component_sizes,
        treewidth_upper_bounds=treewidth_upper_bounds,
        hard_required_edges=tuple(sorted(set(forced_orientations))),
        hard_forbidden_edges=tuple(sorted(set(forbidden_orientations) | track7_forbidden_edges)),
        exact_mode_possible=exact_mode_possible,
        exact_mode_applied=exact_mode_applied,
        fallback_reason=exact_fallback_reason,
        estimated_runtime_seconds=estimated_runtime_seconds,
        estimated_memory_mb=estimated_memory_mb,
        selected_parent_sets=selected_parent_sets,
        track7=track7_stats,
    )
    if computational_feasibility.fallback_reason:
        all_warnings.append(
            f"computational_feasibility_partial:{computational_feasibility.fallback_reason}"
        )

    invariance_testing = (
        RegimeShiftInvarianceTesting(
            alpha=alpha,
            multiple_testing=correction,
            test_family="residual_energy_distance_plus_variance_guard",
            model_class="nonlinear_additive_noise_sieve",
            notes=(
                "Phase-1 certificate contract: nonlinear additive-noise ICP uses degree-3 "
                "cross-fitted polynomial-sieve ridge regression with residual energy-distance "
                "tests and a variance-ratio guard.",
                "A nonlinear certificate is phase-closing only when shift-type screening "
                "allows ICP graph contraction and at least two informative environments remain.",
            ),
        )
        if resolved_model_family == "nonlinear"
        else RegimeShiftInvarianceTesting(
            alpha=alpha,
            multiple_testing=correction,
            test_family="f_test_environment_fixed_effect",
            model_class="linear_ols",
            notes=(
                "Phase-1 certificate contract: this run used the backward-compatible linear "
                "ICP fallback because the nonlinear additive-noise slice was unavailable.",
                "The linear fallback remains executable but does not by itself satisfy the "
                "archival nonlinear sufficient result for Stage 16.1 closure.",
                *route_resolution["notes"],
            ),
        )
    )
    assumptions = [
        "no intervention on target mechanisms",
        "stability-faithfulness for accepted invariant sets",
        "candidate parent search is complete only inside the pruned tractability regime recorded by computational_feasibility",
        "Track 7 algebraic blocks act as hard search-space reducers when supplied",
        "Track 7 algebraic constraints are revalidated after graph assembly before exact-mode promotion",
    ]
    if resolved_model_family == "nonlinear":
        assumptions.extend(
            [
                "continuous target and candidate variables for the nonlinear additive-noise route",
                "degree-3 polynomial-sieve ridge regression is treated as the certified approximation class",
                "environment informativeness is defined by leave-one-out changes to estimated parents or the minimal accepted set",
            ]
        )

    certificate = RegimeShiftIdentificationCertificate(
        produced_by=RegimeShiftProducedBy(
            method="causal.discovery.icp_regime_shifts",
            implementation=(
                "mime_icp_nonlinear_additive_noise_sieve_v1"
                if resolved_model_family == "nonlinear"
                else "mime_icp_linear_f_test_v1"
            ),
        ),
        data_signature=RegimeShiftDataSignature(
            dataset_ref=dataset_ref,
            variables=tuple(variable_names),
            sample_sizes_by_env=env_counts,
        ),
        environments=environments,
        invariance_testing=invariance_testing,
        targets=tuple(target_results),
        computational_feasibility=computational_feasibility,
        mec_contraction=RegimeShiftMECContraction(
            edge_updates=RegimeShiftMECContractionEdgeUpdates(
                forced_orientations=tuple(sorted(set(forced_orientations))),
                forbidden_orientations=tuple(sorted(set(forbidden_orientations))),
                newly_oriented_by_closure=0,
            ),
            summary=RegimeShiftMECContractionSummary(
                edges_oriented_total=len(set(forced_orientations)),
                edges_ambiguous_remaining=0,
            ),
        ),
        assumptions=tuple(assumptions),
        warnings=tuple(sorted(set(all_warnings))),
        metadata={
            "stage": "16.1",
            "track": "causal_discovery_regime_shifts",
            "shift_type_assessment_stage": "16.2",
            "tractability_stage": "16.3",
            "feasibility_mode": "exact" if exact_mode_applied else "partial",
            "model_family_requested": route_resolution["requested"],
            "model_family_resolved": resolved_model_family,
            "nonlinear_route_eligible": bool(route_resolution["nonlinear_eligible"]),
            "super_structure_used": super_structure_graph is not None,
            "track7_blocks_used": len(resolved_algebraic_blocks),
            "track7_prior_blocker_families": list(prior_track7_blocker_families),
            "track7_revalidation": track7_revalidation.model_dump(mode="json"),
        },
    )
    shift_type_assessment, reproducibility_metadata = _build_shift_type_assessment(
        data=data,
        domain_labels=domain_labels,
        variable_names=variable_names,
        target_cols=target_cols,
        alpha=alpha,
        correction=correction,
        context_exogeneity=context_exogeneity,
        baseline_covariate_cols=baseline_covariate_cols,
        selection_max_set_size=selection_max_set_size,
        max_set_size=max_set_size,
        model_family=resolved_model_family,
        random_seed=shift_type_random_seed,
        repro_splits=shift_type_repro_splits,
    )
    identifiability_witness = _build_identifiability_witness(
        env_ids=env_ids,
        target_results=target_results,
        resolved_model_family=resolved_model_family,
        shift_type_assessment=shift_type_assessment,
    )
    return certificate.model_copy(
        update={
            "identifiability_witness": identifiability_witness,
            "shift_type_assessment": shift_type_assessment,
            "metadata": {
                **dict(certificate.metadata),
                "shift_type_reproducibility": reproducibility_metadata,
                "phase_closing_stage16_1": (
                    identifiability_witness.identification_scope
                    == "phase_closing_nonlinear_additive_noise_icp"
                ),
            },
        }
    )


def build_regime_shift_identification_certificate(
    *,
    data: Any,
    domain_labels: Any,
    variable_names: list[str] | None = None,
    target_cols: list[int | str] | None = None,
    alpha: float = 0.05,
    correction: str = "bh",
    max_set_size: int = 2,
    model_family: str = "auto",
    screening: str | None = None,
    dataset_ref: str | None = None,
    context_exogeneity: str = ShiftTypeContextExogeneity.UNVERIFIED.value,
    baseline_covariates: list[int | str] | str | None = None,
    selection_max_set_size: int | None = None,
    shift_type_random_seed: int = 0,
    shift_type_repro_splits: int = 3,
    super_structure: Any | None = None,
    algebraic_blocks: Any = None,
    prior_algebraic_reports: Any = None,
    max_candidate_parents: int = 10,
    local_separator_cap: int | None = 4,
    exact_component_cap: int = 12,
    exact_treewidth_cap: int = 8,
) -> RegimeShiftIdentificationCertificate:
    """Build a typed Stage 16.1/16.2/16.3 regime-shift certificate from labelled data."""
    data_array = _as_2d_float_array(data, caller="build_regime_shift_identification_certificate")
    labels_array = np.asarray(domain_labels)
    if labels_array.ndim != 1:
        raise ValueError(
            "build_regime_shift_identification_certificate: domain_labels must be a vector"
        )
    if len(labels_array) != data_array.shape[0]:
        raise ValueError(
            "build_regime_shift_identification_certificate: domain_labels length must equal n_obs"
        )
    if len(np.unique(labels_array)) < 2:
        raise ValueError(
            "build_regime_shift_identification_certificate: at least two environments are required"
        )
    if not (0.0 <= float(alpha) <= 1.0):
        raise ValueError(
            "build_regime_shift_identification_certificate: alpha must be in [0,1]"
        )
    if int(max_set_size) < 0:
        raise ValueError(
            "build_regime_shift_identification_certificate: max_set_size must be non-negative"
        )
    if selection_max_set_size is not None and int(selection_max_set_size) < 0:
        raise ValueError(
            "build_regime_shift_identification_certificate: selection_max_set_size must be non-negative"
        )
    if int(max_candidate_parents) < 1:
        raise ValueError(
            "build_regime_shift_identification_certificate: max_candidate_parents must be >= 1"
        )
    if local_separator_cap is not None and int(local_separator_cap) < 0:
        raise ValueError(
            "build_regime_shift_identification_certificate: local_separator_cap must be non-negative"
        )
    if int(exact_component_cap) < 1:
        raise ValueError(
            "build_regime_shift_identification_certificate: exact_component_cap must be >= 1"
        )
    if int(exact_treewidth_cap) < 0:
        raise ValueError(
            "build_regime_shift_identification_certificate: exact_treewidth_cap must be non-negative"
        )
    if int(shift_type_repro_splits) < 1:
        raise ValueError(
            "build_regime_shift_identification_certificate: shift_type_repro_splits must be >= 1"
        )

    normalized_variable_names = _normalize_variable_names(
        n_features=data_array.shape[1],
        state={"variable_names": variable_names},
        params={"variable_names": variable_names},
    )
    normalized_target_cols = _normalize_target_cols(
        variable_names=normalized_variable_names,
        params={"target_cols": target_cols},
        state={},
    )
    normalized_baseline_covariates = _normalize_variable_subset(
        variable_names=normalized_variable_names,
        raw_subset=baseline_covariates,
        label="build_regime_shift_identification_certificate baseline_covariates",
    )
    if normalized_baseline_covariates is not None and (
        set(normalized_baseline_covariates) & set(normalized_target_cols)
    ):
        raise ValueError(
            "build_regime_shift_identification_certificate: baseline_covariates must not include targets"
        )
    try:
        normalized_context_exogeneity = ShiftTypeContextExogeneity(str(context_exogeneity))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ShiftTypeContextExogeneity)
        raise ValueError(
            "build_regime_shift_identification_certificate: "
            f"context_exogeneity must be one of {allowed}"
        ) from exc
    return _build_regime_shift_certificate(
        data=data_array,
        domain_labels=labels_array,
        variable_names=normalized_variable_names,
        target_cols=normalized_target_cols,
        alpha=float(alpha),
        correction=str(correction),
        max_set_size=int(max_set_size),
        model_family=str(model_family),
        screening=screening,
        dataset_ref=dataset_ref,
        context_exogeneity=normalized_context_exogeneity,
        baseline_covariate_cols=normalized_baseline_covariates,
        selection_max_set_size=int(selection_max_set_size or max_set_size),
        shift_type_random_seed=int(shift_type_random_seed),
        shift_type_repro_splits=int(shift_type_repro_splits),
        super_structure=super_structure,
        algebraic_blocks=algebraic_blocks,
        prior_algebraic_reports=prior_algebraic_reports,
        max_candidate_parents=int(max_candidate_parents),
        local_separator_cap=(
            int(local_separator_cap) if local_separator_cap is not None else None
        ),
        exact_component_cap=int(exact_component_cap),
        exact_treewidth_cap=int(exact_treewidth_cap),
    )


@foundry_method(
    namespace="causal.discovery",
    version="1.0.0",
    tags={"causal", "discovery", "icp", "regime-shift", "mec-contraction"},
)
class InvariantDiscoveryFromRegimes:
    """ICP-style regime-shift discovery that emits a first-class certificate.

    This is the Phase-1 integration surface for Stage 16.1: it records the
    invariant-set audit trail and MEC contraction deltas.  It intentionally
    exposes assumptions and warnings instead of promoting the output to an
    unconditional graph-identification claim.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="invariant_discovery_from_regimes",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "data",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_obs", "n_features"),
                ),
                SlotSpec(
                    "domain_labels",
                    SlotType.VECTOR,
                    Unit("domain", "label"),
                    shape=("n_obs",),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("certificate", "json"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="correction", default="bh"),
            ParameterSpec(name="max_set_size", default=2),
            ParameterSpec(name="model_family", default="auto"),
            ParameterSpec(name="target_cols", default=None),
            ParameterSpec(name="variable_names", default=None),
            ParameterSpec(name="screening", default=None),
            ParameterSpec(name="dataset_ref", default=None),
            ParameterSpec(name="context_exogeneity", default="unverified"),
            ParameterSpec(name="baseline_covariates", default=None),
            ParameterSpec(name="selection_max_set_size", default=None),
            ParameterSpec(name="shift_type_random_seed", default=0),
            ParameterSpec(name="shift_type_repro_splits", default=3),
            ParameterSpec(name="super_structure", default=None),
            ParameterSpec(name="algebraic_blocks", default=None),
            ParameterSpec(name="prior_algebraic_reports", default=None),
            ParameterSpec(name="max_candidate_parents", default=10),
            ParameterSpec(name="local_separator_cap", default=4),
            ParameterSpec(name="exact_component_cap", default=12),
            ParameterSpec(name="exact_treewidth_cap", default=8),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_EXP,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Builds a RegimeShiftIdentificationCertificate from multi-environment "
            "ICP-style invariant parent-set tests, then attaches a Stage 16.2 "
            "shift-type assessment and a Stage 16.3 computational-feasibility "
            "certificate for tractable Foundry integration."
        ),
        tags=frozenset({"causal", "discovery", "icp", "regime-shift"}),
        citations=(
            "Peters, J., Bühlmann, P., Meinshausen, N. (2016). Causal inference by "
            "using invariant prediction.",
            "Gamella, J. L., Heinze-Deml, C. (2020). Active Invariant Causal Prediction.",
        ),
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Use when observations are labelled by policy regimes or shocks and you "
            "need auditable ICP-style orientation constraints for a discovery pipeline."
        ),
        when_not_to_use=(
            "Do not treat the output as a complete DAG unless the certificate assumptions "
            "and environment coverage conditions are externally satisfied."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "Returns a certificate with accepted/rejected invariant sets, estimated "
            "parents per target, environment redundancy diagnostics, a shift-type "
            "assessment, a computational-feasibility certificate, and forced "
            "orientation candidates."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        certificate = build_regime_shift_identification_certificate(
            data=state["data"],
            domain_labels=state["domain_labels"],
            variable_names=state.get("variable_names", params.get("variable_names")),
            target_cols=params.get("target_cols", params.get("targets", state.get("target_cols"))),
            alpha=float(params.get("alpha", 0.05)),
            correction=str(params.get("correction", "bh")),
            max_set_size=int(params.get("max_set_size", 2)),
            model_family=str(params.get("model_family", "auto")),
            screening=(
                str(params.get("screening"))
                if params.get("screening") is not None
                else None
            ),
            dataset_ref=(
                str(params.get("dataset_ref"))
                if params.get("dataset_ref") is not None
                else None
            ),
            context_exogeneity=str(params.get("context_exogeneity", "unverified")),
            baseline_covariates=params.get("baseline_covariates"),
            selection_max_set_size=params.get("selection_max_set_size"),
            shift_type_random_seed=int(params.get("shift_type_random_seed", 0)),
            shift_type_repro_splits=int(params.get("shift_type_repro_splits", 3)),
            super_structure=params.get("super_structure", state.get("super_structure")),
            algebraic_blocks=params.get("algebraic_blocks"),
            prior_algebraic_reports=params.get("prior_algebraic_reports"),
            max_candidate_parents=int(params.get("max_candidate_parents", 10)),
            local_separator_cap=params.get("local_separator_cap", 4),
            exact_component_cap=int(params.get("exact_component_cap", 12)),
            exact_treewidth_cap=int(params.get("exact_treewidth_cap", 8)),
        )
        forced_orientations = certificate.mec_contraction.edge_updates.forced_orientations
        return {
            "result": {
                "regime_shift_identification_certificate": certificate.model_dump(
                    mode="json"
                ),
                "shift_type_assessment": (
                    certificate.shift_type_assessment.model_dump(mode="json")
                    if certificate.shift_type_assessment is not None
                    else None
                ),
                "computational_feasibility": (
                    certificate.computational_feasibility.model_dump(mode="json")
                    if certificate.computational_feasibility is not None
                    else None
                ),
                "forced_orientations": [list(edge) for edge in forced_orientations],
                "estimated_parents_by_target": {
                    target.target: list(target.estimated_parents)
                    for target in certificate.targets
                },
            },
            "__determinism_tier__": DeterminismTier.STATISTICAL,
        }


def build_environment_audit_report(
    *,
    data: Any,
    variable_names: list[str],
    domain_labels: Any,
    target_col: int | str | None = None,
    alpha: float = 0.05,
    correction: str = "bh",
    provenance_refs: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EnvironmentAuditReport:
    """Build environment audit report."""
    warnings: list[str] = []
    audit_metadata = dict(metadata or {})
    normalized_correction = _normalize_correction(correction, warnings)
    audit_metadata.setdefault("correction", normalized_correction)
    audit_metadata.setdefault("alpha", float(alpha))
    provenance = [str(item) for item in (provenance_refs or []) if str(item).strip()]

    if data is None:
        return _environment_audit_report(
            status="skipped",
            warnings=["environment_audit_missing_data", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "missing_data"},
        )
    if domain_labels is None:
        return _environment_audit_report(
            status="skipped",
            warnings=["environment_audit_missing_domain_labels", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "missing_domain_labels"},
        )

    try:
        data_array = np.asarray(data, dtype=float)
    except Exception as exc:  # noqa: BLE001
        return _environment_audit_report(
            status="degraded",
            warnings=[f"environment_audit_invalid_data:{type(exc).__name__}", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "invalid_data", "error": str(exc)},
        )
    if data_array.ndim == 1:
        data_array = data_array[:, None]
    if data_array.ndim != 2:
        return _environment_audit_report(
            status="degraded",
            warnings=["environment_audit_data_must_be_2d", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "data_not_2d"},
        )
    if not np.isfinite(data_array).all():
        return _environment_audit_report(
            status="degraded",
            warnings=["environment_audit_data_contains_non_finite", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "non_finite_data"},
        )

    resolved_variable_names = [str(item).strip() for item in variable_names if str(item).strip()]
    if not resolved_variable_names:
        return _environment_audit_report(
            status="skipped",
            warnings=["environment_audit_missing_variable_names", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "missing_variable_names"},
        )
    if len(resolved_variable_names) != data_array.shape[1]:
        return _environment_audit_report(
            status="degraded",
            warnings=["environment_audit_variable_name_mismatch", *warnings],
            provenance_refs=provenance,
            metadata={
                **audit_metadata,
                "reason": "variable_name_mismatch",
                "n_features": int(data_array.shape[1]),
                "n_variable_names": len(resolved_variable_names),
            },
        )

    labels_array = np.asarray(domain_labels)
    if labels_array.ndim != 1:
        return _environment_audit_report(
            status="degraded",
            warnings=["environment_audit_domain_labels_not_vector", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "domain_labels_not_vector"},
        )
    if labels_array.shape[0] != data_array.shape[0]:
        return _environment_audit_report(
            status="degraded",
            warnings=["environment_audit_domain_label_length_mismatch", *warnings],
            provenance_refs=provenance,
            metadata={
                **audit_metadata,
                "reason": "domain_label_length_mismatch",
                "n_obs": int(data_array.shape[0]),
                "n_labels": int(labels_array.shape[0]),
            },
        )

    unique_domains, counts = np.unique(labels_array, return_counts=True)
    n_environments = int(len(unique_domains))
    audit_metadata.setdefault(
        "variable_names",
        list(resolved_variable_names),
    )
    audit_metadata.setdefault(
        "environment_counts",
        {str(domain): int(count) for domain, count in zip(unique_domains, counts)},
    )
    if n_environments < 2:
        return _environment_audit_report(
            status="skipped",
            n_environments=n_environments,
            warnings=["environment_audit_single_environment", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "single_environment"},
        )
    if any(int(count) < 2 for count in counts):
        return _environment_audit_report(
            status="skipped",
            n_environments=n_environments,
            warnings=["environment_audit_insufficient_samples_per_environment", *warnings],
            provenance_refs=provenance,
            metadata={**audit_metadata, "reason": "insufficient_samples_per_environment"},
        )

    ks_payload = KSInvarianceTest.pure_step(
        {"data": data_array, "domain_labels": labels_array},
        {"alpha": alpha, "correction": normalized_correction},
    )["result"]
    status = "ok"
    if not bool(ks_payload.get("passed", True)):
        status = "warning"
        warnings.append("ks_detected_distribution_shift")

    icp_run = False
    icp_passed: bool | None = None
    invariant_features: list[int] = []
    variant_features: list[int] = []
    icp_p_values: dict[str, float] = {}

    resolved_target_col, target_warning = _resolve_target_col(
        target_col,
        variable_names=resolved_variable_names,
        n_features=data_array.shape[1],
    )
    if target_warning is not None:
        warnings.append(target_warning)
        status = _merge_environment_audit_status(status, "warning")
    elif resolved_target_col is not None:
        if data_array.shape[1] < 2:
            warnings.append("icp_skipped_no_predictor_features")
            status = _merge_environment_audit_status(status, "warning")
        else:
            icp_run = True
            try:
                icp_payload = ICPInvarianceTest.pure_step(
                    {
                        "data": data_array,
                        "domain_labels": labels_array,
                        "target_col": resolved_target_col,
                    },
                    {"alpha": alpha, "correction": normalized_correction},
                )["result"]
                icp_passed = bool(icp_payload.get("passed", True))
                invariant_features = [
                    int(item) for item in icp_payload.get("invariant_features", [])
                ]
                variant_features = [
                    int(item) for item in icp_payload.get("variant_features", [])
                ]
                icp_p_values = {
                    str(key): float(value)
                    for key, value in dict(icp_payload.get("p_values", {})).items()
                }
                audit_metadata["icp_target_col"] = int(resolved_target_col)
                audit_metadata["icp_target_variable"] = resolved_variable_names[resolved_target_col]
                if not icp_passed:
                    warnings.append("icp_detected_feature_heterogeneity")
                    status = _merge_environment_audit_status(status, "warning")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"icp_failed:{type(exc).__name__}")
                audit_metadata["icp_error"] = str(exc)
                status = _merge_environment_audit_status(status, "degraded")
    else:
        audit_metadata["icp_skip_reason"] = "target_not_requested"

    return _environment_audit_report(
        status=status,
        n_environments=n_environments,
        ks_passed=bool(ks_payload.get("passed", True)),
        ks_rejected_variables=[
            int(item) for item in ks_payload.get("rejected_variables", [])
        ],
        ks_p_values={
            str(key): float(value)
            for key, value in dict(ks_payload.get("p_values_matrix", {})).items()
        },
        icp_run=icp_run,
        icp_passed=icp_passed,
        invariant_features=invariant_features,
        variant_features=variant_features,
        icp_p_values=icp_p_values,
        warnings=warnings,
        provenance_refs=provenance,
        metadata=audit_metadata,
    )


def _resolve_target_col(
    target_col: int | str | None,
    *,
    variable_names: list[str],
    n_features: int,
) -> tuple[int | None, str | None]:
    if target_col is None:
        return None, None
    if isinstance(target_col, str):
        name = target_col.strip()
        if not name:
            return None, "icp_invalid_target_col"
        if name in variable_names:
            return variable_names.index(name), None
        try:
            target_col = int(name)
        except Exception:  # noqa: BLE001
            return None, "icp_invalid_target_col"
    try:
        resolved = int(target_col)
    except Exception:  # noqa: BLE001
        return None, "icp_invalid_target_col"
    if not (0 <= resolved < n_features):
        return None, "icp_invalid_target_col"
    return resolved, None


def _normalize_correction(correction: str, warnings: list[str]) -> str:
    normalized = str(correction or "bh").strip().lower()
    if normalized in {"bh", "bonferroni"}:
        return normalized
    warnings.append(f"environment_audit_unknown_correction:{normalized or 'empty'}")
    return "bh"


def _merge_environment_audit_status(
    current: str,
    incoming: str,
) -> str:
    priority = {"ok": 0, "warning": 1, "degraded": 2}
    return incoming if priority[incoming] > priority[current] else current


def _environment_audit_report(
    *,
    status: str,
    n_environments: int = 0,
    ks_passed: bool | None = None,
    ks_rejected_variables: list[int] | None = None,
    ks_p_values: dict[str, float] | None = None,
    icp_run: bool = False,
    icp_passed: bool | None = None,
    invariant_features: list[int] | None = None,
    variant_features: list[int] | None = None,
    icp_p_values: dict[str, float] | None = None,
    warnings: list[str] | None = None,
    provenance_refs: list[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EnvironmentAuditReport:
    return EnvironmentAuditReport(
        status=status,
        n_environments=n_environments,
        ks_passed=ks_passed,
        ks_rejected_variables=list(ks_rejected_variables or []),
        ks_p_values=dict(ks_p_values or {}),
        icp_run=bool(icp_run),
        icp_passed=icp_passed,
        invariant_features=list(invariant_features or []),
        variant_features=list(variant_features or []),
        icp_p_values=dict(icp_p_values or {}),
        warnings=[str(item) for item in (warnings or []) if str(item).strip()],
        provenance_refs=[str(item) for item in (provenance_refs or []) if str(item).strip()],
        metadata=dict(metadata or {}),
    )


__all__ = [
    "ICPInvarianceTest",
    "InvariantDiscoveryFromRegimes",
    "KSInvarianceTest",
    "build_regime_shift_identification_certificate",
    "build_environment_audit_report",
]
