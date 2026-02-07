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

from .protocols import EconometricResult, TimeSeriesData


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
            except Exception:
                pass

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

    params_df = fit_result.params
    stderr_df = fit_result.stderr
    pvalues_df = fit_result.pvalues

    equations = list(getattr(fit_result, "names", []))
    if not equations:
        equations = [f"eq{i}" for i in range(params_df.shape[1])]

    for eq_idx, eq_name in enumerate(equations):
        for row_name in params_df.index:
            key = f"{eq_name}.{row_name}"
            flat_params[key] = float(params_df.loc[row_name].iloc[eq_idx])
            flat_std_errors[key] = float(stderr_df.loc[row_name].iloc[eq_idx])
            flat_pvalues[key] = float(pvalues_df.loc[row_name].iloc[eq_idx])

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
    tags={"econometrics", "time-series", "arima", "var"},
)
class TimeSeriesEstimator:
    """Time-series econometric estimators via statsmodels."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="time_series",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="time_series_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("timeseries", "observations"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="econometric_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("result", "json"),
                )
            }
        ),
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
            "envelope": envelope,
        }


__all__ = ["TimeSeriesEstimator"]
