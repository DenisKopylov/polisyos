"""Public econometrics advanced module API."""
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData

from .protocols import EconometricResult, PanelData, TimeSeriesData


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except Exception:
        return None
    if not np.isfinite(result):
        return None
    return result


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


def _panel_observational_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelObservationalData,
        nested_keys=("panel_data", "panel_observational_data"),
    )


def _result_output_slots() -> frozenset[SlotSpec]:
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


def _build_regression_result(
    *,
    method_name: str,
    params: Mapping[str, Any],
    std_errors: Mapping[str, Any] | None = None,
    p_values: Mapping[str, Any] | None = None,
    confidence_intervals: Mapping[str, tuple[float, float]] | None = None,
    diagnostics: dict[str, Any] | None = None,
    model_info: dict[str, Any] | None = None,
    n_obs: int = 0,
    n_periods: int | None = None,
) -> EconometricResult:
    return EconometricResult(
        method_name=method_name,
        params={str(k): float(v) for k, v in params.items() if _safe_float(v) is not None},
        std_errors={
            str(k): float(v)
            for k, v in (std_errors or {}).items()
            if _safe_float(v) is not None
        },
        p_values={
            str(k): float(v) for k, v in (p_values or {}).items() if _safe_float(v) is not None
        },
        confidence_intervals=dict(confidence_intervals or {}),
        diagnostics=diagnostics or {},
        model_info=model_info or {},
        n_obs=int(n_obs),
        n_periods=n_periods,
    )


