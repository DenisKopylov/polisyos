"""Public econometrics timeseries module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.common.logger import get_logger
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

from .protocols import EconometricResult, TimeSeriesData

logger = get_logger(__name__)


def _time_series_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=TimeSeriesData,
        nested_keys=("time_series_data",),
    )


def _materialize_time_series(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
    payload = _time_series_payload(fallback_state)
    payload.update(bound_inputs)
    return TimeSeriesData.model_validate(payload)


def _time_series_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
                contract_id=EconometricResult.contract_id,
            ),
            SlotSpec(
                name="uncertainty_envelope",
                slot_type=SlotType.SCALAR,
                unit=Unit("uncertainty", "json"),
            ),
        }
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except Exception:
        return None
    if not np.isfinite(result):
        return None
    return result


def _coerce_ci_mapping(
    conf_int_obj: Any,
    *,
    names: list[str],
) -> dict[str, tuple[float, float]]:
    result: dict[str, tuple[float, float]] = {}
    if conf_int_obj is None:
        return result

    for idx, name in enumerate(names):
        lo: float | None = None
        hi: float | None = None
        try:
            row = conf_int_obj.iloc[idx]
            if hasattr(row, "iloc"):
                lo = _safe_float(row.iloc[0])
                hi = _safe_float(row.iloc[1])
            else:
                arr = np.asarray(row)
                if arr.size >= 2:
                    lo = _safe_float(arr[0])
                    hi = _safe_float(arr[1])
        except Exception:
            try:
                row = conf_int_obj[idx]
                arr = np.asarray(row)
                if arr.size >= 2:
                    lo = _safe_float(arr[0])
                    hi = _safe_float(arr[1])
            except Exception as exc:
                logger.debug("Ignored exception: %s", exc)

        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        result[name] = (lo, hi)

    return result


def _run_arima(state: TimeSeriesData, params: Mapping[str, Any]) -> EconometricResult:
    from statsmodels.tsa.arima.model import ARIMA

    endog = np.asarray(state.endog)
    if endog.ndim != 1:
        raise ValueError("ARIMA requires 1D endog series")

    p = int(params.get("p", 1))
    d = int(params.get("d", 0))
    q = int(params.get("q", 0))
    if min(p, d, q) < 0:
        raise ValueError("ARIMA orders p,d,q must be non-negative")

    confidence_level = float(params.get("confidence_level", 0.95))
    model = ARIMA(endog, exog=state.exog, order=(p, d, q))
    fit_result = model.fit()

    param_names = [str(name) for name in getattr(fit_result, "param_names", [])]
    if not param_names:
        param_names = [f"param_{i}" for i in range(len(np.asarray(fit_result.params)))]

    params_arr = np.asarray(fit_result.params)
    bse_arr = np.asarray(fit_result.bse)
    tvalues_arr = np.asarray(fit_result.tvalues)
    pvalues_arr = np.asarray(fit_result.pvalues)

    params_dict = {name: float(params_arr[idx]) for idx, name in enumerate(param_names)}
    std_errors = {name: float(bse_arr[idx]) for idx, name in enumerate(param_names)}
    t_stats = {name: float(tvalues_arr[idx]) for idx, name in enumerate(param_names)}
    p_values = {name: float(pvalues_arr[idx]) for idx, name in enumerate(param_names)}

    conf_int_obj = fit_result.conf_int(alpha=1.0 - confidence_level)
    intervals = _coerce_ci_mapping(conf_int_obj, names=param_names)

    diagnostics: dict[str, Any] = {
        "order": [p, d, q],
        "aic": _safe_float(getattr(fit_result, "aic", None)),
        "bic": _safe_float(getattr(fit_result, "bic", None)),
    }

    return EconometricResult(
        method_name="arima",
        params=params_dict,
        std_errors=std_errors,
        t_stats=t_stats,
        p_values=p_values,
        confidence_intervals=intervals,
        confidence_level=confidence_level,
        n_obs=int(getattr(fit_result, "nobs", state.n_obs) or state.n_obs),
        diagnostics=diagnostics,
        model_info={
            "library": "statsmodels",
            "estimator": "ARIMA",
            "order": [p, d, q],
        },
    )


def _run_var(state: TimeSeriesData, params: Mapping[str, Any]) -> EconometricResult:
    from statsmodels.tsa.api import VAR


    endog = np.asarray(state.endog)
    if endog.ndim != 2:
        raise ValueError("VAR requires 2D endog series")
    if endog.shape[1] < 2:
        raise ValueError("VAR requires at least two endogenous variables")

    max_lags = int(params.get("max_lags", 8))
    if max_lags <= 0:
        raise ValueError("max_lags must be > 0")

    ic = str(params.get("information_criterion", "aic"))
    confidence_level = float(params.get("confidence_level", 0.95))

    model = VAR(endog=endog, exog=state.exog)
    fit_result = model.fit(maxlags=max_lags, ic=ic)

    flat_params: dict[str, float] = {}
    flat_std_errors: dict[str, float] = {}
    flat_pvalues: dict[str, float] = {}

    params_arr = np.asarray(fit_result.params)
    stderr_arr = np.asarray(fit_result.stderr)
    pvalues_arr = np.asarray(fit_result.pvalues)
    if params_arr.ndim == 1:
        params_arr = params_arr.reshape(-1, 1)
    if stderr_arr.ndim == 1:
        stderr_arr = stderr_arr.reshape(-1, 1)
    if pvalues_arr.ndim == 1:
        pvalues_arr = pvalues_arr.reshape(-1, 1)

    equations = list(getattr(fit_result, "names", []))
    if not equations:
        equations = [f"eq{i}" for i in range(params_arr.shape[1])]

    model_obj = getattr(fit_result, "model", None)
    row_names = list(getattr(model_obj, "exog_names", []) or [])
    if len(row_names) != params_arr.shape[0]:
        row_names = [f"coef_{i}" for i in range(params_arr.shape[0])]

    for eq_idx, eq_name in enumerate(equations):
        for row_idx, row_name in enumerate(row_names):
            key = f"{eq_name}.{row_name}"
            flat_params[key] = float(params_arr[row_idx, eq_idx])
            flat_std_errors[key] = float(stderr_arr[row_idx, eq_idx])
            flat_pvalues[key] = float(pvalues_arr[row_idx, eq_idx])

    diagnostics = {
        "k_ar": int(getattr(fit_result, "k_ar", 0) or 0),
        "aic": _safe_float(getattr(fit_result, "aic", None)),
        "bic": _safe_float(getattr(fit_result, "bic", None)),
        "fpe": _safe_float(getattr(fit_result, "fpe", None)),
        "information_criterion": ic,
    }

    return EconometricResult(
        method_name="var",
        params=flat_params,
        std_errors=flat_std_errors,
        p_values=flat_pvalues,
        confidence_level=confidence_level,
        n_obs=int(getattr(fit_result, "nobs", state.n_obs) or state.n_obs),
        n_periods=int(getattr(fit_result, "nobs", state.n_obs) or state.n_obs),
        diagnostics=diagnostics,
        model_info={
            "library": "statsmodels",
            "estimator": "VAR",
            "k_ar": int(getattr(fit_result, "k_ar", 0) or 0),
            "variables": equations,
        },
    )


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "time-series", "arima", "var", "deprecated:aggregate-wrapper"},
)
class TimeSeriesEstimator:
    """Time-series econometric estimators via statsmodels."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="time_series",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="time_series_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("timeseries", "dataset"),
                    contract_id=TimeSeriesData.contract_id,
                )
            }
        ),
        output_slots=_time_series_output_slots(),
        parameters=(
            ParameterSpec(name="model", default="arima"),
            ParameterSpec(name="p", default=1),
            ParameterSpec(name="d", default=0),
            ParameterSpec(name="q", default=0),
            ParameterSpec(name="max_lags", default=8),
            ParameterSpec(name="information_criterion", default="aic"),
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
        description="Time-series estimators: ARIMA and VAR via statsmodels.",
        tags=frozenset({"econometrics", "time-series", "arima", "var"}),
        citations=(
            "Box, G.E.P. & Jenkins, G.M. (1970). Time Series Analysis.",
            "Sims, C.A. (1980). Macroeconomics and Reality.",
            "Hamilton, J. (1994). Time Series Analysis.",
        ),
        equations={
            "arima": "y_t = c + sum(phi_i * y_{t-i}) + sum(theta_j * e_{t-j}) + e_t",
            "var": "Y_t = c + sum(A_i * Y_{t-i}) + u_t",
        },
        assumptions={
            "arima_stationarity": "Series is stationary after differencing d times.",
            "var_stability": "VAR process is stable with roots outside unit circle.",
            "error_properties": "Residual diagnostics should be checked by analyst.",
        },
        when_to_use="Univariate (ARIMA) or multivariate (VAR) time series forecasting; stationary or difference-stationary series",
        typical_min_obs=50,
        output_interpretation="ARIMA: forecasts with CI, AIC/BIC for model selection, check residual autocorrelation. VAR: IRFs show dynamic responses, FEVD shows each variable's contribution.",
    )

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)

        model = str(params.get("model", "arima")).lower()
        if model == "var":
            result = _run_var(data, params)
        else:
            result = _run_arima(data, params)

        envelope = result.to_uncertainty_envelope(param_name=params.get("envelope_param"))
        return {
            "result": result,
            "uncertainty_envelope": envelope,
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        return _materialize_time_series(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "time-series", "arima"},
)
class ARIMAEstimator:
    """Dedicated ARIMA estimator with explicit time-series slots."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="arima",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="endog",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("timeseries", "value"),
                    shape=("n_obs",),
                )
            }
        ),
        output_slots=_time_series_output_slots(),
        parameters=(
            ParameterSpec(name="p", default=1),
            ParameterSpec(name="d", default=0),
            ParameterSpec(name="q", default=0),
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
        description="Dedicated ARIMA estimator for univariate time series.",
        tags=frozenset({"econometrics", "time-series", "arima"}),
        citations=TimeSeriesEstimator.metadata.citations,
        equations={"arima": TimeSeriesEstimator.metadata.equations["arima"]},
        assumptions=TimeSeriesEstimator.metadata.assumptions,
        when_to_use="Univariate time series forecasting; stationary or difference-stationary series",
        typical_min_obs=50,
        output_interpretation="Forecasts with CI. AIC/BIC for model selection. Check residual autocorrelation.",
    )

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        result = _run_arima(data, params)
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        return _materialize_time_series(bound_inputs, fallback_state)


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "time-series", "var"},
)
class VAREstimator:
    """Dedicated VAR estimator for multivariate time series."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="var",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="endog",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("timeseries", "value"),
                    shape=("n_obs", "n_series"),
                )
            }
        ),
        output_slots=_time_series_output_slots(),
        parameters=(
            ParameterSpec(name="max_lags", default=8),
            ParameterSpec(name="information_criterion", default="aic"),
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
        description="Dedicated VAR estimator for multivariate time series.",
        tags=frozenset({"econometrics", "time-series", "var"}),
        citations=TimeSeriesEstimator.metadata.citations,
        equations={"var": TimeSeriesEstimator.metadata.equations["var"]},
        assumptions=TimeSeriesEstimator.metadata.assumptions,
        when_to_use="Multivariate time series; joint forecasting and impulse response analysis across variables",
        typical_min_obs=80,
        output_interpretation="IRFs show dynamic responses. Forecast error variance decomposition shows each variable's contribution.",
    )

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        result = _run_var(data, params)
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        return _materialize_time_series(bound_inputs, fallback_state)


__all__ = [
    "ARIMAEstimator",
    "TimeSeriesEstimator",
    "VAREstimator",
]
