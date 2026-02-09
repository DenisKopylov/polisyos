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
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.ir.analytics.causal import CausalMethod, DiagnosticTest, EstimationStatus


def _normal_two_sided_pvalue(z_score: float) -> float:
    return float(math.erfc(abs(z_score) / math.sqrt(2.0)))


def _kernel_weights(distance: np.ndarray, *, kernel: str) -> np.ndarray:
    abs_distance = np.abs(distance)
    if kernel == "uniform":
        return (abs_distance <= 1.0).astype(float)
    if kernel == "epanechnikov":
        weights = 0.75 * (1.0 - abs_distance**2)
        weights[abs_distance > 1.0] = 0.0
        return weights
    weights = 1.0 - abs_distance
    weights[abs_distance > 1.0] = 0.0
    return weights


def _auto_bandwidth(x: np.ndarray) -> float:
    # Heuristic IK-like bandwidth used for MVP implementation.
    std = float(np.std(x, ddof=1))
    n_obs = x.shape[0]
    return max(1e-6, 1.84 * std * (n_obs ** (-1.0 / 5.0)))


def _fit_local_polynomial(
    x_centered: np.ndarray,
    y_vec: np.ndarray,
    *,
    cutoff_side: str,
    poly_order: int,
    kernel: str,
    bandwidth: float,
) -> tuple[float, float, float]:
    if cutoff_side == "right":
        mask = x_centered >= 0
    else:
        mask = x_centered < 0

    x_side = x_centered[mask]
    y_side = y_vec[mask]
    if x_side.shape[0] < max(10, poly_order + 2):
        raise ValueError(f"insufficient observations on {cutoff_side} side")

    distance = x_side / bandwidth
    weights = _kernel_weights(distance, kernel=kernel)
    valid = weights > 0
    x_side = x_side[valid]
    y_side = y_side[valid]
    weights = weights[valid]

    if x_side.shape[0] < max(10, poly_order + 2):
        raise ValueError(f"insufficient weighted observations on {cutoff_side} side")

    design = [np.ones_like(x_side)]
    for order in range(1, poly_order + 1):
        design.append(x_side**order)
    x_mat = np.column_stack(design)

    w = np.diag(weights)
    xtwx = x_mat.T @ w @ x_mat
    xtwy = x_mat.T @ w @ y_side
    beta = np.linalg.pinv(xtwx) @ xtwy
    residual = y_side - x_mat @ beta
    dof = max(x_side.shape[0] - x_mat.shape[1], 1)
    sigma2 = float((weights * residual**2).sum() / dof)
    cov = sigma2 * np.linalg.pinv(xtwx)
    intercept = float(beta[0])
    intercept_se = float(np.sqrt(max(cov[0, 0], 0.0)))
    return intercept, intercept_se, float(x_side.shape[0])


