"""independence_tests — conditional independence tests as falsification hints.

Four methods for detecting gross violations of (conditional) independence
in causal identification pipelines:

* **HSICIndependenceTest**: Hilbert-Schmidt Independence Criterion with
  bootstrap permutation null — tests marginal independence X ⊥ Y.
* **KCIConditionalTest**: Kernel Conditional Independence via residualization
  — tests conditional independence X ⊥ Y | Z.
* **CategoricalConditionalIndependenceTest**: G²/χ² conditional independence
  test for categorical variables, optionally stratified by categorical Z.
* **PartialCorrelationTest**: Partial correlation via OLS residuals with
  Fisher z-transform — fast linear CI test.

All methods return a unified dict with test_name, statistic, p_value, passed,
critical_value, and metadata. They are "falsification hints" — a rejection
flags a gross violation, non-rejection does not prove independence. Kernel and
categorical families additionally support DP-aware calibration via
``polisyos.foundry.calibration.dp_ci``.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.calibration.dp_ci import (
    calibrate_discrete_ci,
    calibrate_kernel_ci,
    coerce_dp_context,
    resolve_ci_threshold_policy,
)
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

_EPS = 1e-12


# ---------------------------------------------------------------------------
# Private kernel / stats helpers
# ---------------------------------------------------------------------------


def _median_bandwidth(X: np.ndarray, Y: np.ndarray | None = None) -> float:
    """Median heuristic bandwidth for RBF kernel."""
    if Y is None:
        Z = X
    else:
        Z = np.vstack([X, Y])
    n = Z.shape[0]
    if n > 500:
        rng = np.random.default_rng(0)
        idx = rng.choice(n, size=500, replace=False)
        Z = Z[idx]
    sq_dists: list[float] = []
    for i in range(len(Z)):
        for j in range(i + 1, len(Z)):
            d = float(np.sum((Z[i] - Z[j]) ** 2))
            sq_dists.append(d)
    if not sq_dists:
        return 1.0
    median_sq = float(np.median(sq_dists))
    return math.sqrt(max(median_sq, _EPS))


def _rbf_kernel(X: np.ndarray, bandwidth: float) -> np.ndarray:
    """Compute n×n RBF kernel matrix."""
    n = X.shape[0]
    sq_dists = (
        np.sum(X ** 2, axis=1, keepdims=True)
        + np.sum(X ** 2, axis=1)
        - 2.0 * (X @ X.T)
    )
    sq_dists = np.maximum(sq_dists, 0.0)
    return np.exp(-sq_dists / (2.0 * bandwidth ** 2 + _EPS))


def _centering_matrix(n: int) -> np.ndarray:
    return np.eye(n) - np.ones((n, n)) / n


def _hsic_statistic(Kx: np.ndarray, Ky: np.ndarray) -> float:
    """HSIC = Tr(K_x H K_y H) / n² (biased estimator)."""
    n = Kx.shape[0]
    H = _centering_matrix(n)
    KxH = Kx @ H
    KyH = Ky @ H
    return float(np.trace(KxH @ KyH)) / (n * n)


def _kernel_ridge_residuals(
    X: np.ndarray, Z: np.ndarray, bandwidth: float, ridge: float = 1e-3
) -> np.ndarray:
    """Residuals of kernel ridge regression X ~ Z."""
    Kz = _rbf_kernel(Z, bandwidth)
    n = Kz.shape[0]
    alpha = np.linalg.solve(Kz + ridge * np.eye(n), X)
    X_hat = Kz @ alpha
    return X - X_hat


def _ols_residuals(Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """OLS residuals Y - Z @ beta_hat."""
    n = Z.shape[0]
    Zaug = np.column_stack([np.ones(n), Z])
    try:
        beta, _, _, _ = np.linalg.lstsq(Zaug, Y, rcond=None)
    except np.linalg.LinAlgError:
        return Y - np.mean(Y, axis=0)
    return Y - Zaug @ beta


def _fisher_z(r: float, n: int) -> tuple[float, float]:
    """Fisher z-transform test: returns (z_statistic, p_value) two-sided."""
    r_clipped = min(max(r, -1.0 + _EPS), 1.0 - _EPS)
    z = 0.5 * math.log((1.0 + r_clipped) / (1.0 - r_clipped))
    se = 1.0 / math.sqrt(max(n - 3, 1))
    z_stat = z / se
    # two-sided p-value via normal approximation
    from math import erfc, sqrt
    p = float(erfc(abs(z_stat) / sqrt(2.0)))
    return float(z_stat), min(p, 1.0)


def _bootstrap_hsic_null(
    Kx: np.ndarray,
    Ky: np.ndarray,
    n_bootstrap: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Bootstrap null distribution of HSIC by permuting Y rows."""
    null_stats: list[float] = []
    n = Kx.shape[0]
    for _ in range(n_bootstrap):
        perm = rng.permutation(n)
        Ky_perm = Ky[perm][:, perm]
        null_stats.append(_hsic_statistic(Kx, Ky_perm))
    return np.array(null_stats, dtype=float)


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return not math.isfinite(float(value))
    return False


