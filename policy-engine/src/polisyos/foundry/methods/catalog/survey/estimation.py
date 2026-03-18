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
    namespace="survey.estimation",
    version="1.0.0",
    tags={"survey", "small-area", "fay-herriot"},
)
class FayHerriotEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fay_herriot",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("y_direct", SlotType.VECTOR, Unit("estimate", "value"), shape=("n_areas",)),
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_areas", "n_covariates")),
                SlotSpec("sampling_var", SlotType.VECTOR, Unit("variance", "value"), shape=("n_areas",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=100),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fay-Herriot area-level model for small area estimation via EBLUP.",
        tags=frozenset({"survey", "small-area", "fay-herriot", "eblup"}),
        citations=("Fay, R.E. & Herriot, R.A. (1979). Estimates of Income for Small Places. JASA.",),
        equations={"fay_herriot": "y_i = x_i'*beta + v_i + e_i; v_i ~ N(0, A), e_i ~ N(0, D_i)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Reliable estimates for small domains/areas with insufficient direct sample size; borrow strength",
        typical_min_obs=5,
        output_interpretation="EBLUP = weighted average of direct estimate and regression estimate. MSE smaller than direct. Shrinkage toward model prediction.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y = np.asarray(state["y_direct"], dtype=float)
        X = np.asarray(state["X"], dtype=float)
        D = np.asarray(state["sampling_var"], dtype=float)
        m, p = X.shape
        max_iter = int(params.get("max_iter", 100))

        # Estimate A (model variance) via method of moments
        beta_ols = np.linalg.lstsq(X, y, rcond=None)[0]
        residuals = y - X @ beta_ols
        A_hat = max(0.0, float(np.mean(residuals**2) - np.mean(D)))

        for _ in range(max_iter):
            # Weights
            w = 1.0 / (D + A_hat)
            W = np.diag(w)

            # GLS
            beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)
            resid = y - X @ beta

            # Update A via REML-like iteration
            A_new = max(0.0, float(np.sum(w**2 * (resid**2 - D)) / np.sum(w**2)))
            if abs(A_new - A_hat) < 1e-8:
                A_hat = A_new
                break
            A_hat = A_new

        # EBLUP
        gamma = A_hat / (A_hat + D)
        eblup = gamma * y + (1 - gamma) * (X @ beta)

        # MSE approximation
        g1 = D * A_hat / (D + A_hat)
        mse = g1  # simplified Prasad-Rao MSE

        return {
            "result": {
                "eblup_estimates": eblup.tolist(),
                "beta": beta.tolist(),
                "model_variance_A": A_hat,
                "shrinkage_factors": gamma.tolist(),
                "mse_estimates": mse.tolist(),
                "n_areas": m,
            }
        }


@foundry_method(
    namespace="survey.estimation",
    version="1.0.0",
    tags={"survey", "calibration", "greg"},
)
class CalibrationGREGEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="calibration_greg",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("X", SlotType.MATRIX, Unit("auxiliary", "value"), shape=("n_obs", "n_aux")),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_obs",)),
                SlotSpec("population_totals", SlotType.VECTOR, Unit("total", "value"), shape=("n_aux",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generalized Regression (GREG) calibration estimator for survey totals.",
        tags=frozenset({"survey", "calibration", "greg", "regression-estimator"}),
        citations=("Särndal, C.E. et al. (1992). Model Assisted Survey Sampling. Springer.",),
        equations={"greg": "t_GREG = t_HT(y) + (T_X - t_HT(X))' * B_w"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Estimate population totals/means from complex sample; HT for design-based; GREG for model-assisted",
        output_interpretation="Calibrated estimates with SE. GREG uses auxiliary population totals to improve efficiency vs HT.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y = np.asarray(state["y"], dtype=float)
        X = np.asarray(state["X"], dtype=float)
        w = np.asarray(state["weights"], dtype=float)
        T_X = np.asarray(state["population_totals"], dtype=float)
        n = len(y)

        # HT estimates
        t_HT_y = float(np.sum(w * y))
        t_HT_X = np.sum(w[:, None] * X, axis=0)

        # Weighted regression coefficient
        W = np.diag(w)
        B_w = np.linalg.lstsq(X.T @ W @ X, X.T @ (w * y), rcond=None)[0]

        # GREG total
        t_GREG = t_HT_y + float((T_X - t_HT_X) @ B_w)

        # Calibration weights
        g = 1.0 + (T_X - t_HT_X) @ np.linalg.lstsq(X.T @ W @ X, X.T, rcond=None)[0]
        cal_weights = w * g

        # Residuals for variance
        e = y - X @ B_w
        var_greg = float(np.sum((w * e) ** 2))

        return {
            "result": {
                "greg_total": t_GREG,
                "ht_total": t_HT_y,
                "regression_coefficients": B_w.tolist(),
                "variance_estimate": var_greg,
                "calibration_weights_mean": float(np.mean(cal_weights)),
                "n_obs": n,
            }
        }


__all__ = [
    "CalibrationGREGEstimator",
    "FayHerriotEstimator",
]