def _manipulation_test(x_centered: np.ndarray, bandwidth: float) -> DiagnosticTest:
    eps = bandwidth / 5.0
    left_count = int(np.sum((x_centered < 0.0) & (x_centered >= -eps)))
    right_count = int(np.sum((x_centered >= 0.0) & (x_centered <= eps)))
    log_ratio = math.log((right_count + 0.5) / (left_count + 0.5))
    se = math.sqrt(1.0 / (right_count + 0.5) + 1.0 / (left_count + 0.5))
    z_score = 0.0 if se <= 0 else log_ratio / se
    p_value = _normal_two_sided_pvalue(z_score)
    return DiagnosticTest(
        test_name="mcCrary_density_discontinuity",
        statistic=log_ratio,
        p_value=p_value,
        passed=bool(p_value > 0.05),
        details={
            "left_count": left_count,
            "right_count": right_count,
            "z_score": z_score,
            "window_eps": eps,
        },
    )


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "quasi-experimental", "regression-discontinuity"},
)
class RegressionDiscontinuity:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="regression_discontinuity",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="running_variable",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("forcing", "value"),
                ),
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
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
            ParameterSpec(name="polynomial_order", default=1),
            ParameterSpec(name="bandwidth", default=None),
            ParameterSpec(name="kernel", default="triangular"),
            ParameterSpec(name="bias_correction", default=True),
            ParameterSpec(name="manipulation_test", default=True),
            ParameterSpec(name="n_bins_density", default=50),
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
            "Regression Discontinuity Design with local polynomial regression at cutoff "
            "and manipulation diagnostic."
        ),
        tags=frozenset({"causal", "quasi-experimental", "regression-discontinuity"}),
        citations=(
            "Imbens, G., & Kalyanaraman, K. (2012). "
            "Optimal Bandwidth Choice for the RDD Estimator.",
            "Calonico, S., Cattaneo, M., & Titiunik, R. (2014). Robust Nonparametric CIs for RDD.",
            "McCrary, J. (2008). Manipulation of the Running Variable in RDD.",
        ),
        equations={
            "tau": "tau_hat = lim_{x->c+} E[Y|X=x] - lim_{x->c-} E[Y|X=x]",
            "kernel": "K_h(x) = K((x-c)/h)",
        },
        assumptions={
            "continuity": "Potential outcomes are continuous at the cutoff.",
            "no_precise_manipulation": (
                "Units cannot precisely manipulate the running variable at cutoff."
            ),
            "local_randomization": "Near cutoff assignment approximates randomization.",
        },
    )

    @staticmethod
    def pure_step(state: RDDObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, RDDObservationalData)
            else RDDObservationalData.model_validate(state)
        )
        x_centered = data.running_variable - float(data.cutoff)
        poly_order = int(params.get("polynomial_order", 1))
        kernel = str(params.get("kernel", "triangular")).lower()
        bandwidth = params.get("bandwidth")
        bandwidth_value = float(bandwidth) if bandwidth is not None else _auto_bandwidth(x_centered)
        if bandwidth_value <= 0:
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=f"invalid bandwidth={bandwidth_value}",
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=int(np.sum(x_centered >= 0)),
                n_control=int(np.sum(x_centered < 0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

        try:
            right_mu, right_se, right_n = _fit_local_polynomial(
                x_centered,
                data.outcome,
                cutoff_side="right",
                poly_order=poly_order,
                kernel=kernel,
                bandwidth=bandwidth_value,
            )
            left_mu, left_se, left_n = _fit_local_polynomial(
                x_centered,
                data.outcome,
                cutoff_side="left",
                poly_order=poly_order,
                kernel=kernel,
                bandwidth=bandwidth_value,
            )
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"RDD local polynomial failed: {exc}",
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=int(np.sum(x_centered >= 0)),
                n_control=int(np.sum(x_centered < 0)),
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "fit failure"])

        tau = float(right_mu - left_mu)
        tau_se = float(math.sqrt(right_se**2 + left_se**2))
        confidence_level = float(params.get("confidence_level", 0.95))
        z_critical = 1.959963984540054
        ci = (tau - z_critical * tau_se, tau + z_critical * tau_se)
        z_score = 0.0 if tau_se <= 0 else tau / tau_se
        p_value = _normal_two_sided_pvalue(z_score)

        diagnostics: list[DiagnosticTest] = [
            DiagnosticTest(
                test_name="effective_sample_size",
                statistic=float(right_n + left_n),
                passed=bool((right_n >= 20) and (left_n >= 20)),
                details={"n_left": left_n, "n_right": right_n, "bandwidth": bandwidth_value},
            )
        ]
        if bool(params.get("manipulation_test", True)):
            diagnostics.append(_manipulation_test(x_centered, bandwidth_value))

        effect_size = compute_cohen_d(
            effect=tau,
            treated_outcome=data.outcome[x_centered >= 0],
            control_outcome=data.outcome[x_centered < 0],
        )

        report = build_success_report(
            method=CausalMethod.REGRESSION_DISCONTINUITY,
            estimand="LATE",
            point_estimate=tau,
            confidence_interval=ci,
            confidence_level=confidence_level,
            standard_error=tau_se,
            p_value=p_value,
            inference_method="asymptotic",
            effect_size_cohen_d=effect_size,
            diagnostics=diagnostics,
            sample_size=data.sample_size,
            n_treated=int(np.sum(x_centered >= 0)),
            n_control=int(np.sum(x_centered < 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            method_params={
                "bandwidth": bandwidth_value,
                "kernel": kernel,
                "polynomial_order": poly_order,
                "bias_correction": bool(params.get("bias_correction", True)),
            },
        )
        return wrap_causal_output(report)


__all__ = ["RegressionDiscontinuity"]
