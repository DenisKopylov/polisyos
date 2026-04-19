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
from polisyos.ir.analytics.invariance import (
    RegimeShiftCandidateSetPlan,
    RegimeShiftDataSignature,
    RegimeShiftEnvironmentRecord,
    RegimeShiftIdentificationCertificate,
    RegimeShiftInformativeness,
    RegimeShiftInvarianceTesting,
    RegimeShiftMECContraction,
    RegimeShiftMECContractionEdgeUpdates,
    RegimeShiftMECContractionSummary,
    RegimeShiftProducedBy,
    RegimeShiftSetTestResult,
    RegimeShiftStabilityMetrics,
    RegimeShiftTargetResult,
)
from polisyos.ir.analytics.literature import EnvironmentAuditReport

_EPS = 1e-12


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


def _candidate_sets_for_target(
    *,
    n_features: int,
    target_col: int,
    max_set_size: int,
) -> list[tuple[int, ...]]:
    feature_cols = [idx for idx in range(n_features) if idx != target_col]
    bounded_size = min(max_set_size, len(feature_cols))
    candidate_sets: list[tuple[int, ...]] = [()]
    for size in range(1, bounded_size + 1):
        candidate_sets.extend(tuple(combo) for combo in combinations(feature_cols, size))
    return candidate_sets


def _correct_p_values(raw_pvalues: np.ndarray, correction: str, alpha: float) -> np.ndarray:
    if correction == "bh":
        return _bh_correction(raw_pvalues, alpha)
    if correction in {"bonferroni", "holm"}:
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
) -> tuple[tuple[RegimeShiftSetTestResult, ...], tuple[RegimeShiftSetTestResult, ...]]:
    unique_domains = np.unique(domain_labels)
    if len(unique_domains) < 2:
        raise ValueError(
            "InvariantDiscoveryFromRegimes: at least two environments are required"
        )
    raw_pvalues = np.ones(len(candidate_sets), dtype=float)
    diagnostics: list[dict[str, Any]] = []
    for idx, candidate_set in enumerate(candidate_sets):
        f_stat, p_value = _f_test_heterogeneity(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            feature_cols=list(candidate_set),
        )
        raw_pvalues[idx] = p_value
        diagnostics.append(
            {
                "test": "pooled_vs_environment_fixed_effect_f_test",
                "f_statistic": f_stat,
                "raw_p_value": p_value,
            }
        )
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
    alpha: float,
    correction: str,
) -> tuple[dict[str, bool], tuple[str, ...]]:
    parent_changes: dict[str, bool] = {}
    redundant_envs: list[str] = []
    baseline = set(baseline_parents)
    for env in np.unique(domain_labels):
        env_id = str(env)
        mask = domain_labels != env
        if len(np.unique(domain_labels[mask])) < 2:
            parent_changes[env_id] = True
            continue
        accepted, _ = _evaluate_candidate_sets(
            data=data[mask],
            domain_labels=domain_labels[mask],
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            alpha=alpha,
            correction=correction,
        )
        changed = set(_accepted_intersection(accepted)) != baseline
        parent_changes[env_id] = changed
        if not changed:
            redundant_envs.append(env_id)
    return parent_changes, tuple(redundant_envs)


