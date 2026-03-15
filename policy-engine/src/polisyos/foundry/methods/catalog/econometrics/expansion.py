from __future__ import annotations

import math
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
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData

from .advanced import (
    _build_regression_result,
    _panel_observational_payload,
    _result_output_slots,
    _safe_float,
    _time_series_payload,
)
from .protocols import EconometricResult, TimeSeriesData


def _z_value(confidence_level: float) -> float:
    return 1.959963984540054 if confidence_level >= 0.95 else 1.6448536269514722


def _normal_pvalue(z_score: float) -> float:
    return float(math.erfc(abs(float(z_score)) / math.sqrt(2.0)))


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "vecm"},
)
class VECMEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="vecm",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.TENSOR, Unit("timeseries", "value"), shape=("n_obs", "n_series")),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="coint_rank", default=1),
            ParameterSpec(name="k_ar_diff", default=1),
            ParameterSpec(name="deterministic", default="co"),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Vector error correction model for cointegrated multivariate time series.",
        tags=frozenset({"econometrics", "vecm"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        from statsmodels.tsa.vector_ar.vecm import VECM

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        endog = np.asarray(data.endog, dtype=float)
        if endog.ndim == 1:
            raise ValueError("vecm requires multivariate endog with at least two series")
        exog = None if data.exog is None else np.asarray(data.exog, dtype=float)
        fit = VECM(
            endog,
            exog=exog,
            k_ar_diff=max(1, int(params.get("k_ar_diff", 1))),
            coint_rank=max(1, int(params.get("coint_rank", 1))),
            deterministic=str(params.get("deterministic", "co")),
        ).fit()

        coeffs: dict[str, float] = {}
        for row_idx, row in enumerate(np.asarray(fit.alpha, dtype=float)):
            for col_idx, value in enumerate(row):
                coeffs[f"alpha_{row_idx}_{col_idx}"] = float(value)
        for row_idx, row in enumerate(np.asarray(fit.beta, dtype=float)):
            for col_idx, value in enumerate(row):
                coeffs[f"beta_{row_idx}_{col_idx}"] = float(value)
        gamma = getattr(fit, "gamma", None)
        if gamma is not None:
            gamma_arr = np.asarray(gamma, dtype=float)
            for idx_tuple, value in np.ndenumerate(gamma_arr):
                coeffs["gamma_" + "_".join(str(item) for item in idx_tuple)] = float(value)

        result = _build_regression_result(
            method_name="vecm",
            params=coeffs,
            diagnostics={
                "coint_rank": int(params.get("coint_rank", 1)),
                "k_ar_diff": int(params.get("k_ar_diff", 1)),
                "llf": _safe_float(getattr(fit, "llf", None)),
            },
            model_info={"library": "statsmodels", "estimator": "VECM"},
            n_obs=int(endog.shape[0]),
            n_periods=int(endog.shape[0]),
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "bayesian-var"},
)
class BayesianVAREstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bayesian_var",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.TENSOR, Unit("timeseries", "value"), shape=("n_obs", "n_series")),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="n_lags", default=2),
            ParameterSpec(name="prior_scale", default=0.25),
            ParameterSpec(name="include_intercept", default=True),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Closed-form Bayesian VAR with ridge-style Minnesota prior shrinkage.",
        tags=frozenset({"econometrics", "bayesian-var"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        endog = np.asarray(data.endog, dtype=float)
        if endog.ndim == 1:
            endog = endog[:, None]
        n_obs, n_series = endog.shape
        n_lags = max(1, int(params.get("n_lags", 2)))
        include_intercept = bool(params.get("include_intercept", True))
        if n_obs <= n_lags + 5:
            raise ValueError("bayesian_var requires more observations than lags")

        rows = []
        targets = []
        for t in range(n_lags, n_obs):
            lagged = [endog[t - lag] for lag in range(1, n_lags + 1)]
            reg = np.concatenate(lagged, axis=0)
            if include_intercept:
                reg = np.concatenate([[1.0], reg], axis=0)
            rows.append(reg)
            targets.append(endog[t])
        x = np.asarray(rows, dtype=float)
        y = np.asarray(targets, dtype=float)
        prior_scale = max(1e-6, float(params.get("prior_scale", 0.25)))
        precision = x.T @ x + (1.0 / prior_scale) * np.eye(x.shape[1], dtype=float)
        precision_inv = np.linalg.pinv(precision)
        beta = precision_inv @ x.T @ y
        fitted = x @ beta
        residual = y - fitted
        sigma = residual.T @ residual / max(y.shape[0] - x.shape[1], 1)
        confidence_level = float(params.get("confidence_level", 0.95))
        z = _z_value(confidence_level)

        names: list[str] = []
        if include_intercept:
            names.append("intercept")
        for lag in range(1, n_lags + 1):
            for series_idx in range(n_series):
                names.append(f"lag{lag}_series{series_idx}")

        coeffs: dict[str, float] = {}
        std_errors: dict[str, float] = {}
        p_values: dict[str, float] = {}
        intervals: dict[str, tuple[float, float]] = {}
        diag_precision = np.diag(precision_inv)
        for eq_idx in range(n_series):
            sigma_eq = float(max(sigma[eq_idx, eq_idx], 1e-10))
            se_vec = np.sqrt(np.maximum(diag_precision * sigma_eq, 1e-12))
            for coef_idx, base_name in enumerate(names):
                label = f"eq{eq_idx}_{base_name}"
                value = float(beta[coef_idx, eq_idx])
                se = float(se_vec[coef_idx])
                z_score = value / max(se, 1e-12)
                coeffs[label] = value
                std_errors[label] = se
                p_values[label] = _normal_pvalue(z_score)
                intervals[label] = (value - z * se, value + z * se)

        result = _build_regression_result(
            method_name="bayesian_var",
            params=coeffs,
            std_errors=std_errors,
            p_values=p_values,
            confidence_intervals=intervals,
            diagnostics={
                "prior_scale": prior_scale,
                "residual_covariance_trace": float(np.trace(sigma)),
                "n_lags": n_lags,
            },
            model_info={"library": "numpy", "estimator": "BayesianVAR"},
            n_obs=int(y.shape[0]),
            n_periods=int(n_obs),
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


def _project_simplex(weights: np.ndarray) -> np.ndarray:
    positive = np.maximum(np.asarray(weights, dtype=float), 0.0)
    total = float(np.sum(positive))
    if total <= 1e-12:
        return np.full_like(positive, 1.0 / positive.shape[0])
    return positive / total


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "synthetic-did"},
)
class SyntheticDiDEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="synthetic_did",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.MATRIX, Unit("outcome", "value"), shape=("n_units", "n_periods")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("binary", "flag"), shape=("n_units",)),
                SlotSpec("time_treatment", SlotType.SCALAR, Unit("time", "index")),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="ridge", default=1e-3),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Synthetic difference-in-differences estimator with ridge-regularized donor weights.",
        tags=frozenset({"econometrics", "synthetic-did"}),
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        payload = _panel_observational_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelObservationalData.model_validate(payload)

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        treated_mask = np.asarray(data.treatment, dtype=int) == 1
        control_mask = ~treated_mask
        if not treated_mask.any() or not control_mask.any():
            raise ValueError("synthetic_did requires treated and control units")

        pre = slice(0, data.time_treatment)
        post = slice(data.time_treatment, data.n_periods)
        treated_pre = np.mean(np.asarray(data.outcome[treated_mask, pre], dtype=float), axis=0)
        treated_post = np.mean(np.asarray(data.outcome[treated_mask, post], dtype=float), axis=0)
        controls_pre = np.asarray(data.outcome[control_mask, pre], dtype=float)
        controls_post = np.asarray(data.outcome[control_mask, post], dtype=float)

        ridge = max(1e-8, float(params.get("ridge", 1e-3)))
        gram = controls_pre @ controls_pre.T + ridge * np.eye(controls_pre.shape[0], dtype=float)
        target = controls_pre @ treated_pre
        weights = np.linalg.pinv(gram) @ target
        weights = _project_simplex(weights)

        synthetic_pre = weights @ controls_pre
        synthetic_post = weights @ controls_post
        effect_series = (treated_post - synthetic_post) - (np.mean(treated_pre - synthetic_pre))
        ate = float(np.mean(effect_series))
        se = float(np.std(effect_series, ddof=1) / np.sqrt(effect_series.shape[0])) if effect_series.shape[0] > 1 else 0.0
        result = _build_regression_result(
            method_name="synthetic_did",
            params={"ate_sdid": ate},
            std_errors={"ate_sdid": se},
            p_values={"ate_sdid": _normal_pvalue(0.0 if se <= 0 else ate / se)},
            confidence_intervals={"ate_sdid": (ate - 1.96 * se, ate + 1.96 * se)},
            diagnostics={
                "pre_fit_rmse": float(np.sqrt(np.mean((treated_pre - synthetic_pre) ** 2))),
                "donor_weights": weights.tolist(),
            },
            model_info={"library": "numpy", "estimator": "SyntheticDiD"},
            n_obs=int(data.n_units * data.n_periods),
            n_periods=int(data.n_periods),
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


def _row_normalize(weights_matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(weights_matrix, dtype=float)
    row_sums = np.sum(arr, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return arr / row_sums


@foundry_method(
    namespace="econometrics.spatial",
    version="1.0.0",
    tags={"econometrics", "spatial-autoregressive"},
)
class SpatialAutoregressiveEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="spatial_autoregressive",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec(
                    "weights_matrix",
                    SlotType.MATRIX,
                    Unit("spatial_weight", "value"),
                    shape=("n_obs", "n_obs"),
                ),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default="rho"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Spatial autoregressive regression using a normalized spatial lag of the outcome.",
        tags=frozenset({"econometrics", "spatial-autoregressive"}),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm

        if not isinstance(state, Mapping):
            raise TypeError("spatial_autoregressive expects a mapping state")
        y = np.asarray(state["endog"], dtype=float)
        x = np.asarray(state["exog"], dtype=float)
        weights = _row_normalize(np.asarray(state["weights_matrix"], dtype=float))
        y_lag = weights @ y
        design = sm.add_constant(np.column_stack([y_lag, x]), has_constant="add")
        fit = sm.OLS(y, design).fit(cov_type="HC1")
        confidence_level = float(params.get("confidence_level", 0.95))
        z = _z_value(confidence_level)
        names = ["const", "rho"] + [
            f"x{i}" for i in range(x.shape[1])
        ]
        intervals = {
            names[idx]: (float(fit.params[idx] - z * fit.bse[idx]), float(fit.params[idx] + z * fit.bse[idx]))
            for idx in range(len(names))
        }
        result = _build_regression_result(
            method_name="spatial_autoregressive",
            params={names[idx]: fit.params[idx] for idx in range(len(names))},
            std_errors={names[idx]: fit.bse[idx] for idx in range(len(names))},
            p_values={names[idx]: fit.pvalues[idx] for idx in range(len(names))},
            confidence_intervals=intervals,
            diagnostics={
                "r_squared": _safe_float(getattr(fit, "rsquared", None)),
                "moran_like_lag_correlation": float(np.corrcoef(y, y_lag)[0, 1]),
            },
            model_info={"library": "statsmodels", "estimator": "SAR-OLS"},
            n_obs=int(y.shape[0]),
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


__all__ = [
    "BayesianVAREstimator",
    "SpatialAutoregressiveEstimator",
    "SyntheticDiDEstimator",
    "VECMEstimator",
]
