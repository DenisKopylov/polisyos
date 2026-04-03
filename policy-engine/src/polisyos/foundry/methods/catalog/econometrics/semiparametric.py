"""Estimate partially linear and kernel semiparametric regressions."""
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


@foundry_method(
    namespace="econometrics.semiparametric",
    version="1.0.0",
    tags={"econometrics", "semiparametric", "robinson", "cross-section"},
)
class RobinsonEstimator:
    """Estimate a partially linear effect after nonparametric residualization; avoid small samples with high-dimensional smoothers."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="robinson",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("z", SlotType.VECTOR, Unit("nonpar", "value"), shape=("n_obs",)),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="bandwidth", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Robinson (1988) partially linear model: y = X*beta + g(z) + e.",
        tags=frozenset({"econometrics", "semiparametric", "robinson", "partially-linear", "cross-section"}),
        citations=("Robinson, P.M. (1988). Root-N-Consistent Semiparametric Regression. Econometrica.",),
        equations={"robinson": "y - E[y|z] = (X - E[X|z]) * beta + e"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Estimate linear parametric component while flexibly controlling for nonlinear nuisance functions",
        typical_min_obs=200,
        output_interpretation="θ: parametric coefficient of interest, consistent and √n-normal. Nonparametric part estimated but not reported as point.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        z = np.asarray(state["z"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape

        # Bandwidth
        bw = params.get("bandwidth")
        if bw is None:
            std_z = max(float(np.std(z)), 1e-6)
            bw = 1.06 * std_z * n ** (-0.2)
        bw = max(float(bw), 1e-8)

        # Kernel regression: E[y|z] and E[X|z] via Gaussian kernel
        diffs = z[:, None] - z[None, :]  # (n, n)
        K = np.exp(-0.5 * (diffs / bw) ** 2)
        K_sum = np.sum(K, axis=1, keepdims=True)
        K_sum = np.maximum(K_sum, 1e-12)
        W = K / K_sum  # (n, n) row-normalized weights

        E_y_z = W @ y
        E_X_z = W @ X

        # Robinson estimator
        y_tilde = y - E_y_z
        X_tilde = X - E_X_z

        beta = np.linalg.lstsq(X_tilde, y_tilde, rcond=None)[0]

        # Nonparametric component
        g_hat = E_y_z - E_X_z @ beta

        residuals = y - X @ beta - g_hat
        r_squared = 1.0 - float(np.var(residuals)) / max(float(np.var(y)), 1e-12)

        return {
            "result": {
                "coefficients": beta.tolist(),
                "r_squared": max(0.0, float(r_squared)),
                "bandwidth": float(bw),
                "n_obs": n,
                "n_features": k,
            }
        }


@foundry_method(
    namespace="econometrics.semiparametric",
    version="1.0.0",
    tags={"econometrics", "semiparametric", "kernel-regression", "cross-section"},
)
class KernelRegressionEstimator:
    """Estimate a nonparametric regression surface with kernel smoothing; avoid high-dimensional covariates or weak bandwidth support."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="kernel_regression",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("x", SlotType.VECTOR, Unit("covariate", "value"), shape=("n_obs",)),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="bandwidth", default=None),
            ParameterSpec(name="n_eval_points", default=100),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Nadaraya-Watson kernel regression estimator.",
        tags=frozenset({"econometrics", "semiparametric", "kernel-regression", "nonparametric", "cross-section"}),
        citations=("Nadaraya, E.A. (1964). On Estimating Regression. Theory of Probability.",),
        equations={"nw": "m(x) = sum K((x-x_i)/h)*y_i / sum K((x-x_i)/h)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Single-index restriction when functional form is unknown; dimension reduction; nonparametric mean regression on one covariate",
        typical_min_obs=300,
        output_interpretation="Fitted curve m(x) at evaluation points. Bandwidth h controls smoothness. LOO-CV score for bandwidth selection.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        x = np.asarray(state["x"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n = len(x)

        bw = params.get("bandwidth")
        if bw is None:
            std_x = max(float(np.std(x)), 1e-6)
            bw = 1.06 * std_x * n ** (-0.2)
        bw = max(float(bw), 1e-8)
        n_eval = int(params.get("n_eval_points", 100))

        eval_pts = np.linspace(float(np.min(x)), float(np.max(x)), n_eval)
        fitted = np.zeros(n_eval)
        for i, pt in enumerate(eval_pts):
            K = np.exp(-0.5 * ((x - pt) / bw) ** 2)
            k_sum = float(np.sum(K))
            fitted[i] = float(np.sum(K * y) / max(k_sum, 1e-12))

        # Leave-one-out CV score
        loo_residuals = np.zeros(n)
        for i in range(n):
            K = np.exp(-0.5 * ((x - x[i]) / bw) ** 2)
            K[i] = 0.0
            k_sum = float(np.sum(K))
            pred = float(np.sum(K * y) / max(k_sum, 1e-12))
            loo_residuals[i] = y[i] - pred
        cv_score = float(np.mean(loo_residuals ** 2))

        return {
            "result": {
                "eval_points": eval_pts.tolist(),
                "fitted_values": fitted.tolist(),
                "bandwidth": float(bw),
                "cv_score": cv_score,
                "n_obs": n,
            }
        }


__all__ = [
    "KernelRegressionEstimator",
    "RobinsonEstimator",
]
