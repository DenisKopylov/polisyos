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
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    compute_cohen_d,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.causal import CausalMethod, DiagnosticTest, EstimationStatus


def _normal_two_sided_pvalue(z_score: float) -> float:
    return float(math.erfc(abs(z_score) / math.sqrt(2.0)))


def _ols_hc1(x_mat: np.ndarray, y_vec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n_obs, n_params = x_mat.shape
    beta, *_ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
    residual = y_vec - x_mat @ beta
    xtx_inv = np.linalg.pinv(x_mat.T @ x_mat)
    meat = np.zeros((n_params, n_params), dtype=float)
    for idx in range(n_obs):
        row = x_mat[idx : idx + 1, :]
        meat += float(residual[idx] ** 2) * (row.T @ row)
    scale = float(n_obs / max(n_obs - n_params, 1))
    cov = scale * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    return beta, se


def _parallel_trend_diagnostic(
    outcome: np.ndarray,
    treatment: np.ndarray,
    *,
    t0: int,
) -> DiagnosticTest:
    if t0 < 3:
        return DiagnosticTest(
            test_name="pre_trend_parallelism",
            statistic=0.0,
            p_value=None,
            passed=True,
            details={"reason": "insufficient_pre_periods"},
        )
    treated_mask = treatment == 1
    control_mask = treatment == 0
    if not treated_mask.any() or not control_mask.any():
        return DiagnosticTest(
            test_name="pre_trend_parallelism",
            statistic=0.0,
            p_value=None,
            passed=False,
            details={"reason": "treated_or_control_group_missing"},
        )

    treated_means = outcome[treated_mask, :t0].mean(axis=0)
    control_means = outcome[control_mask, :t0].mean(axis=0)
    diff = treated_means - control_means
    timeline = np.arange(t0, dtype=float)
    x_mat = np.column_stack([np.ones(t0), timeline])
    beta, se = _ols_hc1(x_mat, diff)
    slope = float(beta[1])
    slope_se = float(se[1]) if se.shape[0] > 1 else float("inf")
    z_score = 0.0 if slope_se <= 0 else slope / slope_se
    p_value = _normal_two_sided_pvalue(z_score)
    return DiagnosticTest(
        test_name="pre_trend_parallelism",
        statistic=slope,
        p_value=p_value,
        passed=bool(p_value > 0.05),
        details={"slope_se": slope_se, "z_score": z_score},
    )


def _run_standard_did(data: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
    t0 = data.time_treatment
    treated_mask = data.treatment == 1
    control_mask = data.treatment == 0
    if not treated_mask.any() or not control_mask.any():
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.INPUT_INVALID,
            reason="DiD requires both treated and control groups",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int(treated_mask.sum()),
            n_control=int(control_mask.sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(DifferenceInDifferences.metadata.assumptions),
        )
        return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

    y = data.outcome.reshape(-1)
    post = np.tile(np.arange(data.n_periods) >= t0, data.n_units).astype(float)
    treat = np.repeat(data.treatment.astype(float), data.n_periods)
    interaction = post * treat
    x_mat = np.column_stack([np.ones_like(y), post, treat, interaction])

    beta, se = _ols_hc1(x_mat, y)
    att = float(beta[3])
    att_se = float(se[3]) if se.shape[0] > 3 else 0.0
    confidence_level = float(params.get("confidence_level", 0.95))
    z_critical = 1.959963984540054
    ci = (att - z_critical * att_se, att + z_critical * att_se)
    z_score = 0.0 if att_se <= 0 else att / att_se
    p_value = _normal_two_sided_pvalue(z_score)

    pre_diag = _parallel_trend_diagnostic(data.outcome, data.treatment, t0=t0)
    diagnostics = [pre_diag]
    if not pre_diag.passed:
        diagnostics.append(
            DiagnosticTest(
                test_name="parallel_trends_warning",
                statistic=pre_diag.statistic,
                p_value=pre_diag.p_value,
                passed=False,
                details={"message": "Parallel trends test failed on pre-treatment periods"},
            )
        )

    treated_pre = data.outcome[treated_mask, :t0].mean(axis=1)
    control_pre = data.outcome[control_mask, :t0].mean(axis=1)
    pooled_control = np.repeat(control_pre.mean(), treated_pre.shape[0])
    effect_size = compute_cohen_d(
        effect=att,
        treated_outcome=treated_pre,
        control_outcome=pooled_control,
    )

    report = build_success_report(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="ATT",
        point_estimate=att,
        confidence_interval=ci,
        confidence_level=confidence_level,
        standard_error=att_se,
        p_value=p_value,
        inference_method="asymptotic",
        effect_size_cohen_d=effect_size,
        diagnostics=diagnostics,
        sample_size=data.n_units * data.n_periods,
        n_treated=int(treated_mask.sum()),
        n_control=int(control_mask.sum()),
        pre_periods=data.pre_periods,
        post_periods=data.post_periods,
        assumptions=dict(DifferenceInDifferences.metadata.assumptions),
        method_params={
            "staggered": False,
            "cov_type": str(params.get("cov_type", "HC1")),
            "delta_hat": att,
        },
    )
    return wrap_causal_output(report)


def _cohort_time_att(
    data: PanelObservationalData,
    *,
    control_group: str,
    anticipation: int,
) -> tuple[np.ndarray, np.ndarray]:
    assert data.treatment_timing is not None
    timing = data.treatment_timing.astype(int)
    valid_groups = sorted(int(value) for value in np.unique(timing) if value >= 0)
    att_values: list[float] = []
    weights: list[float] = []

    for group_start in valid_groups:
        if group_start <= 0 or group_start >= data.n_periods:
            continue
        group_mask = timing == group_start
        if not group_mask.any():
            continue
        baseline_t = group_start - 1 - anticipation
        if baseline_t < 0:
            continue
        for t in range(group_start, data.n_periods):
            if control_group == "not_yet_treated":
                control_mask = (timing == -1) | (timing > t)
            else:
                control_mask = timing == -1
            if not control_mask.any():
                continue
            treated_delta = (
                data.outcome[group_mask, t].mean() - data.outcome[group_mask, baseline_t].mean()
            )
            control_delta = (
                data.outcome[control_mask, t].mean() - data.outcome[control_mask, baseline_t].mean()
            )
            att_values.append(float(treated_delta - control_delta))
            weights.append(float(group_mask.sum()))

    if not att_values:
        return np.array([], dtype=float), np.array([], dtype=float)
    return np.asarray(att_values, dtype=float), np.asarray(weights, dtype=float)


def _run_staggered_did(data: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
    if data.treatment_timing is None:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.INPUT_INVALID,
            reason="staggered DiD requires treatment_timing array",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int((data.treatment == 1).sum()),
            n_control=int((data.treatment == 0).sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(DifferenceInDifferences.metadata.assumptions),
        )
        return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

    control_group = str(params.get("control_group", "never_treated"))
    anticipation = int(params.get("anticipation", 0))
    atts, weights = _cohort_time_att(
        data,
        control_group=control_group,
        anticipation=anticipation,
    )
    if atts.size == 0:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.ASSUMPTION_FAILED,
            reason="unable to construct valid staggered ATT(g,t) cells",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int((data.treatment == 1).sum()),
            n_control=int((data.treatment == 0).sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(DifferenceInDifferences.metadata.assumptions),
        )
        return wrap_causal_output(report, warnings=[report.status_reason or "assumption failed"])

    weights = weights / weights.sum()
    att = float(np.sum(atts * weights))

    rng = params["__rng__"]
    n_bootstrap = int(params.get("n_bootstrap", 1000))
    boot = np.zeros(n_bootstrap, dtype=float)
    idx = np.arange(atts.shape[0])
    for b in range(n_bootstrap):
        sample = rng.choice(idx, size=idx.shape[0], replace=True)
        boot[b] = float(np.sum(atts[sample] * weights[sample] / np.sum(weights[sample])))
    confidence_level = float(params.get("confidence_level", 0.95))
    ci = bootstrap_ci(boot, confidence_level=confidence_level)
    p_value = float((np.sum(np.abs(boot) >= abs(att)) + 1) / (n_bootstrap + 1))

    pre_diag = _parallel_trend_diagnostic(data.outcome, data.treatment, t0=data.time_treatment)
    diagnostics = [pre_diag]
    effect_size = compute_cohen_d(
        effect=att,
        treated_outcome=atts,
        control_outcome=np.zeros_like(atts),
    )
    report = build_success_report(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="ATT",
        point_estimate=att,
        confidence_interval=ci,
        confidence_level=confidence_level,
        p_value=p_value,
        inference_method="bootstrap",
        n_bootstrap_samples=n_bootstrap,
        effect_size_cohen_d=effect_size,
        diagnostics=diagnostics,
        sample_size=data.n_units * data.n_periods,
        n_treated=int((data.treatment == 1).sum()),
        n_control=int((data.treatment == 0).sum()),
        pre_periods=data.pre_periods,
        post_periods=data.post_periods,
        assumptions=dict(DifferenceInDifferences.metadata.assumptions),
        method_params={
            "staggered": True,
            "control_group": control_group,
            "anticipation": anticipation,
            "n_cells": int(atts.shape[0]),
        },
    )
    return wrap_causal_output(report)


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "quasi-experimental", "difference-in-differences"},
)
class DifferenceInDifferences:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="difference_in_differences",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome_panel",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("outcome", "value"),
                ),
                SlotSpec(
                    name="treatment_indicator",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
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
            ParameterSpec(name="staggered", default=False),
            ParameterSpec(name="control_group", default="never_treated"),
            ParameterSpec(name="n_bootstrap", default=1000),
            ParameterSpec(name="cov_type", default="HC1"),
            ParameterSpec(name="cluster_var", default=None),
            ParameterSpec(name="anticipation", default=0),
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
            "Difference-in-Differences estimator with standard 2x2 mode and "
            "staggered adoption aggregation (Callaway-Sant'Anna style)."
        ),
        tags=frozenset({"causal", "quasi-experimental", "difference-in-differences"}),
        citations=(
            "Callaway, B., & Sant'Anna, P. (2021). "
            "Difference-in-Differences with Multiple Time Periods.",
            "Angrist, J., & Pischke, J. (2009). Mostly Harmless Econometrics.",
        ),
        equations={
            "did_2x2": "ATT = (Y_treated_post - Y_treated_pre) - (Y_control_post - Y_control_pre)",
            "regression": "Y_it = a + b*Post_t + c*Treat_i + d*(Post_t*Treat_i) + e_it",
        },
        assumptions={
            "parallel_trends": "Untreated potential outcomes follow parallel trends.",
            "no_anticipation": (
                "No treatment effect before treatment start "
                "(unless explicitly modeled)."
            ),
            "stable_composition": "Group composition is stable over analysis horizon.",
        },
    )

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        staggered = bool(params.get("staggered", False))
        if staggered:
            return _run_staggered_did(data, params)
        return _run_standard_did(data, params)


__all__ = ["DifferenceInDifferences"]
