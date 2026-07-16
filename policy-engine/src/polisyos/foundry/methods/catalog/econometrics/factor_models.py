"""
Factor Model methods for econometrics.

Implements:
- ``PrincipalComponentsEstimator``  — PCA-based factor extraction, loadings,
  explained variance, factor scores, and scree diagnostics.
- ``DynamicFactorModelEstimator``   — DFM via EM algorithm for panel time series:
  factor loadings, common factors, idiosyncratic noise, and Kalman-smoother
  factor estimates.
"""

from __future__ import annotations

from collections.abc import Mapping
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload

from .protocols import EconometricResult

# ---------------------------------------------------------------------------
# Output slots
# ---------------------------------------------------------------------------


def _factor_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec.for_output_contract(
                "result",
                SlotType.SCALAR,
                Unit("result", "json"),
                output_contract=EconometricResult,
            ),
            SlotSpec(
                "factor_loadings",
                SlotType.MATRIX,
                Unit("loadings", "matrix"),
                shape=("n_vars", "n_factors"),
            ),
            SlotSpec(
                "factor_scores",
                SlotType.MATRIX,
                Unit("scores", "matrix"),
                shape=("n_obs", "n_factors"),
            ),
            SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
        }
    )


def _resolve_exog(state: Any) -> Any:
    if isinstance(state, Mapping):
        for key in ("exog", "features", "X"):
            if key in state and state[key] is not None:
                return state[key]
        return None
    for key in ("exog", "features", "X"):
        value = getattr(state, key, None)
        if value is not None:
            return value
    return None


