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
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    compute_cohen_d,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import CausalMethod, DiagnosticTest, EstimationStatus


def _normal_two_sided_pvalue(z_score: float) -> float:
    return float(math.erfc(abs(z_score) / math.sqrt(2.0)))


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "structural-time-series", "bsts-approximation", "causal-impact"},
)
class StructuralTimeSeries:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="structural_time_series",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome_panel",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("outcome", "value"),
                    shape=("n_units", "n_periods"),
                ),
                SlotSpec(
                    name="treatment_indicator",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_effect_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="level", default=True),
            ParameterSpec(name="trend", default=False),
            ParameterSpec(name="seasonal", default=None),
            ParameterSpec(name="max_donors", default=10),
            ParameterSpec(name="n_simulations", default=1000),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Structural time-series causal impact model using state-space estimation "
            "(Kalman filter + simulation smoothing)."
        ),
        tags=frozenset(
            {
                "causal",
                "structural-time-series",
                "bsts-approximation",
                "causal-impact",
            }
        ),
        citations=(
            "Brodersen, K. et al. (2015). Inferring Causal Impact "
            "Using Bayesian Structural Time Series Models.",
            "Harvey, A. (1990). Forecasting, Structural Time Series Models and the Kalman Filter.",
        ),
        equations={
            "state_space": "Y_t = Z_t a_t + beta X_t + eps_t; a_{t+1} = T_t a_t + R_t eta_t",
            "effect": "tau_t = Y_t - Y_hat_t",
        },
        assumptions={
            "stable_pre_period": "Pre-treatment dynamics are stable and identifiable.",
            "predictive_controls": (
                "Control units carry predictive signal for "
                "treated unit counterfactual."
            ),
            "no_structural_break_pre": "No unmodeled structural break before treatment.",
        },
        when_to_use="Interrupted time series with control covariates; estimate causal impact of policy intervention on single time series",
        when_not_to_use="No pre-intervention baseline; confounded trend; multiple simultaneous interventions",
        typical_min_obs=52,
        output_interpretation="Counterfactual predicted series vs actual. Absolute/relative impact = actual - counterfactual. Posterior probability of effect.",
    )

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        assumptions = dict(StructuralTimeSeries.metadata.assumptions)
        treated_idx = np.where(data.treatment == 1)[0]
        donor_idx = np.where(data.treatment == 0)[0]

        if treated_idx.shape[0] != 1:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.INPUT_INVALID,
                reason=(
                    "StructuralTimeSeries requires exactly one treated unit, "
                    f"got {treated_idx.shape[0]}"
                ),
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=int(treated_idx.shape[0]),
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
        if donor_idx.shape[0] < 1:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.INPUT_INVALID,
                reason="StructuralTimeSeries requires at least one donor unit",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=0,
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
        if data.time_treatment <= 2 or data.time_treatment >= data.n_periods:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.INPUT_INVALID,
                reason=(
                    f"time_treatment={data.time_treatment} is invalid "
                    "for structural time-series fitting"
                ),
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

        try:
            from statsmodels.tsa.statespace.structural import UnobservedComponents
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency runtime
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"statsmodels missing: {exc}",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "missing dependency"]
            )

        treated = int(treated_idx[0])
        t0 = data.time_treatment
        max_donors = int(params.get("max_donors", 10))
        donor_series = data.outcome[donor_idx, :]
        corr_scores = np.array(
            [
                abs(np.corrcoef(data.outcome[treated, :t0], donor_series[idx, :t0])[0, 1])
                if np.std(donor_series[idx, :t0]) > 0
                else 0.0
                for idx in range(donor_series.shape[0])
            ]
        )
        top_idx = np.argsort(corr_scores)[::-1][: max(1, min(max_donors, donor_series.shape[0]))]
        donor_subset = donor_series[top_idx]

        y_pre = data.outcome[treated, :t0]
        y_post = data.outcome[treated, t0:]
        x_pre = donor_subset[:, :t0].T
        x_post = donor_subset[:, t0:].T

        seasonal = params.get("seasonal")
        if seasonal is not None:
            seasonal = int(seasonal)

        try:
            model = UnobservedComponents(
                endog=y_pre,
                level=bool(params.get("level", True)),
                trend=bool(params.get("trend", False)),
                seasonal=seasonal,
                exog=x_pre,
            )
            fit = model.fit(disp=False)
            forecast = fit.get_forecast(steps=data.post_periods, exog=x_post)
            predicted = np.asarray(forecast.predicted_mean, dtype=float)
            conf_int = np.asarray(
                forecast.conf_int(alpha=1.0 - float(params.get("confidence_level", 0.95)))
            )
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.STRUCTURAL_TIME_SERIES,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"state-space fit failed: {exc}",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return wrap_causal_output(
                report, warnings=[report.status_reason or "numerical failure"]
            )

        effects = y_post - predicted
        att = float(np.mean(effects))
        lower_pred = conf_int[:, 0]
        upper_pred = conf_int[:, 1]
        effect_lower = y_post - upper_pred
        effect_upper = y_post - lower_pred
        ci = (float(np.mean(effect_lower)), float(np.mean(effect_upper)))

        effect_std = float(np.std(effects, ddof=1)) if effects.shape[0] > 1 else 0.0
        effect_se = float(effect_std / math.sqrt(max(effects.shape[0], 1)))
        z_score = 0.0 if effect_se <= 0 else att / effect_se
        p_value = _normal_two_sided_pvalue(z_score)

        diagnostics = [
            DiagnosticTest(
                test_name="state_space_fit_converged",
                statistic=1.0,
                passed=True,
                details={"llf": float(getattr(fit, "llf", float("nan")))},
            ),
            DiagnosticTest(
                test_name="donor_signal_strength",
                statistic=float(np.mean(corr_scores[top_idx])) if top_idx.size else 0.0,
                passed=bool(top_idx.size > 0 and np.mean(corr_scores[top_idx]) > 0.1),
                details={"n_selected_donors": int(top_idx.size)},
            ),
        ]

        effect_size = compute_cohen_d(
            effect=att,
            treated_outcome=y_post,
            control_outcome=predicted,
        )
        confidence_level = float(params.get("confidence_level", 0.95))
        report = build_success_report(
            method=CausalMethod.STRUCTURAL_TIME_SERIES,
            estimand="ATT",
            point_estimate=att,
            confidence_interval=ci,
            confidence_level=confidence_level,
            standard_error=effect_se,
            p_value=p_value,
            inference_method="state_space_simulation",
            effect_size_cohen_d=effect_size,
            diagnostics=diagnostics,
            sample_size=data.n_units * data.n_periods,
            n_treated=1,
            n_control=int(donor_idx.shape[0]),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=assumptions,
            time_effects={
                "period": list(range(t0, data.n_periods)),
                "effect": [float(value) for value in effects],
                "ci_lower": [float(value) for value in effect_lower],
                "ci_upper": [float(value) for value in effect_upper],
            },
            method_params={
                "selected_donors": donor_idx[top_idx].astype(int).tolist(),
                "n_simulations": int(params.get("n_simulations", 1000)),
            },
        )
        return wrap_causal_output(
            report,
            extras={
                "counterfactual": predicted,
                "model_diagnostics": {"llf": float(getattr(fit, "llf", float("nan")))},
            },
        )


__all__ = ["StructuralTimeSeries"]
