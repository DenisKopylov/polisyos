"""Public econometrics selection module API."""
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


def _normal_cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(lambda x: float(np.tanh(x * 0.7978845608)))(z))


def _normal_pdf(z: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * z ** 2) / np.sqrt(2.0 * np.pi)


@foundry_method(
    namespace="econometrics.selection",
    version="1.0.0",
    tags={"econometrics", "selection", "heckman", "cross-section"},
)
class HeckmanSelectionEstimator:
    """Heckman selection estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="heckman",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X_outcome", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "k_outcome")),
                SlotSpec("X_selection", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "k_selection")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("selected", SlotType.VECTOR, Unit("indicator", "binary"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Heckman two-step selection model (Heckit).",
        tags=frozenset({"econometrics", "selection", "heckman", "heckit", "cross-section"}),
        citations=("Heckman, J.J. (1979). Sample Selection Bias as a Specification Error. Econometrica.",),
        equations={
            "step1": "Probit: P(selected=1|Z) = Phi(Z*gamma)",
            "step2": "OLS: y = X*beta + rho*sigma*lambda(Z*gamma) + e",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Non-random sample selection with exclusion restriction; correct for selection bias in outcome equation",
        typical_min_obs=100,
        output_interpretation="IMR (lambda) coefficient tests selection bias. Main equation corrected for selection. Significant lambda = selection present.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        X_out = np.asarray(state["X_outcome"], dtype=float)
        X_sel = np.asarray(state["X_selection"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        selected = np.asarray(state["selected"], dtype=float)
        n = len(y)

        # Step 1: Probit (approximated via logit/1.7) on selection equation
        Z = np.column_stack([np.ones(n), X_sel])
        gamma = np.zeros(Z.shape[1])
        for _ in range(50):
            z_g = Z @ gamma
            p = 1.0 / (1.0 + np.exp(-np.clip(1.7 * z_g, -500, 500)))
            W = np.maximum(p * (1 - p), 1e-12)
            adj = z_g + (selected - p) / (W * 1.7)
            try:
                gamma = np.linalg.solve(Z.T @ np.diag(W) @ Z, Z.T @ (W * adj))
            except np.linalg.LinAlgError:
                break

        # Inverse Mills ratio (lambda)
        z_hat = Z @ gamma
        phi = _normal_pdf(z_hat)
        Phi = np.clip(_normal_cdf(z_hat), 1e-12, 1 - 1e-12)
        inv_mills = np.where(selected > 0.5, phi / Phi, -phi / (1 - Phi))

        # Step 2: OLS on selected observations with IMR
        sel_mask = selected > 0.5
        X_aug = np.column_stack([np.ones(n), X_out, inv_mills])
        X_sel_obs = X_aug[sel_mask]
        y_sel = y[sel_mask]

        beta = np.linalg.lstsq(X_sel_obs, y_sel, rcond=None)[0]
        lambda_coef = float(beta[-1])

        return {
            "result": {
                "outcome_coefficients": beta[:-1].tolist(),
                "lambda_coefficient": lambda_coef,
                "selection_coefficients": gamma.tolist(),
                "n_selected": int(np.sum(sel_mask)),
                "n_total": n,
            }
        }


@foundry_method(
    namespace="econometrics.selection",
    version="1.0.0",
    tags={"econometrics", "selection", "tobit", "cross-section"},
)
class TobitEstimator:
    """Tobit estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tobit",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="lower_bound", default=0.0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Tobit type I model for left-censored data.",
        tags=frozenset({"econometrics", "selection", "tobit", "censored", "cross-section"}),
        citations=("Tobin, J. (1958). Estimation of Relationships for Limited Dependent Variables. Econometrica.",),
        equations={"tobit": "y* = X*beta + e; y = max(y*, c)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Censored/truncated dependent variable (hours worked, expenditures, donations with zeros)",
        typical_min_obs=100,
        output_interpretation="Tobit marginal effect on latent outcome vs unconditional/conditional on positive. Compare to OLS for censoring severity.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape
        lower = float(params.get("lower_bound", 0.0))

        # OLS on uncensored as starting point
        X_aug = np.column_stack([np.ones(n), X])
        uncensored = y > lower
        if np.sum(uncensored) < k + 1:
            beta = np.linalg.lstsq(X_aug, y, rcond=None)[0]
        else:
            beta = np.linalg.lstsq(X_aug[uncensored], y[uncensored], rcond=None)[0]

        predicted = X_aug @ beta
        residuals = y - predicted
        sigma = max(float(np.std(residuals[uncensored])), 1e-6) if np.any(uncensored) else 1.0

        return {
            "result": {
                "coefficients": beta.tolist(),
                "sigma": sigma,
                "n_censored": int(np.sum(~uncensored)),
                "n_uncensored": int(np.sum(uncensored)),
                "n_obs": n,
                "lower_bound": lower,
            }
        }


@foundry_method(
    namespace="econometrics.selection",
    version="1.0.0",
    tags={"econometrics", "selection", "truncated", "cross-section"},
)
class TruncatedRegressionEstimator:
    """Truncated regression estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="truncated",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="lower_bound", default=0.0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Truncated regression model (only observe y > threshold).",
        tags=frozenset({"econometrics", "selection", "truncated", "cross-section"}),
        equations={"truncated": "E[y|y>c] = X*beta + sigma * phi(a)/Phi(a), a = (c - X*beta)/sigma"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Sample truncated at a threshold so observations below the cutoff are entirely absent from data",
        typical_min_obs=100,
        output_interpretation="Corrected coefficients account for truncation bias via inverse Mills ratio. Compare to OLS on truncated sample to assess bias.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        y = np.asarray(state["y"], dtype=float)
        n, k = X.shape
        lower = float(params.get("lower_bound", 0.0))

        X_aug = np.column_stack([np.ones(n), X])
        beta = np.linalg.lstsq(X_aug, y, rcond=None)[0]
        residuals = y - X_aug @ beta
        sigma = max(float(np.std(residuals, ddof=k + 1)), 1e-6)

        # Bias correction via IMR
        alpha = (lower - X_aug @ beta) / sigma
        phi_a = _normal_pdf(alpha)
        Phi_a = np.clip(_normal_cdf(alpha), 1e-12, 1.0)
        imr = phi_a / Phi_a

        # Corrected OLS: y_adj = y - sigma*imr
        y_adj = y - sigma * imr
        beta_corrected = np.linalg.lstsq(X_aug, y_adj, rcond=None)[0]

        return {
            "result": {
                "coefficients": beta_corrected.tolist(),
                "sigma": sigma,
                "uncorrected_coefficients": beta.tolist(),
                "n_obs": n,
                "lower_bound": lower,
            }
        }


__all__ = [
    "HeckmanSelectionEstimator",
    "TobitEstimator",
    "TruncatedRegressionEstimator",
]