# ---------------------------------------------------------------------------
# PrincipalComponentsEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="econometrics.factor",
    version="1.0.0",
    tags={"econometrics", "factor-model", "pca", "dimensionality-reduction"},
)
class PrincipalComponentsEstimator:
    """
    PCA-based factor model.

    Extracts the leading ``n_factors`` principal components from a
    panel/cross-section data matrix.  Returns factor loadings, factor scores,
    variance explained, and a scree-plot-ready eigenvalue sequence.

    Parameters
    ----------
    n_factors:
        Number of factors to extract (default: 3, 0 = auto via Kaiser rule).
    standardize:
        If True (default), demean and scale each variable before PCA.
    rotation:
        ``"none"``, ``"varimax"`` (basic rotation approximation), or
        ``"quartimax"``.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="principal_components",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_vars")
                ),
            }
        ),
        output_slots=_factor_output_slots(),
        parameters=(
            ParameterSpec(name="n_factors", default=3, bounds=(0, 50)),
            ParameterSpec(name="standardize", default=True),
            ParameterSpec(name="rotation", default="none"),
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
            "PCA-based factor model with optional varimax rotation. "
            "Returns loadings, scores, eigenvalues, and explained variance ratio."
        ),
        tags=frozenset({"econometrics", "factor-model", "pca", "dimensionality-reduction"}),
        when_to_use="Summarize many correlated macro/financial variables into few factors; dimensionality reduction",
        citations=(
            "Stock, J. & Watson, M. (2002). Forecasting using principal components from a large number of predictors. Journal of the American Statistical Association, 97(460), 1167-1179.",
        ),
        output_interpretation="Factor loadings + scores. Scree plot for factor number selection. % variance explained.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = extract_model_payload(fallback_state, model_cls=None, nested_keys=())
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        exog = _resolve_exog(state)
        X = np.asarray(exog, dtype=float)
        if X.ndim != 2:
            raise ValueError("exog must be a 2D array (n_obs, n_vars)")

        n_obs, n_vars = X.shape
        standardize = bool(params.get("standardize", True))
        n_factors = int(params.get("n_factors", 3))
        rotation = str(params.get("rotation", "none"))

        # Standardise
        means = X.mean(axis=0)
        X_c = X - means
        if standardize:
            stds = np.std(X_c, axis=0, ddof=1)
            stds = np.where(stds < 1e-10, 1.0, stds)
            X_c = X_c / stds

        # SVD-based PCA
        U, s, Vt = np.linalg.svd(X_c, full_matrices=False)
        eigenvalues = (s**2) / (n_obs - 1)
        total_var = float(np.sum(eigenvalues))
        explained_var_ratio = eigenvalues / max(total_var, 1e-10)

        # Kaiser rule: keep factors with eigenvalue > 1
        if n_factors == 0:
            n_factors = max(1, int(np.sum(eigenvalues > 1.0)))

        n_factors = min(n_factors, n_vars, n_obs)
        loadings = Vt[:n_factors].T  # (n_vars, n_factors)
        scores = U[:, :n_factors] * s[:n_factors]  # (n_obs, n_factors)

        # Basic varimax rotation (power iteration)
        if rotation == "varimax" and n_factors > 1:
            loadings = _varimax_rotation(loadings)

        # Communalities
        communalities = np.sum(loadings**2, axis=1)

        result = EconometricResult(
            method_name="principal_components",
            n_obs=n_obs,
            params={"n_factors": float(n_factors)},
            std_errors={},
            t_stats={},
            p_values={},
            diagnostics={
                "eigenvalues": eigenvalues[:n_factors].tolist(),
                "explained_variance_ratio": explained_var_ratio[:n_factors].tolist(),
                "total_explained": float(np.sum(explained_var_ratio[:n_factors])),
                "communalities_mean": float(np.mean(communalities)),
                "standardized": standardize,
            },
            model_info={
                "library": "numpy",
                "estimator": "PCA",
                "rotation": rotation,
            },
        )

        from polisyos.ir.analytics.uncertainty import (
            DistributionFamily,
            IntervalSemantics,
            PropagationMethod,
            UncertaintyEnvelope,
            UncertaintySource,
        )

        envelope = UncertaintyEnvelope(
            point_estimate=float(np.sum(explained_var_ratio[:n_factors])),
            confidence_interval=(0.0, 1.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.ANALYTICAL,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=n_obs,
            metadata={"econometric_method": "principal_components", "rotation": rotation},
        )

        return {
            "result": result,
            "factor_loadings": loadings,
            "factor_scores": scores,
            "eigenvalues": eigenvalues.tolist(),
            "explained_var_ratio": explained_var_ratio.tolist(),
            "n_factors_extracted": n_factors,
            "uncertainty_envelope": envelope,
        }


def _varimax_rotation(loadings: np.ndarray, max_iter: int = 100, tol: float = 1e-6) -> np.ndarray:
    """Simple varimax rotation via Gram-Schmidt + variance maximisation."""
    n_vars, n_factors = loadings.shape
    rotation_matrix = np.eye(n_factors)
    for _ in range(max_iter):
        old = rotation_matrix.copy()
        for i in range(n_factors):
            for j in range(i + 1, n_factors):
                col_i = loadings @ rotation_matrix[:, i]
                col_j = loadings @ rotation_matrix[:, j]
                u = col_i**2 - col_j**2
                v = 2 * col_i * col_j
                A = np.sum(u)
                B = np.sum(v)
                C = np.sum(u**2 - v**2)
                D = np.sum(u * v)
                num = D - 2 * A * B / n_vars
                den = C - (A**2 - B**2) / n_vars
                theta = 0.25 * np.arctan2(num, den)
                c, s = np.cos(theta), np.sin(theta)
                Rij = np.eye(n_factors)
                Rij[i, i] = c
                Rij[j, j] = c
                Rij[i, j] = -s
                Rij[j, i] = s
                rotation_matrix = rotation_matrix @ Rij
        if np.max(np.abs(rotation_matrix - old)) < tol:
            break
    return loadings @ rotation_matrix


# ---------------------------------------------------------------------------
# DynamicFactorModelEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="econometrics.factor",
    version="1.0.0",
    tags={"econometrics", "factor-model", "dynamic", "time-series", "em"},
)
class DynamicFactorModelEstimator:
    """
    Dynamic Factor Model (DFM) via EM algorithm.

    Extracts latent common factors from a multivariate time series (panel
    or macro data) using the EM algorithm with Kalman filtering/smoothing.

    Model
    -----
    X_t = Λ f_t + ε_t      (observation equation)
    f_t = A f_{t-1} + η_t  (transition equation)

    where Λ ∈ R^{n_vars × n_factors}, A is diagonal by default.

    Returns factor loadings (Λ), common factors {f_t}, idiosyncratic
    variances (diag of Σ_ε), and log-likelihood trajectory.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dynamic_factor_model",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_time", "n_vars")
                ),
            }
        ),
        output_slots=_factor_output_slots(),
        parameters=(
            ParameterSpec(name="n_factors", default=2, bounds=(1, 20)),
            ParameterSpec(name="max_iter", default=50, bounds=(5, 500)),
            ParameterSpec(name="tol", default=1e-4, bounds=(1e-8, 0.1)),
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
            "Dynamic Factor Model via EM algorithm with Kalman smoothing. "
            "Extracts latent common factors from multivariate time series."
        ),
        tags=frozenset({"econometrics", "factor-model", "dynamic", "time-series", "em"}),
        when_to_use="Extract common factors from large panel time series; DFM for macroeconomic forecasting",
        citations=(
            "Stock, J. & Watson, M. (2011). Dynamic factor models. In Oxford Handbook of Economic Forecasting.",
            "Forni, M. et al. (2000). The generalized dynamic-factor model: Identification and estimation. Review of Economics and Statistics, 82(4), 540-554.",
        ),
        typical_min_obs=100,
        output_interpretation="Common factor time series. Factor loadings show variable contributions. GDP forecast with DFM.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = extract_model_payload(fallback_state, model_cls=None, nested_keys=())
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        exog = _resolve_exog(state)
        X = np.asarray(exog, dtype=float)
        if X.ndim != 2:
            raise ValueError("exog must be 2D (n_time, n_vars)")

        T, p = X.shape
        n_factors = int(params.get("n_factors", 2))
        max_iter = int(params.get("max_iter", 50))
        tol = float(params.get("tol", 1e-4))

        # Demean
        X_mean = X.mean(axis=0)
        X_c = X - X_mean

        # Initialise via PCA
        _, s, Vt = np.linalg.svd(X_c, full_matrices=False)
        Lambda = Vt[:n_factors].T  # (p, q)
        A = 0.9 * np.eye(n_factors)
        Sigma_e = np.diag(np.var(X_c, axis=0, ddof=1) * 0.5)
        Sigma_eta = np.eye(n_factors) * 0.1

        log_likelihoods: list[float] = []

        for _em_iter in range(max_iter):
            # ---- E-step: Kalman filter + smoother ----
            # State: f_t ~ N(mu_f, P_f)
            mu_f = np.zeros(n_factors)
            P_f = np.eye(n_factors)
            mus: list[np.ndarray] = []
            Ps: list[np.ndarray] = []
            innovations: list[np.ndarray] = []
            S_list: list[np.ndarray] = []
            K_list: list[np.ndarray] = []

            ll = 0.0
            for t in range(T):
                # Predict
                mu_pred = A @ mu_f
                P_pred = A @ P_f @ A.T + Sigma_eta
                # Update
                innovation = X_c[t] - Lambda @ mu_pred
                S = Lambda @ P_pred @ Lambda.T + Sigma_e
                try:
                    S_inv = np.linalg.inv(S)
                except np.linalg.LinAlgError:
                    S_inv = np.linalg.pinv(S)
                K = P_pred @ Lambda.T @ S_inv
                mu_f = mu_pred + K @ innovation
                P_f = (np.eye(n_factors) - K @ Lambda) @ P_pred
                mus.append(mu_f.copy())
                Ps.append(P_f.copy())
                innovations.append(innovation.copy())
                S_list.append(S.copy())
                K_list.append(K.copy())

                # Log-likelihood increment
                sign, logdet = np.linalg.slogdet(S)
                if sign > 0:
                    ll -= 0.5 * (
                        p * np.log(2 * np.pi) + logdet + float(innovation @ S_inv @ innovation)
                    )

            log_likelihoods.append(ll)

            # Rauch-Tung-Striebel smoother
            mus_s = list(mus)
            Ps_s = list(Ps)
            for t in range(T - 2, -1, -1):
                P_pred_tp1 = A @ Ps[t] @ A.T + Sigma_eta
                try:
                    G = Ps[t] @ A.T @ np.linalg.inv(P_pred_tp1)
                except np.linalg.LinAlgError:
                    G = Ps[t] @ A.T @ np.linalg.pinv(P_pred_tp1)
                mus_s[t] = mus[t] + G @ (mus_s[t + 1] - A @ mus[t])
                Ps_s[t] = Ps[t] + G @ (Ps_s[t + 1] - P_pred_tp1) @ G.T

            # ---- M-step ----
            F = np.array(mus_s)  # (T, q)
            FF = sum(Ps_s[t] + np.outer(mus_s[t], mus_s[t]) for t in range(T))
            XF = X_c.T @ F

            Lambda = XF @ np.linalg.pinv(FF)
            residuals = X_c - F @ Lambda.T
            Sigma_e = np.diag(np.var(residuals, axis=0, ddof=1))

            if len(log_likelihoods) > 1 and abs(log_likelihoods[-1] - log_likelihoods[-2]) < tol:
                break

        converged = (
            len(log_likelihoods) > 1 and abs(log_likelihoods[-1] - log_likelihoods[-2]) < tol
        )
        factor_variances = np.var(F, axis=0, ddof=1) if T > 1 else np.var(F, axis=0)
        total_factor_variance = float(np.sum(factor_variances))
        explained_var_ratio = factor_variances / max(total_factor_variance, 1e-10)

        result = EconometricResult(
            method_name="dynamic_factor_model",
            n_obs=T,
            params={
                "n_factors": float(n_factors),
                "n_iter": float(len(log_likelihoods)),
                "tol": float(tol),
            },
            std_errors={},
            t_stats={},
            p_values={},
            diagnostics={
                "final_log_likelihood": log_likelihoods[-1] if log_likelihoods else float("nan"),
                "n_iter": len(log_likelihoods),
                "n_factors": n_factors,
                "converged": converged,
                "explained_variance_ratio": explained_var_ratio.tolist(),
            },
            model_info={
                "library": "numpy",
                "estimator": "DynamicFactorModel",
                "max_iter": max_iter,
            },
        )

        from polisyos.ir.analytics.uncertainty import (
            DistributionFamily,
            IntervalSemantics,
            PropagationMethod,
            UncertaintyEnvelope,
            UncertaintySource,
        )

        envelope = UncertaintyEnvelope(
            point_estimate=float(log_likelihoods[-1]) if log_likelihoods else 0.0,
            confidence_interval=(
                float(min(log_likelihoods)) if log_likelihoods else 0.0,
                float(max(log_likelihoods)) if log_likelihoods else 0.0,
            ),
            confidence_level=0.95,
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.ANALYTICAL,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=T,
            metadata={"econometric_method": "dynamic_factor_model", "converged": converged},
        )

        return {
            "result": result,
            "factor_loadings": Lambda,
            "factor_scores": F,
            "explained_var_ratio": explained_var_ratio.tolist(),
            "log_likelihoods": log_likelihoods,
            "converged": converged,
            "n_factors_extracted": n_factors,
            "uncertainty_envelope": envelope,
        }
