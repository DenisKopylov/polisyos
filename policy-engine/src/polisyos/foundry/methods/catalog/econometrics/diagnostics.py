"""Public econometrics diagnostics module API."""
from __future__ import annotations

import uuid
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
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario, OutcomeComparison

from polisyos.foundry.methods.catalog._payloads import extract_model_payload

from .protocols import EconometricDiagnosticResult, PanelData, TimeSeriesData


def _diagnostic_output_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("diagnostic", "json"),
                contract_id=EconometricDiagnosticResult.contract_id,
            )
        }
    )


def _panel_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelData,
        nested_keys=("panel_data",),
    )


def _time_series_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=TimeSeriesData,
        nested_keys=("time_series_data",),
    )


def _build_diag_result(
    test_name: str,
    *,
    statistic: float | None,
    p_value: float | None,
    passed: bool,
    critical_value: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> EconometricDiagnosticResult:
    return EconometricDiagnosticResult(
        test_name=test_name,
        statistic=statistic,
        p_value=p_value,
        passed=passed,
        critical_value=critical_value,
        metadata=metadata or {},
    )


@foundry_method(
    namespace="econometrics.diagnostics",
    version="1.0.0",
    tags={"econometrics", "diagnostics", "hausman"},
)
class HausmanTestEstimator:
    """Hausman test estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "pandas", "scipy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hausman_test",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("dependent", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("entity_ids", SlotType.VECTOR, Unit("entity", "id"), shape=("n_obs",)),
                SlotSpec("time_ids", SlotType.VECTOR, Unit("time", "index"), shape=("n_obs",)),
            }
        ),
        output_slots=_diagnostic_output_slot(),
        parameters=(ParameterSpec(name="alpha", default=0.05),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Hausman specification test between FE and RE panel estimators.",
        tags=frozenset({"econometrics", "diagnostics", "hausman"}),
        when_to_use="Panel data; test whether random effects are consistent (i.e., correlated with regressors)",
        citations=(
            "Hausman, J. (1978). Specification tests in econometrics. Econometrica, 46(6), 1251-1271.",
        ),
        typical_min_obs=50,
        output_interpretation="Reject H0 → FE preferred (RE inconsistent). Fail to reject → RE efficient. Chi-sq statistic with df = number of common coefficients.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelData.model_validate(payload)

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        import pandas as pd
        from linearmodels.panel import PanelOLS, RandomEffects
        from scipy.stats import chi2

        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        names = list(data.feature_names or [f"x{i}" for i in range(data.exog.shape[1])])
        frame = pd.DataFrame(data.exog, columns=names)
        frame["y"] = data.dependent
        frame["entity"] = data.entity_ids
        frame["time"] = data.time_ids
        frame = frame.set_index(["entity", "time"])
        rhs = " + ".join(names)
        fe = PanelOLS.from_formula(f"y ~ {rhs} + EntityEffects", data=frame).fit(cov_type="robust")
        re = RandomEffects.from_formula(f"y ~ 1 + {rhs}", data=frame).fit(cov_type="robust")
        common = [name for name in names if name in fe.params.index and name in re.params.index]
        diff = np.asarray(fe.params[common] - re.params[common], dtype=float)
        cov = np.asarray(fe.cov.loc[common, common] - re.cov.loc[common, common], dtype=float)
        stat = float(diff.T @ np.linalg.pinv(cov) @ diff)
        df = max(len(common), 1)
        p_value = float(1.0 - chi2.cdf(stat, df=df))
        alpha = float(params.get("alpha", 0.05))
        return {
            "result": _build_diag_result(
                "hausman_test",
                statistic=stat,
                p_value=p_value,
                passed=bool(p_value >= alpha),
                critical_value=float(chi2.ppf(1.0 - alpha, df=df)),
                metadata={"df": df, "common_coefficients": common},
            )
        }


@foundry_method(
    namespace="econometrics.diagnostics",
    version="1.0.0",
    tags={"econometrics", "diagnostics", "weak-iv"},
)
class WeakIVTestEstimator:
    """Weak IV test estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="weak_iv_test",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("dependent", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("instrument_ids", SlotType.MATRIX, Unit("instrument", "value"), shape=("n_obs", "n_instruments")),
            }
        ),
        output_slots=_diagnostic_output_slot(),
        parameters=(ParameterSpec(name="n_endogenous", default=1), ParameterSpec(name="threshold", default=10.0)),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="First-stage weak instrument diagnostic using an F-stat threshold.",
        tags=frozenset({"econometrics", "diagnostics", "weak-iv"}),
        when_to_use="IV/2SLS estimation; check whether instruments are sufficiently correlated with endogenous regressors",
        citations=(
            "Stock, J. & Yogo, M. (2005). Testing for weak instruments in linear IV regression. In Identification and Inference for Econometric Models, Cambridge University Press.",
            "Staiger, D. & Stock, J. (1997). Instrumental variables regression with weak instruments. Econometrica, 65(3), 557-586.",
        ),
        typical_min_obs=100,
        output_interpretation="F-stat >= 10 (Staiger-Stock rule of thumb) indicates strong instruments. Low F-stat → weak IV bias toward OLS.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelData.model_validate(payload)

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm

        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        if data.instrument_ids is None:
            raise ValueError("weak_iv_test requires instrument_ids")
        n_endogenous = max(1, int(params.get("n_endogenous", 1)))
        y = np.asarray(data.exog[:, 0], dtype=float) if n_endogenous >= 1 else np.asarray(data.exog[:, 0], dtype=float)
        exog_controls = np.asarray(data.exog[:, n_endogenous:], dtype=float)
        z = np.asarray(data.instrument_ids, dtype=float)
        full_x = sm.add_constant(np.column_stack([exog_controls, z]), has_constant="add")
        restricted_x = sm.add_constant(exog_controls, has_constant="add")
        fit_full = sm.OLS(y, full_x).fit()
        fit_restricted = sm.OLS(y, restricted_x).fit()
        f_stat, p_value, _ = fit_full.compare_f_test(fit_restricted)
        threshold = float(params.get("threshold", 10.0))
        return {
            "result": _build_diag_result(
                "weak_iv_test",
                statistic=float(f_stat),
                p_value=float(p_value),
                passed=bool(float(f_stat) >= threshold),
                critical_value=threshold,
                metadata={"rule_of_thumb": "Staiger-Stock", "n_instruments": int(z.shape[1])},
            )
        }


