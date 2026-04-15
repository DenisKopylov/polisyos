"""Estimate high-dimensional sparse models with post-selection correction."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _soft_threshold(z: float, lam: float) -> float:
    if z > lam:
        return z - lam
    elif z < -lam:
        return z + lam
    return 0.0


def _lasso_cd(X: np.ndarray, y: np.ndarray, lam: float, max_iter: int = 100) -> np.ndarray:
    """Coordinate descent LASSO."""
    n, p = X.shape
    beta = np.zeros(p)
    for _ in range(max_iter):
        beta_old = beta.copy()
        for j in range(p):
            r = y - X @ beta + X[:, j] * beta[j]
            z = float(X[:, j] @ r) / n
            beta[j] = _soft_threshold(z, lam)
        if np.max(np.abs(beta - beta_old)) < 1e-8:
            break
    return beta


@foundry_method(
    namespace="econometrics.high_dimensional",
    version="1.0.0",
    tags={"econometrics", "high-dimensional", "post-lasso", "cross-section"},
)
class PostLASSOEstimator:
    """Estimate coefficients after LASSO variable screening; avoid dense true signals where sparse selection is unstable."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="post_lasso",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="lambda_factor", default=1.0, bounds=(0.01, 100.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Post-LASSO estimator: LASSO for selection, OLS on selected variables.",
        tags=frozenset({"econometrics", "high-dimensional", "post-lasso", "variable-selection", "cross-section"}),
        citations=("Belloni, A. & Chernozhukov, V. (2013). Least Squares After Model Selection. Bernoulli.",),
        equations={"post_lasso": "Step 1: LASSO select S; Step 2: OLS on X_S"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="High-dimensional regression with sparse true model; variable selection + shrinkage",
        typical_min_obs=100,
        output_interpretation="Zero coefficients = excluded variables. Post-LASSO OLS for unbiased estimates of selected variables.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, p = X.shape

        # Standardize
        X_mean = np.mean(X, axis=0)
        X_std = np.std(X, axis=0)
        X_std = np.where(X_std > 0, X_std, 1.0)
        X_s = (X - X_mean) / X_std
        y_mean = float(np.mean(y))
        y_c = y - y_mean

        # BIC-type lambda
        lam_factor = float(params.get("lambda_factor", 1.0))
        sigma_hat = max(float(np.std(y_c)), 1e-6)
        lam = lam_factor * sigma_hat * np.sqrt(2 * np.log(p) / n)

        # Step 1: LASSO
        beta_lasso = _lasso_cd(X_s, y_c, lam)
        selected = np.where(np.abs(beta_lasso) > 1e-10)[0]

        if len(selected) == 0:
            return {
                "result": {
                    "coefficients": np.zeros(p).tolist(),
                    "intercept": y_mean,
                    "selected_indices": [],
                    "n_selected": 0,
                    "lambda": float(lam),
                    "n_obs": n,
                }
            }

        # Step 2: OLS on selected
        X_sel = np.column_stack([np.ones(n), X[:, selected]])
        beta_ols = np.linalg.lstsq(X_sel, y, rcond=None)[0]

        coefficients = np.zeros(p)
        coefficients[selected] = beta_ols[1:]
        intercept = float(beta_ols[0])

        residuals = y - X_sel @ beta_ols
        r_squared = 1.0 - float(np.var(residuals)) / max(float(np.var(y)), 1e-12)

        return {
            "result": {
                "coefficients": coefficients.tolist(),
                "intercept": intercept,
                "selected_indices": selected.tolist(),
                "n_selected": len(selected),
                "r_squared": max(0.0, float(r_squared)),
                "lambda": float(lam),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="econometrics.high_dimensional",
    version="1.0.0",
    tags={"econometrics", "high-dimensional", "post-double-selection", "cross-section"},
)
class PostDoubleSelectionEstimator:
    """Estimate a target effect after double-selection controls; avoid weak nuisance selection or severe multicollinearity."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="post_double_selection",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_controls")),
                SlotSpec("d", SlotType.VECTOR, Unit("treatment", "value"), shape=("n_obs",)),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="lambda_factor", default=1.0, bounds=(0.01, 100.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Post-double-selection LASSO for causal inference in high dimensions.",
        tags=frozenset({"econometrics", "high-dimensional", "post-double-selection", "causal", "cross-section"}),
        citations=("Belloni, A., Chernozhukov, V. & Hansen, C. (2014). Inference on Treatment Effects. REStud.",),
        equations={
            "step1": "LASSO: y ~ X → select S_y",
            "step2": "LASSO: d ~ X → select S_d",
            "step3": "OLS: y ~ d + X_{S_y ∪ S_d}",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Causal inference with high-dimensional controls; double-selection for uniform inference on treatment",
        typical_min_obs=200,
        output_interpretation="Treatment effect robust to high-dimensional confounding. Conservative SE from double-selection.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        d = np.asarray(state["d"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, p = X.shape

        # Standardize X
        X_mean = np.mean(X, axis=0)
        X_std = np.std(X, axis=0)
        X_std = np.where(X_std > 0, X_std, 1.0)
        X_s = (X - X_mean) / X_std

        lam_factor = float(params.get("lambda_factor", 1.0))

        # Step 1: LASSO of y on X
        y_c = y - np.mean(y)
        sigma_y = max(float(np.std(y_c)), 1e-6)
        lam_y = lam_factor * sigma_y * np.sqrt(2 * np.log(p) / n)
        beta_y = _lasso_cd(X_s, y_c, lam_y)
        S_y = set(np.where(np.abs(beta_y) > 1e-10)[0])

        # Step 2: LASSO of d on X
        d_c = d - np.mean(d)
        sigma_d = max(float(np.std(d_c)), 1e-6)
        lam_d = lam_factor * sigma_d * np.sqrt(2 * np.log(p) / n)
        beta_d = _lasso_cd(X_s, d_c, lam_d)
        S_d = set(np.where(np.abs(beta_d) > 1e-10)[0])

        # Step 3: OLS of y on d + union(S_y, S_d)
        union_S = sorted(S_y | S_d)

        if len(union_S) > 0:
            X_sel = np.column_stack([np.ones(n), d, X[:, union_S]])
        else:
            X_sel = np.column_stack([np.ones(n), d])

        beta_ols = np.linalg.lstsq(X_sel, y, rcond=None)[0]
        treatment_effect = float(beta_ols[1])

        # SE for treatment effect
        residuals = y - X_sel @ beta_ols
        sigma2 = float(np.sum(residuals ** 2) / max(n - len(beta_ols), 1))
        try:
            var_beta = sigma2 * np.linalg.inv(X_sel.T @ X_sel)
            se = float(np.sqrt(max(var_beta[1, 1], 0.0)))
        except np.linalg.LinAlgError:
            se = float("inf")

        return {
            "result": {
                "treatment_effect": treatment_effect,
                "standard_error": se,
                "t_statistic": treatment_effect / max(se, 1e-12),
                "selected_controls_y": sorted(S_y),
                "selected_controls_d": sorted(S_d),
                "n_selected_union": len(union_S),
                "n_obs": n,
                "n_controls": p,
            }
        }


__all__ = [
    "PostDoubleSelectionEstimator",
    "PostLASSOEstimator",
]