def _complete_case_mask_generic(columns: list[np.ndarray]) -> np.ndarray:
    if not columns:
        raise ValueError("at least one column is required")
    mask = np.ones(len(columns[0]), dtype=bool)
    for column in columns:
        arr = np.asarray(column, dtype=object).reshape(-1)
        if len(arr) != len(mask):
            raise ValueError("all columns must have the same length")
        mask &= np.array([not _is_missing_value(item) for item in arr], dtype=bool)
    return mask


def _build_contingency_table(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x_labels, x_codes = np.unique(np.asarray(x, dtype=object).astype(str), return_inverse=True)
    y_labels, y_codes = np.unique(np.asarray(y, dtype=object).astype(str), return_inverse=True)
    table = np.zeros((len(x_labels), len(y_labels)), dtype=float)
    np.add.at(table, (x_codes, y_codes), 1.0)
    return table


def _categorical_tables(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None = None,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    if z is None:
        return [_build_contingency_table(x, y)], {"valid_strata": 1, "skipped_strata": 0}

    z_arr = np.asarray(z, dtype=object)
    if z_arr.ndim == 1:
        z_arr = z_arr[:, None]

    strata: dict[tuple[str, ...], list[int]] = {}
    for idx, row in enumerate(z_arr):
        strata.setdefault(tuple(np.asarray(row, dtype=object).astype(str).tolist()), []).append(idx)

    tables: list[np.ndarray] = []
    skipped = 0
    for indices in strata.values():
        table = _build_contingency_table(x[indices], y[indices])
        if table.shape[0] < 2 or table.shape[1] < 2:
            skipped += 1
            continue
        tables.append(table)
    return tables, {"valid_strata": len(tables), "skipped_strata": skipped}


def _result_payload(
    *,
    test_name: str,
    observed: float,
    calibration: Any,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    passed = bool(float(observed) <= float(calibration.critical_statistic_value))
    payload_metadata = dict(metadata)
    payload_metadata.update(dict(calibration.null_summary))
    if calibration.sample_size_requirement is not None:
        payload_metadata["sample_size_requirement"] = calibration.sample_size_requirement.model_dump(
            mode="json"
        )
    if calibration.threshold_policy.threshold_scope:
        payload_metadata["threshold_registry_scope"] = dict(calibration.threshold_policy.threshold_scope)
    if calibration.threshold_policy.threshold_registry_version is not None:
        payload_metadata["threshold_registry_version"] = calibration.threshold_policy.threshold_registry_version
    return {
        "result": {
            "test_name": test_name,
            "statistic": float(observed),
            "p_value": float(calibration.p_value),
            "passed": passed,
            "critical_value": float(calibration.alpha),
            "alpha": float(calibration.alpha),
            "critical_statistic_value": float(calibration.critical_statistic_value),
            "calibration_mode": calibration.calibration_mode,
            "dp_context_summary": calibration.dp_context_summary,
            "naive_fpr_inflation_bound": (
                None
                if calibration.naive_fpr_inflation_bound is None
                else calibration.naive_fpr_inflation_bound.model_dump(mode="json")
            ),
            "metadata": payload_metadata,
        }
    }


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.diagnostics.independence",
    version="1.0.0",
    tags={"causal", "diagnostics", "independence", "hsic", "kernel", "cross-section"},
)
class HSICIndependenceTest:
    """Hilbert-Schmidt Independence Criterion (HSIC) test for X ⊥ Y.

    Uses RBF kernels and a bootstrap permutation null distribution.
    H₀: X and Y are independent.  Rejection indicates dependence.

    Suitable as a falsification hint: if the test rejects, the assumed
    independence constraint is likely violated.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hsic",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "p")),
                SlotSpec("Y", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "q")),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(name="kernel", default="rbf"),
            ParameterSpec(name="n_bootstrap", default=200),
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="bandwidth", default="median"),
            ParameterSpec(name="dp_context", default=None),
            ParameterSpec(name="judge_threshold_registry_root", default=None),
            ParameterSpec(name="readiness_target", default="diagnostic"),
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
            "HSIC test for marginal independence X ⊥ Y using RBF kernels "
            "and bootstrap permutation null."
        ),
        tags=frozenset({"causal", "diagnostics", "independence", "hsic", "kernel", "falsification"}),
        citations=(
            "Gretton, A. et al. (2005). Measuring statistical dependence with Hilbert-Schmidt norms.",
            "Gretton, A. et al. (2008). A kernel statistical test of independence.",
        ),
        equations={
            "hsic": "HSIC(X,Y) = Tr(K_X H K_Y H) / n²",
            "centering": "H = I_n - (1/n) 1 1ᵀ",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Check whether an assumed conditional independence holds as a falsification hint. "
            "Use before running identification algorithms that rely on specific independence constraints."
        ),
        when_not_to_use=(
            "Not a confirmatory test — non-rejection does not prove independence. "
            "For large n (>5000) prefer approximate or linear tests."
        ),
        typical_min_obs=30,
        output_interpretation=(
            "passed=True: independence NOT rejected at alpha level (consistent with H₀). "
            "passed=False: gross dependence detected — assumed independence constraint violated."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        Y = np.asarray(state["Y"], dtype=float)

        if X.ndim == 1:
            X = X[:, None]
        if Y.ndim == 1:
            Y = Y[:, None]

        n = X.shape[0]
        if n != Y.shape[0]:
            raise ValueError("HSICIndependenceTest: X and Y must have the same number of rows")

        requested_bootstrap = int(params.get("n_bootstrap", 200))
        requested_alpha = float(params.get("alpha", 0.05))
        dp_context = coerce_dp_context(params.get("dp_context"))
        threshold_policy = resolve_ci_threshold_policy(
            family="kernel_ci",
            query_type="hsic",
            estimator="permutation",
            dp_context=dp_context,
            registry_root=params.get("judge_threshold_registry_root"),
            alpha=requested_alpha,
            n_bootstrap=requested_bootstrap,
            readiness_target=str(params.get("readiness_target", "diagnostic")),
        )
        n_bootstrap = int(threshold_policy.mc_bootstrap_B)
        alpha = float(threshold_policy.alpha_base)
        bandwidth_param = params.get("bandwidth", "median")

        if bandwidth_param == "median":
            bw_x = _median_bandwidth(X)
            bw_y = _median_bandwidth(Y)
        else:
            bw_x = bw_y = float(bandwidth_param)

        Kx = _rbf_kernel(X, bw_x)
        Ky = _rbf_kernel(Y, bw_y)

        observed = _hsic_statistic(Kx, Ky)

        rng = np.random.default_rng(0)
        null_dist = _bootstrap_hsic_null(Kx, Ky, n_bootstrap=n_bootstrap, rng=rng)
        calibration = calibrate_kernel_ci(
            observed=float(observed),
            null_distribution=null_dist,
            n_obs=n,
            alpha=alpha,
            dp_context=dp_context,
            threshold_policy=threshold_policy,
            dims=max(X.shape[1] + Y.shape[1], 1),
        )

        return _result_payload(
            test_name="hsic",
            observed=float(observed),
            calibration=calibration,
            metadata={
                "n_obs": n,
                "n_bootstrap": n_bootstrap,
                "bandwidth_x": bw_x,
                "bandwidth_y": bw_y,
            },
        )


@foundry_method(
    namespace="causal.diagnostics.independence",
    version="1.0.0",
    tags={"causal", "diagnostics", "independence", "kci", "conditional", "kernel", "cross-section"},
)
class KCIConditionalTest:
    """Kernel Conditional Independence (KCI) test for X ⊥ Y | Z.

    Approximates the KCI test via residualization: fit kernel ridge regressions
    X~Z and Y~Z, then run HSIC on the residuals.  Rejection indicates that X
    and Y remain dependent even after conditioning on Z.

    This is a practical approximation of the full KCI (Zhang et al. 2012).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="kci",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "p")),
                SlotSpec("Y", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "q")),
                SlotSpec("Z", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "r")),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(name="kernel", default="rbf"),
            ParameterSpec(name="n_bootstrap", default=200),
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="ridge", default=1e-3),
            ParameterSpec(name="dp_context", default=None),
            ParameterSpec(name="judge_threshold_registry_root", default=None),
            ParameterSpec(name="readiness_target", default="diagnostic"),
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
            "Kernel Conditional Independence test X ⊥ Y | Z via residualization + HSIC. "
            "Flags gross violations of assumed conditional independence."
        ),
        tags=frozenset(
            {
                "causal",
                "diagnostics",
                "independence",
                "conditional",
                "kci",
                "kernel",
                "falsification",
            }
        ),
        citations=(
            "Zhang, K. et al. (2012). Kernel-based conditional independence test and application "
            "in causal discovery.",
        ),
        equations={
            "residuals_x": "R_X = X - K_Z(K_Z + λI)⁻¹ X",
            "residuals_y": "R_Y = Y - K_Z(K_Z + λI)⁻¹ Y",
            "kci_approx": "HSIC(R_X, R_Y)",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Verify whether an assumed conditional independence X ⊥ Y | Z holds in data. "
            "Useful for d-separation falsification and Markov condition checks."
        ),
        when_not_to_use=(
            "Not confirmatory. For very large datasets prefer linear partial correlation. "
            "Ridge parameter may need tuning for small samples."
        ),
        typical_min_obs=50,
        output_interpretation=(
            "passed=True: conditional independence NOT rejected — consistent with X ⊥ Y | Z. "
            "passed=False: conditional dependence detected — assumed d-separation violated."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        Y = np.asarray(state["Y"], dtype=float)
        Z = np.asarray(state["Z"], dtype=float)

        if X.ndim == 1:
            X = X[:, None]
        if Y.ndim == 1:
            Y = Y[:, None]
        if Z.ndim == 1:
            Z = Z[:, None]

        n = X.shape[0]
        if not (Y.shape[0] == n and Z.shape[0] == n):
            raise ValueError("KCIConditionalTest: X, Y, Z must have the same number of rows")

        requested_bootstrap = int(params.get("n_bootstrap", 200))
        requested_alpha = float(params.get("alpha", 0.05))
        dp_context = coerce_dp_context(params.get("dp_context"))
        threshold_policy = resolve_ci_threshold_policy(
            family="kernel_ci",
            query_type="kci",
            estimator="residualized_hsic",
            dp_context=dp_context,
            registry_root=params.get("judge_threshold_registry_root"),
            alpha=requested_alpha,
            n_bootstrap=requested_bootstrap,
            readiness_target=str(params.get("readiness_target", "diagnostic")),
        )
        n_bootstrap = int(threshold_policy.mc_bootstrap_B)
        alpha = float(threshold_policy.alpha_base)
        ridge: float = float(params.get("ridge", 1e-3))

        bw_z = _median_bandwidth(Z)
        bw_res = _median_bandwidth(X, Y)

        # Residualize X and Y on Z via kernel ridge
        Rx = _kernel_ridge_residuals(X, Z, bandwidth=bw_z, ridge=ridge)
        Ry = _kernel_ridge_residuals(Y, Z, bandwidth=bw_z, ridge=ridge)

        Kx = _rbf_kernel(Rx, bw_res)
        Ky = _rbf_kernel(Ry, bw_res)

        observed = _hsic_statistic(Kx, Ky)
        rng = np.random.default_rng(0)
        null_dist = _bootstrap_hsic_null(Kx, Ky, n_bootstrap=n_bootstrap, rng=rng)
        calibration = calibrate_kernel_ci(
            observed=float(observed),
            null_distribution=null_dist,
            n_obs=n,
            alpha=alpha,
            dp_context=dp_context,
            threshold_policy=threshold_policy,
            dims=max(X.shape[1] + Y.shape[1] + Z.shape[1], 1),
        )

        return _result_payload(
            test_name="kci",
            observed=float(observed),
            calibration=calibration,
            metadata={
                "n_obs": n,
                "n_bootstrap": n_bootstrap,
                "bandwidth_z": bw_z,
                "bandwidth_residuals": bw_res,
                "ridge": ridge,
            },
        )


@foundry_method(
    namespace="causal.diagnostics.independence",
    version="1.0.0",
    tags={
        "causal",
        "diagnostics",
        "independence",
        "categorical",
        "g-test",
        "chi-square",
        "cross-section",
    },
)
class CategoricalConditionalIndependenceTest:
    """Categorical CI test using G² or Pearson χ² with optional DP calibration."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="categorical_ci",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.VECTOR, Unit("covariate", "category"), shape=("n_obs",)),
                SlotSpec("Y", SlotType.VECTOR, Unit("covariate", "category"), shape=("n_obs",)),
                SlotSpec("Z", SlotType.MATRIX, Unit("covariate", "category"), shape=("n_obs", "r")),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="statistic_family", default="g2"),
            ParameterSpec(name="n_bootstrap", default=2000),
            ParameterSpec(name="dp_context", default=None),
            ParameterSpec(name="judge_threshold_registry_root", default=None),
            ParameterSpec(name="readiness_target", default="diagnostic"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Categorical CI test using stratified G² or Pearson χ² statistics, "
            "with DP-aware threshold correction for privatized count releases."
        ),
        tags=frozenset(
            {
                "causal",
                "diagnostics",
                "independence",
                "categorical",
                "g-test",
                "chi-square",
                "falsification",
            }
        ),
        citations=(
            "Dwork, C. and Roth, A. (2014). The Algorithmic Foundations of Differential Privacy.",
            "Gaboardi, M. et al. (2016). Differentially private chi-squared hypothesis testing.",
        ),
        equations={
            "g2": "G² = 2 Σ O_ij log(O_ij / E_ij)",
            "chi2": "χ² = Σ (O_ij - E_ij)² / E_ij",
            "conditional": "T(X,Y|Z) = Σ_z T(X,Y ; Z=z)",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy", "scipy"),
        when_to_use=(
            "Check categorical independence or conditional independence, including "
            "DP-noised contingency-table releases."
        ),
        when_not_to_use=(
            "Not suitable for continuous variables. Use HSIC/KCI or partial correlation "
            "for continuous settings."
        ),
        typical_min_obs=30,
        output_interpretation=(
            "passed=True means the categorical CI constraint is not rejected at the calibrated alpha. "
            "passed=False flags a categorical dependence incompatible with the assumed graph."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=object).reshape(-1)
        Y = np.asarray(state["Y"], dtype=object).reshape(-1)
        Z_raw = state.get("Z")

        if len(X) != len(Y):
            raise ValueError(
                "CategoricalConditionalIndependenceTest: X and Y must have the same length"
            )

        requested_alpha = float(params.get("alpha", 0.05))
        requested_bootstrap = int(params.get("n_bootstrap", 2000))
        statistic_family = str(params.get("statistic_family", "g2")).strip().lower()
        if statistic_family not in {"g2", "chi2"}:
            raise ValueError("statistic_family must be either 'g2' or 'chi2'")

        z_arr: np.ndarray | None
        columns = [X, Y]
        if Z_raw is None:
            z_arr = None
        else:
            z_arr = np.asarray(Z_raw, dtype=object)
            if z_arr.ndim == 1:
                z_arr = z_arr[:, None]
            if z_arr.shape[0] != len(X):
                raise ValueError(
                    "CategoricalConditionalIndependenceTest: Z must have the same number of rows as X/Y"
                )
            columns.extend(z_arr[:, idx] for idx in range(z_arr.shape[1]))

        mask = _complete_case_mask_generic(columns)
        x_obs = X[mask]
        y_obs = Y[mask]
        z_obs = None if z_arr is None else z_arr[mask]
        dp_context = coerce_dp_context(params.get("dp_context"))
        threshold_policy = resolve_ci_threshold_policy(
            family="categorical_ci",
            query_type=statistic_family,
            estimator="stratified_counts",
            dp_context=dp_context,
            registry_root=params.get("judge_threshold_registry_root"),
            alpha=requested_alpha,
            n_bootstrap=requested_bootstrap,
            readiness_target=str(params.get("readiness_target", "diagnostic")),
        )
        tables, table_meta = _categorical_tables(x_obs, y_obs, z_obs)
        observed, observed_meta, calibration = calibrate_discrete_ci(
            tables=tables,
            alpha=float(threshold_policy.alpha_base),
            statistic_family=statistic_family,  # type: ignore[arg-type]
            dp_context=dp_context,
            threshold_policy=threshold_policy,
        )

        return _result_payload(
            test_name="categorical_ci",
            observed=float(observed),
            calibration=calibration,
            metadata={
                "n_obs": int(mask.sum()),
                "statistic_family": statistic_family,
                **table_meta,
                **observed_meta,
            },
        )


@foundry_method(
    namespace="causal.diagnostics.independence",
    version="1.0.0",
    tags={"causal", "diagnostics", "independence", "partial-correlation", "linear", "cross-section"},
)
class PartialCorrelationTest:
    """Partial correlation test for X ⊥ Y | Z using Fisher z-transform.

    Computes OLS residuals X~Z and Y~Z, then tests whether their correlation
    is significantly different from zero via Fisher z-transform.

    Fast and interpretable, but only detects linear conditional dependence.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="partial_correlation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.VECTOR, Unit("covariate", "value"), shape=("n_obs",)),
                SlotSpec("Y", SlotType.VECTOR, Unit("covariate", "value"), shape=("n_obs",)),
                SlotSpec("Z", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "r")),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="dp_context", default=None),
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
            "Partial correlation test X ⊥ Y | Z via OLS residualization and Fisher z-transform. "
            "Fast linear falsification hint for conditional independence."
        ),
        tags=frozenset(
            {"causal", "diagnostics", "independence", "partial-correlation", "linear", "falsification"}
        ),
        citations=(
            "Fisher, R.A. (1924). The distribution of the partial correlation coefficient.",
        ),
        equations={
            "partial_corr": "r(X,Y|Z) = corr(X - Ẑ_X, Y - Ẑ_Y)",
            "fisher_z": "z = 0.5 · ln((1+r)/(1-r)), SE = 1/√(n-3)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Quick linear CI check before running discovery or identification algorithms. "
            "Cheap to run, good first-pass falsification."
        ),
        when_not_to_use="Does not detect nonlinear dependence. Use KCI for nonlinear cases.",
        typical_min_obs=10,
        output_interpretation=(
            "passed=True: partial correlation not significantly different from 0 — "
            "consistent with linear conditional independence. "
            "partial_corr field gives the raw correlation value."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float).ravel()
        Y = np.asarray(state["Y"], dtype=float).ravel()
        Z_raw = state.get("Z")
        dp_context = coerce_dp_context(params.get("dp_context"))

        n = len(X)
        if len(Y) != n:
            raise ValueError("PartialCorrelationTest: X and Y must have the same length")

        alpha: float = float(params.get("alpha", 0.05))

        if Z_raw is not None:
            Z = np.asarray(Z_raw, dtype=float)
            if Z.ndim == 1:
                Z = Z[:, None]
            if Z.shape[0] != n:
                raise ValueError("PartialCorrelationTest: Z must have n rows")
            Rx = _ols_residuals(X[:, None], Z).ravel()
            Ry = _ols_residuals(Y[:, None], Z).ravel()
        else:
            Rx = X - float(np.mean(X))
            Ry = Y - float(np.mean(Y))

        std_x = float(np.std(Rx))
        std_y = float(np.std(Ry))
        if std_x < _EPS or std_y < _EPS:
            return {
                "result": {
                    "test_name": "partial_correlation",
                    "statistic": 0.0,
                    "p_value": 1.0,
                    "passed": True,
                    "critical_value": alpha,
                    "metadata": {
                        "n_obs": n,
                        "partial_corr": 0.0,
                        "note": "zero variance",
                        **(
                            {}
                            if dp_context is None
                            else {
                                "dp_calibration_supported": False,
                                "dp_warning": "partial_correlation_has_no_dp_specific_calibration",
                            }
                        ),
                    },
                }
            }

        partial_corr = float(np.corrcoef(Rx, Ry)[0, 1])
        z_stat, p_value = _fisher_z(partial_corr, n)
        passed = bool(p_value >= alpha)

        return {
            "result": {
                "test_name": "partial_correlation",
                "statistic": z_stat,
                "p_value": p_value,
                "passed": passed,
                "critical_value": alpha,
                "metadata": {
                    "n_obs": n,
                    "partial_corr": partial_corr,
                    "has_conditioning_set": Z_raw is not None,
                    **(
                        {}
                        if dp_context is None
                        else {
                            "dp_calibration_supported": False,
                            "dp_warning": "partial_correlation_has_no_dp_specific_calibration",
                        }
                    ),
                },
            }
        }


__all__ = [
    "CategoricalConditionalIndependenceTest",
    "HSICIndependenceTest",
    "KCIConditionalTest",
    "PartialCorrelationTest",
]