def _build_regime_shift_certificate(
    *,
    data: np.ndarray,
    domain_labels: np.ndarray,
    variable_names: list[str],
    target_cols: list[int],
    alpha: float,
    correction: str,
    max_set_size: int,
    screening: str | None,
    dataset_ref: str | None,
) -> RegimeShiftIdentificationCertificate:
    unique_domains, counts = np.unique(domain_labels, return_counts=True)
    env_ids = [str(env) for env in unique_domains]
    env_counts = {
        str(env): int(count) for env, count in zip(unique_domains, counts, strict=True)
    }
    environments = tuple(
        RegimeShiftEnvironmentRecord(env_id=env_id, regime_id=env_id) for env_id in env_ids
    )

    target_results: list[RegimeShiftTargetResult] = []
    forced_orientations: list[tuple[str, str]] = []
    forbidden_orientations: list[tuple[str, str]] = []
    all_warnings: list[str] = []

    for target_col in target_cols:
        target = variable_names[target_col]
        candidate_sets = _candidate_sets_for_target(
            n_features=data.shape[1],
            target_col=target_col,
            max_set_size=max_set_size,
        )
        accepted, rejected = _evaluate_candidate_sets(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            alpha=alpha,
            correction=correction,
        )
        parents = _accepted_intersection(accepted)
        empty_set_stable = any(len(result.S) == 0 for result in accepted)
        parent_changes, redundant_envs = _leave_one_out_parent_changes(
            data=data,
            domain_labels=domain_labels,
            target_col=target_col,
            candidate_sets=candidate_sets,
            variable_names=variable_names,
            baseline_parents=parents,
            alpha=alpha,
            correction=correction,
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
        all_warnings.extend(warnings)

        candidate_variables = tuple(
            name for idx, name in enumerate(variable_names) if idx != target_col
        )
        target_results.append(
            RegimeShiftTargetResult(
                target=target,
                envs_used=tuple(env_ids),
                candidate_sets_tested=RegimeShiftCandidateSetPlan(
                    enumeration="all_subsets_upto_k",
                    max_set_size=max_set_size,
                    screening=screening,
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
                ),
                warnings=tuple(warnings),
            )
        )

        if accepted and not empty_set_stable:
            for parent in parents:
                forced_orientations.append((parent, target))
                forbidden_orientations.append((target, parent))

    return RegimeShiftIdentificationCertificate(
        produced_by=RegimeShiftProducedBy(
            method="causal.discovery.icp_regime_shifts",
            implementation="linear_subset_icp_f_test",
        ),
        data_signature=RegimeShiftDataSignature(
            dataset_ref=dataset_ref,
            variables=tuple(variable_names),
            sample_sizes_by_env=env_counts,
        ),
        environments=environments,
        invariance_testing=RegimeShiftInvarianceTesting(
            alpha=alpha,
            multiple_testing=correction,
            test_family="f_test_environment_fixed_effect",
            model_class="linear_ols",
            notes=(
                "Phase-1 certificate contract: statistical test is a conservative "
                "linear ICP proxy; nonlinear/general guarantees remain assumption-gated.",
            ),
        ),
        targets=tuple(target_results),
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
        assumptions=(
            "no intervention on target mechanisms",
            "stability-faithfulness for accepted invariant sets",
            "candidate parent search is complete up to max_set_size",
        ),
        warnings=tuple(sorted(set(all_warnings))),
        metadata={"stage": "16.1", "track": "causal_discovery_regime_shifts"},
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
    screening: str | None = None,
    dataset_ref: str | None = None,
) -> RegimeShiftIdentificationCertificate:
    """Build a typed Stage 16.1 certificate from labelled multi-environment data."""
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
    return _build_regime_shift_certificate(
        data=data_array,
        domain_labels=labels_array,
        variable_names=normalized_variable_names,
        target_cols=normalized_target_cols,
        alpha=float(alpha),
        correction=str(correction),
        max_set_size=int(max_set_size),
        screening=screening,
        dataset_ref=dataset_ref,
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
            ParameterSpec(name="target_cols", default=None),
            ParameterSpec(name="variable_names", default=None),
            ParameterSpec(name="screening", default=None),
            ParameterSpec(name="dataset_ref", default=None),
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
            "ICP-style invariant parent-set tests and records MEC contraction deltas."
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
            "parents per target, environment redundancy diagnostics, and forced "
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
        )
        forced_orientations = certificate.mec_contraction.edge_updates.forced_orientations
        return {
            "result": {
                "regime_shift_identification_certificate": certificate.model_dump(
                    mode="json"
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