@foundry_method(
    namespace="econometrics.diagnostics",
    version="1.0.0",
    tags={"econometrics", "diagnostics", "sargan-hansen"},
)
class SarganHansenEstimator:
    """Sargan hansen estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("linearmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sargan_hansen",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("dependent", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
                SlotSpec("instrument_ids", SlotType.MATRIX, Unit("instrument", "value"), shape=("n_obs", "n_instruments")),
            }
        ),
        output_slots=_diagnostic_output_slot(),
        parameters=(ParameterSpec(name="n_endogenous", default=1), ParameterSpec(name="alpha", default=0.05)),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Overidentifying restrictions test using Sargan-Hansen/J-statistic.",
        tags=frozenset({"econometrics", "diagnostics", "sargan-hansen"}),
        when_to_use="Overidentified IV models (more instruments than endogenous variables); test instrument exogeneity jointly",
        citations=(
            "Hansen, L. (1982). Large sample properties of generalized method of moments estimators. Econometrica, 50(4), 1029-1054.",
            "Sargan, J. (1958). The estimation of economic relationships using instrumental variables. Econometrica, 26(3), 393-415.",
        ),
        typical_min_obs=100,
        output_interpretation="Fail to reject H0 → instruments pass overidentification test. Reject → at least one instrument correlated with error.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelData.model_validate(payload)

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        from linearmodels.iv import IV2SLS

        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        if data.instrument_ids is None:
            raise ValueError("sargan_hansen requires instrument_ids")
        n_endogenous = max(1, int(params.get("n_endogenous", 1)))
        y = np.asarray(data.dependent, dtype=float)
        endog = np.asarray(data.exog[:, :n_endogenous], dtype=float)
        exog = np.asarray(data.exog[:, n_endogenous:], dtype=float) if data.exog.shape[1] > n_endogenous else None
        fit = IV2SLS(y, exog, endog, np.asarray(data.instrument_ids, dtype=float)).fit(cov_type="robust")
        stat_obj = getattr(fit, "sargan", None) or getattr(fit, "j_stat", None)
        stat = None if stat_obj is None else float(getattr(stat_obj, "stat", np.nan))
        p_value = None if stat_obj is None else float(getattr(stat_obj, "pval", np.nan))
        alpha = float(params.get("alpha", 0.05))
        return {
            "result": _build_diag_result(
                "sargan_hansen",
                statistic=stat,
                p_value=p_value,
                passed=bool(p_value is not None and p_value >= alpha),
                critical_value=alpha,
                metadata={"test_source": type(stat_obj).__name__ if stat_obj is not None else "missing"},
            )
        }


@foundry_method(
    namespace="econometrics.diagnostics",
    version="1.0.0",
    tags={"econometrics", "diagnostics", "cointegration"},
)
class CointegrationTestEstimator:
    """Cointegration test estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cointegration_test",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.TENSOR, Unit("timeseries", "value"), shape=("n_obs", "n_series")),
            }
        ),
        output_slots=_diagnostic_output_slot(),
        parameters=(ParameterSpec(name="alpha", default=0.05),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Engle-Granger cointegration diagnostic.",
        tags=frozenset({"econometrics", "diagnostics", "cointegration"}),
        when_to_use="Test for long-run equilibrium relationship between two I(1) time series before fitting VECM",
        citations=(
            "Engle, R. & Granger, C. (1987). Co-integration and error correction: Representation, estimation, and testing. Econometrica, 55(2), 251-276.",
            "Johansen, S. (1991). Estimation and hypothesis testing of cointegration vectors in Gaussian vector autoregressive models. Econometrica, 59(6), 1551-1580.",
        ),
        typical_min_obs=100,
        output_interpretation="Reject H0 → series are cointegrated (residuals stationary). Use VECM. Fail to reject → model in differences (VAR).",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        from statsmodels.tsa.stattools import coint

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        series = np.asarray(data.endog, dtype=float)
        if series.ndim == 1:
            if data.exog is None or np.asarray(data.exog).shape[1] < 1:
                raise ValueError("cointegration_test requires two time series")
            y0 = series
            y1 = np.asarray(data.exog[:, 0], dtype=float)
        else:
            if series.shape[1] < 2:
                raise ValueError("cointegration_test requires at least two endogenous series")
            y0 = series[:, 0]
            y1 = series[:, 1]
        stat, p_value, crit = coint(y0, y1)
        alpha = float(params.get("alpha", 0.05))
        return {
            "result": _build_diag_result(
                "cointegration_test",
                statistic=float(stat),
                p_value=float(p_value),
                passed=bool(float(p_value) < alpha),
                critical_value=float(crit[1]),
                metadata={"critical_values": [float(item) for item in crit]},
            )
        }


@foundry_method(
    namespace="econometrics.diagnostics",
    version="1.0.0",
    tags={"econometrics", "diagnostics", "forecast-backtest"},
)
class ForecastBacktestEstimator:
    """Forecast backtest estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="forecast_backtest",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.TENSOR, Unit("timeseries", "value"), shape=("n_obs", "n_series")),
            }
        ),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("backtest", "json"))}),
        parameters=(
            ParameterSpec(name="model", default="arima"),
            ParameterSpec(name="holdout", default=12),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Rolling holdout forecast backtest for ARIMA/VAR style models.",
        tags=frozenset({"econometrics", "diagnostics", "forecast-backtest"}),
        when_to_use="Evaluate out-of-sample forecast accuracy of time series models using rolling holdout windows",
        citations=(
            "Tashman, L. (2000). Out-of-sample tests of forecasting accuracy: An analysis and review. International Journal of Forecasting, 16(4), 437-450.",
        ),
        typical_min_obs=50,
        output_interpretation="RMSE and MAE over holdout period. Lower values = better forecast accuracy. Compare across models.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        from statsmodels.tsa.arima.model import ARIMA

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            y = y[:, 0]
        holdout = max(4, int(params.get("holdout", 12)))
        holdout = min(holdout, y.shape[0] - 4)
        train = y[:-holdout]
        test = y[-holdout:]
        preds: list[float] = []
        for idx in range(holdout):
            fit = ARIMA(y[: y.shape[0] - holdout + idx], order=(1, 0, 0)).fit()
            preds.append(float(fit.forecast(steps=1)[0]))
        preds_arr = np.asarray(preds, dtype=float)
        rmse = float(np.sqrt(np.mean((preds_arr - test) ** 2)))
        mae = float(np.mean(np.abs(preds_arr - test)))
        comparisons = [
            OutcomeComparison(
                metric_name=f"step_{idx}",
                y_pred=float(preds_arr[idx]),
                y_true=float(test[idx]),
                absolute_error=float(abs(preds_arr[idx] - test[idx])),
                relative_error=float(abs(preds_arr[idx] - test[idx]) / max(abs(test[idx]), 1e-8)),
                within_ci=False,
            )
            for idx in range(holdout)
        ]
        report = BacktestReport(
            report_id=f"forecast_backtest_{uuid.uuid4().hex[:10]}",
            scenarios=[
                BacktestScenario(
                    scenario_id="holdout",
                    scenario_label="rolling_holdout",
                    outcome_comparisons=comparisons,
                    rmse=rmse,
                    mae=mae,
                )
            ],
            overall_rmse=rmse,
            overall_mae=mae,
            n_scenarios=1,
            n_metrics_evaluated=holdout,
            metadata={"model": str(params.get("model", "arima")), "holdout": holdout},
        )
        return {"result": report}


__all__ = [
    "CointegrationTestEstimator",
    "ForecastBacktestEstimator",
    "HausmanTestEstimator",
    "SarganHansenEstimator",
    "WeakIVTestEstimator",
]
