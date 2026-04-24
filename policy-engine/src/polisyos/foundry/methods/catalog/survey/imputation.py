"""Public survey imputation module API."""

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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="survey.imputation",
    version="1.0.0",
    tags={"survey", "imputation", "mice"},
)
class MICEEstimator:
    """Impute missing survey fields with chained-equation multiple imputation."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mice",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("data", "value"), shape=("n_obs", "n_vars")),
                SlotSpec(
                    "missing_mask", SlotType.MATRIX, Unit("mask", "bool"), shape=("n_obs", "n_vars")
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_imputations", default=5),
            ParameterSpec(name="n_cycles", default=10),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Multiple Imputation by Chained Equations (MICE) via predictive mean matching.",
        tags=frozenset(
            {"survey", "imputation", "mice", "multiple-imputation", "chained-equations"}
        ),
        citations=(
            "van Buuren, S. & Groothuis-Oudshoorn, K. (2011). mice: Multivariate Imputation. JSS.",
        ),
        equations={
            "mice": "For each variable j with missing: impute via regression on other variables, cycle"
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="Handle missing values in survey data via imputation; maintain sample size and distributional properties",
        typical_min_obs=50,
        output_interpretation="Imputed dataset(s). Check imputation plausibility. For MI: pool estimates using Rubin's rules.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        mask = np.asarray(state["missing_mask"], dtype=bool)
        n, p = X.shape
        n_imp = int(params.get("n_imputations", 5))
        n_cycles = int(params.get("n_cycles", 10))
        seed = int(params.get("seed", 42))

        rng = np.random.RandomState(seed)

        # Initialize missing values with column means
        col_means = np.nanmean(np.where(mask, np.nan, X), axis=0)
        col_means = np.nan_to_num(col_means, nan=0.0)

        imputed_datasets = []

        for imp in range(n_imp):
            X_imp = X.copy()
            for j in range(p):
                miss_j = mask[:, j]
                if not np.any(miss_j):
                    continue
                X_imp[miss_j, j] = col_means[j]

            for _cycle in range(n_cycles):
                for j in range(p):
                    miss_j = mask[:, j]
                    if not np.any(miss_j):
                        continue
                    obs_j = ~miss_j
                    other_cols = [c for c in range(p) if c != j]
                    if not other_cols:
                        continue

                    X_pred = X_imp[:, other_cols]
                    X_obs = np.column_stack([np.ones(int(np.sum(obs_j))), X_pred[obs_j]])
                    y_obs = X_imp[obs_j, j]

                    try:
                        beta = np.linalg.lstsq(X_obs, y_obs, rcond=None)[0]
                    except np.linalg.LinAlgError:
                        continue

                    X_miss = np.column_stack([np.ones(int(np.sum(miss_j))), X_pred[miss_j]])
                    y_pred = X_miss @ beta

                    # Add noise
                    resid = y_obs - X_obs @ beta
                    sigma = max(float(np.std(resid)), 1e-6)
                    noise = rng.normal(0, sigma, size=len(y_pred))
                    X_imp[miss_j, j] = y_pred + noise

            imputed_datasets.append(X_imp.tolist())

        # Rubin's combining rules for means
        means_list = [np.mean(np.array(d), axis=0) for d in imputed_datasets]
        pooled_mean = np.mean(means_list, axis=0)

        # Between-imputation variance
        between_var = np.var(means_list, axis=0, ddof=1) if n_imp > 1 else np.zeros(p)

        return {
            "result": {
                "pooled_means": pooled_mean.tolist(),
                "between_imputation_variance": between_var.tolist(),
                "n_imputations": n_imp,
                "n_missing_per_var": np.sum(mask, axis=0).tolist(),
                "n_obs": n,
                "n_vars": p,
            }
        }


@foundry_method(
    namespace="survey.imputation",
    version="1.0.0",
    tags={"survey", "nonresponse", "adjustment"},
)
class NonresponseAdjustmentEstimator:
    """Adjust survey weights or outcomes for unit nonresponse."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="nonresponse_adjustment",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")
                ),
                SlotSpec(
                    "response_indicator",
                    SlotType.VECTOR,
                    Unit("indicator", "binary"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "base_weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="max_iter", default=50),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Nonresponse adjustment via response propensity weighting.",
        tags=frozenset({"survey", "nonresponse", "adjustment", "propensity-weighting"}),
        equations={"adjustment": "w_adj = w_base / P(R=1|X)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Handle missing values in survey data via imputation; maintain sample size and distributional properties",
        output_interpretation="Imputed dataset(s). Check imputation plausibility. For MI: pool estimates using Rubin's rules.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        r = np.asarray(state["response_indicator"], dtype=float)
        w = np.asarray(state["base_weights"], dtype=float)
        n = len(r)
        max_iter = int(params.get("max_iter", 50))

        # Logistic regression for response propensity
        X_aug = np.column_stack([np.ones(n), X])
        beta = np.zeros(X_aug.shape[1])

        for _ in range(max_iter):
            eta = np.clip(X_aug @ beta, -20, 20)
            p_hat = 1.0 / (1.0 + np.exp(-eta))
            W_diag = p_hat * (1 - p_hat)
            W_diag = np.maximum(W_diag, 1e-12)
            grad = X_aug.T @ (r - p_hat)
            H = X_aug.T @ np.diag(W_diag) @ X_aug
            try:
                delta = np.linalg.solve(H, grad)
            except np.linalg.LinAlgError:
                break
            beta += delta
            if np.max(np.abs(delta)) < 1e-8:
                break

        eta_final = np.clip(X_aug @ beta, -20, 20)
        propensity = 1.0 / (1.0 + np.exp(-eta_final))
        propensity = np.clip(propensity, 0.01, 0.99)

        adjusted_weights = w / propensity
        # Normalize to sum of base weights among respondents
        resp_mask = r > 0.5
        if np.any(resp_mask):
            scale = float(np.sum(w)) / float(np.sum(adjusted_weights[resp_mask]))
            adjusted_weights[resp_mask] *= scale

        return {
            "result": {
                "adjusted_weights": adjusted_weights.tolist(),
                "response_propensities": propensity.tolist(),
                "response_rate": float(np.mean(r)),
                "weight_cv": float(
                    np.std(adjusted_weights[resp_mask])
                    / max(np.mean(adjusted_weights[resp_mask]), 1e-12)
                )
                if np.any(resp_mask)
                else 0.0,
                "n_respondents": int(np.sum(resp_mask)),
                "n_total": n,
            }
        }


__all__ = [
    "MICEEstimator",
    "NonresponseAdjustmentEstimator",
]