@foundry_method(
    namespace="econometrics.regression",
    version="1.0.0",
    tags={"econometrics", "quantile-regression"},
)
class QuantileRegressionEstimator:
    """Quantile regression estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="quantile_regression",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("dependent", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec("exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="quantile", default=0.5),
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
        description="Quantile regression for heterogeneous effects across the conditional distribution.",
        tags=frozenset({"econometrics", "quantile-regression"}),
        citations=("Koenker, R. (2005). Quantile Regression.",),
        when_to_use="Distributional effects of treatment/policy; heterogeneous impacts at different outcome quantiles",
        typical_min_obs=100,
        output_interpretation="Conditional quantile function. β(τ): effect at quantile τ. Plot β(τ) vs τ to see distributional heterogeneity.",
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
        q = float(params.get("quantile", 0.5))
        confidence_level = float(params.get("confidence_level", 0.95))
        x = sm.add_constant(np.asarray(data.exog), has_constant="add")
        fit = sm.QuantReg(np.asarray(data.dependent), x).fit(q=q)
        names = ["const"] + list(data.feature_names or [f"x{i}" for i in range(data.exog.shape[1])])
        ci = fit.conf_int(alpha=1.0 - confidence_level)
        intervals = {
            names[idx]: (float(ci[idx, 0]), float(ci[idx, 1]))
            for idx in range(min(len(names), ci.shape[0]))
        }
        result = _build_regression_result(
            method_name="quantile_regression",
            params={names[idx]: fit.params[idx] for idx in range(len(names))},
            std_errors={names[idx]: fit.bse[idx] for idx in range(len(names))},
            p_values={names[idx]: fit.pvalues[idx] for idx in range(len(names))},
            confidence_intervals=intervals,
            diagnostics={"quantile": q, "pseudo_r_squared": _safe_float(getattr(fit, "prsquared", None))},
            model_info={"library": "statsmodels", "estimator": "QuantReg"},
            n_obs=data.n_obs,
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "event-study"},
)
class EventStudyEstimator:
    """Event study estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="event_study",
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
            ParameterSpec(name="pre_window", default=4),
            ParameterSpec(name="post_window", default=4),
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
        description="Simple event-study estimator over relative treatment time.",
        tags=frozenset({"econometrics", "event-study"}),
        citations=("Sun, L. & Abraham, S. (2021). Estimating dynamic treatment effects in event studies.",),
        when_to_use="Panel data with staggered or common treatment timing; plot dynamic treatment effects around event",
        typical_min_obs=50,
        output_interpretation="Coefficients at each relative period (pre/post event). Pre-period estimates should be near zero (parallel trends check).",
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
        timing = (
            np.asarray(data.treatment_timing)
            if data.treatment_timing is not None
            else np.where(np.asarray(data.treatment) == 1, int(data.time_treatment), -1)
        )
        pre_window = max(1, int(params.get("pre_window", 4)))
        post_window = max(1, int(params.get("post_window", 4)))
        confidence_level = float(params.get("confidence_level", 0.95))
        z = 1.959963984540054 if confidence_level >= 0.95 else 1.6448536269514722

        estimates: dict[str, float] = {}
        ses: dict[str, float] = {}
        pvalues: dict[str, float] = {}
        intervals: dict[str, tuple[float, float]] = {}
        n_cells = 0
        for rel_time in range(-pre_window, post_window + 1):
            if rel_time == -1:
                continue
            cell_effects: list[float] = []
            for unit_idx, start in enumerate(timing):
                if start < 0:
                    continue
                event_t = int(start + rel_time)
                baseline_t = int(start - 1)
                if event_t < 0 or event_t >= data.n_periods or baseline_t < 0:
                    continue
                control_mask = timing == -1
                if not control_mask.any():
                    control_mask = np.asarray(data.treatment) == 0
                if not control_mask.any():
                    continue
                treated_delta = float(data.outcome[unit_idx, event_t] - data.outcome[unit_idx, baseline_t])
                control_delta = float(
                    np.mean(data.outcome[control_mask, event_t] - data.outcome[control_mask, baseline_t])
                )
                cell_effects.append(treated_delta - control_delta)
            if not cell_effects:
                continue
            arr = np.asarray(cell_effects, dtype=float)
            estimate = float(np.mean(arr))
            se = float(np.std(arr, ddof=1) / np.sqrt(arr.shape[0])) if arr.shape[0] > 1 else 0.0
            label = f"event_t{rel_time:+d}"
            estimates[label] = estimate
            ses[label] = se
            z_score = 0.0 if se <= 0 else estimate / se
            p = float(math.erfc(abs(z_score) / np.sqrt(2.0)))
            pvalues[label] = p
            intervals[label] = (estimate - z * se, estimate + z * se)
            n_cells += int(arr.shape[0])

        result = _build_regression_result(
            method_name="event_study",
            params=estimates,
            std_errors=ses,
            p_values=pvalues,
            confidence_intervals=intervals,
            diagnostics={"n_cells": n_cells, "pre_window": pre_window, "post_window": post_window},
            model_info={"library": "numpy", "estimator": "event_study"},
            n_obs=int(data.n_units * data.n_periods),
            n_periods=data.n_periods,
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
    tags={"econometrics", "local-projections"},
)
class LocalProjectionsEstimator:
    """Local projections estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="local_projections",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
                SlotSpec("exog", SlotType.MATRIX, Unit("shock", "value"), shape=("n_obs", "n_features")),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="max_horizon", default=6),
            ParameterSpec(name="n_lags", default=2),
            ParameterSpec(name="shock_column", default=0),
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
        description="Jorda local projections for impulse responses.",
        tags=frozenset({"econometrics", "local-projections"}),
        citations=("Jorda, O. (2005). Estimation and Inference of Impulse Responses by Local Projections.",),
        when_to_use="Flexible impulse response estimation without VAR model restrictions; non-linear or state-dependent dynamics",
        typical_min_obs=80,
        output_interpretation="IRF at each horizon h. Plot irf_h0 through irf_hH with CIs. More robust to misspecification than VAR-based IRFs.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            raise ValueError("local projections currently require 1D endog")
        if data.exog is None:
            raise ValueError("local projections require exog with a shock column")
        shocks = np.asarray(data.exog, dtype=float)
        shock_col = int(params.get("shock_column", 0))
        max_horizon = max(1, int(params.get("max_horizon", 6)))
        n_lags = max(1, int(params.get("n_lags", 2)))
        confidence_level = float(params.get("confidence_level", 0.95))
        z = 1.959963984540054 if confidence_level >= 0.95 else 1.6448536269514722

        estimates: dict[str, float] = {}
        ses: dict[str, float] = {}
        pvalues: dict[str, float] = {}
        intervals: dict[str, tuple[float, float]] = {}
        for horizon in range(max_horizon + 1):
            rows = []
            targets = []
            for t in range(n_lags, y.shape[0] - horizon):
                lagged = [y[t - lag] for lag in range(1, n_lags + 1)]
                rows.append([shocks[t, shock_col], *lagged])
                targets.append(y[t + horizon])
            x = sm.add_constant(np.asarray(rows, dtype=float), has_constant="add")
            fit = sm.OLS(np.asarray(targets, dtype=float), x).fit(cov_type="HC1")
            key = f"irf_h{horizon}"
            estimate = float(fit.params[1])
            se = float(fit.bse[1])
            p = float(fit.pvalues[1])
            estimates[key] = estimate
            ses[key] = se
            pvalues[key] = p
            intervals[key] = (estimate - z * se, estimate + z * se)

        result = _build_regression_result(
            method_name="local_projections",
            params=estimates,
            std_errors=ses,
            p_values=pvalues,
            confidence_intervals=intervals,
            diagnostics={"max_horizon": max_horizon, "n_lags": n_lags},
            model_info={"library": "statsmodels", "estimator": "OLS"},
            n_obs=y.shape[0],
            n_periods=y.shape[0],
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
    tags={"econometrics", "garch"},
)
class GARCHEstimator:
    """GARCH estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("arch", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="garch",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="p", default=1),
            ParameterSpec(name="q", default=1),
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
        description="GARCH volatility model for conditional heteroskedasticity.",
        tags=frozenset({"econometrics", "garch"}),
        citations=("Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity.",),
        when_to_use="Volatility clustering in financial/macro time series; conditional heteroskedasticity",
        typical_min_obs=200,
        output_interpretation="Conditional variance forecast. alpha+beta close to 1 = high persistence. ARCH LM test for fit.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        from arch import arch_model

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            raise ValueError("garch requires 1D endog")
        fit = arch_model(y, vol="GARCH", p=int(params.get("p", 1)), q=int(params.get("q", 1))).fit(
            disp="off"
        )
        param_names = list(fit.params.index)
        result = _build_regression_result(
            method_name="garch",
            params={param_names[idx]: fit.params.iloc[idx] for idx in range(len(param_names))},
            std_errors={param_names[idx]: fit.std_err.iloc[idx] for idx in range(len(param_names))},
            p_values={param_names[idx]: fit.pvalues.iloc[idx] for idx in range(len(param_names))},
            diagnostics={
                "loglikelihood": _safe_float(getattr(fit, "loglikelihood", None)),
                "aic": _safe_float(getattr(fit, "aic", None)),
                "bic": _safe_float(getattr(fit, "bic", None)),
                "last_conditional_volatility": float(np.asarray(fit.conditional_volatility)[-1]),
            },
            model_info={"library": "arch", "estimator": "GARCH"},
            n_obs=y.shape[0],
            n_periods=y.shape[0],
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
    tags={"econometrics", "change-point"},
)
class ChangePointEstimator:
    """Change point estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("ruptures", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="change_point",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="model", default="l2"),
            ParameterSpec(name="penalty", default=3.0),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Structural break detection via rupture-based change point search.",
        tags=frozenset({"econometrics", "change-point"}),
        citations=("Truong, C. et al. (2020). Selective review of offline change point detection methods.",),
        when_to_use="Time series with suspected regime shifts or structural breaks; detect when mean/variance changes",
        typical_min_obs=50,
        output_interpretation="Breakpoint indices and segment means. Penalty controls number of breaks detected. Visual inspection recommended.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(state: TimeSeriesData, params: Mapping[str, Any]) -> dict[str, Any]:
        import ruptures as rpt

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            raise ValueError("change_point requires 1D endog")
        algo = rpt.Pelt(model=str(params.get("model", "l2"))).fit(y)
        breakpoints = [int(bp) for bp in algo.predict(pen=float(params.get("penalty", 3.0)))[:-1]]
        means = []
        start = 0
        for bp in breakpoints + [y.shape[0]]:
            means.append(float(np.mean(y[start:bp])))
            start = bp
        result = _build_regression_result(
            method_name="change_point",
            params={f"break_{idx}": bp for idx, bp in enumerate(breakpoints)},
            diagnostics={"breakpoints": breakpoints, "segment_means": means},
            model_info={"library": "ruptures", "estimator": "Pelt"},
            n_obs=y.shape[0],
            n_periods=y.shape[0],
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


__all__ = [
    "ChangePointEstimator",
    "EventStudyEstimator",
    "GARCHEstimator",
    "LocalProjectionsEstimator",
    "QuantileRegressionEstimator",
]
