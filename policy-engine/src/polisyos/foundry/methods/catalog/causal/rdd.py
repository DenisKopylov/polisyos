"""Estimate cutoff-local causal effects with regression-discontinuity designs."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from statistics import NormalDist
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
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


def _normal_critical_value(confidence_level: float) -> float:
    """Return the two-sided normal critical value for a validated level."""

    level = float(confidence_level)
    if not math.isfinite(level) or not 0.0 < level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    return float(NormalDist().inv_cdf((1.0 + level) / 2.0))


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

    weighted_design = weights[:, None] * x_mat
    rank = int(np.linalg.matrix_rank(weighted_design))
    if rank < x_mat.shape[1]:
        raise ValueError(
            f"rank deficient design on {cutoff_side} side: "
            f"rank={rank} < parameters={x_mat.shape[1]}"
        )

    xtwx = x_mat.T @ weighted_design
    xtwy = x_mat.T @ (weights * y_side)
    xtwx_pinv = np.linalg.pinv(xtwx)
    beta = xtwx_pinv @ xtwy
    residual = y_side - x_mat @ beta
    dof = max(x_side.shape[0] - x_mat.shape[1], 1)
    sigma2 = float((weights * residual**2).sum() / dof)
    cov = sigma2 * xtwx_pinv
    intercept = float(beta[0])
    intercept_se = float(np.sqrt(max(cov[0, 0], 0.0)))
    return intercept, intercept_se, float(x_side.shape[0])


def _fit_rbc_polynomial(
    x_centered: np.ndarray,
    y_vec: np.ndarray,
    *,
    cutoff_side: str,
    poly_order: int,
    bias_order: int,
    kernel: str,
    bandwidth: float,
    bias_bandwidth: float,
) -> tuple[float, float, float, float, int, int]:
    """Compute sharp-RD CCT corrected weights and their HC0 variance on one side.

    This is a clean-room specialization of CCT (2014), Appendix A.1/A.2,
    Theorem A.1(V), for derivative zero, q=p+1 and fixed h/b. With scaled
    polynomial bases, a=e0' inv(Rp'Wh Rp) Rp'Wh and
    d=e(p+1)' inv(Rq'Wb Rq) Rq'Wb. The corrected weight is a-L*d, where
    L=(a @ (x/h)**(p+1))*(h/b)**(p+1). Squaring that combined weight
    includes the bias-estimation variance and its covariance with the
    conventional estimate. HC0 uses q-fit residuals, including observations
    in the union of the h and b windows; only small Gram matrices are formed.
    """
    side = x_centered >= 0 if cutoff_side == "right" else x_centered < 0
    x_side, y_side = x_centered[side], y_vec[side]
    wh = _kernel_weights(x_side / bandwidth, kernel=kernel)
    wb = _kernel_weights(x_side / bias_bandwidth, kernel=kernel)
    union = (wh > 0) | (wb > 0)
    x_side, y_side, wh, wb = x_side[union], y_side[union], wh[union], wb[union]
    n_h, n_b = int(np.sum(wh > 0)), int(np.sum(wb > 0))
    if min(n_h, n_b) < max(10, bias_order + 2):
        raise ValueError(f"insufficient RBC weighted support on {cutoff_side} side")

    rp = np.vander(x_side / bandwidth, poly_order + 1, increasing=True)
    rq = np.vander(x_side / bias_bandwidth, bias_order + 1, increasing=True)
    for design, weights in ((rp, wh), (rq, wb)):
        if np.linalg.matrix_rank(np.sqrt(weights)[:, None] * design) < design.shape[1]:
            raise ValueError(f"rank deficient RBC design on {cutoff_side} side")
    map_p = np.linalg.solve(rp.T @ (wh[:, None] * rp), rp.T * wh)
    map_q = np.linalg.solve(rq.T @ (wb[:, None] * rq), rq.T * wb)
    a = map_p[0]
    leading = float(a @ ((x_side / bandwidth) ** (poly_order + 1)))
    leading *= (bandwidth / bias_bandwidth) ** (poly_order + 1)
    bias_weights = leading * map_q[poly_order + 1]
    corrected_weights = a - bias_weights
    conventional = float(a @ y_side)
    corrected = float(corrected_weights @ y_side)
    residual_p = y_side - rp @ (map_p @ y_side)
    residual_q = y_side - rq @ (map_q @ y_side)
    variance_us = float(np.sum((a * residual_p) ** 2))
    variance_rb = float(np.sum((corrected_weights * residual_q) ** 2))
    values = np.array([conventional, corrected, variance_us, variance_rb])
    if not np.isfinite(values).all():
        raise ValueError("non-finite RBC fit or variance")
    return conventional, corrected, variance_us, variance_rb, n_h, n_b


def _rdd_input_digest(data: RDDObservationalData) -> str:
    """Bind admitted row order, outcome, running variable and cutoff bytes."""
    digest = hashlib.sha256(b"policyos.sharp-rdd.input.v1\0")
    digest.update(np.asarray([data.sample_size], dtype="<i8").tobytes())
    for array in (data.running_variable, data.outcome, [data.cutoff]):
        digest.update(np.asarray(array, dtype="<f8").tobytes())
    return digest.hexdigest()


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
    """Estimate a local treatment jump under continuity and no precise manipulation; avoid sparse support near the threshold."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="regression_discontinuity",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="running_variable",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("forcing", "value"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_obs",),
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
            ParameterSpec(name="bias_correction", default=False),
            ParameterSpec(name="bias_bandwidth", default=None),
            ParameterSpec(name="bias_polynomial_order", default=None),
            ParameterSpec(name="vce", default="hc0"),
            ParameterSpec(name="masspoints", default="off"),
            ParameterSpec(name="bandwidth_selector", default="fixed"),
            ParameterSpec(name="design", default="sharp"),
            ParameterSpec(name="manipulation_test", default=True),
            ParameterSpec(name="n_bins_density", default=50),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
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
        when_to_use="Sharp RDD with a forcing/running variable and clear cutoff; fixed-bandwidth CCT RBC or separate conventional local polynomial",
        when_not_to_use="No clear discontinuity; manipulation of running variable; small bandwidth yields <30 obs",
        typical_min_obs=100,
        output_interpretation="RD estimate: LATE at the cutoff. Positive = treatment increases outcome at threshold.",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> RDDObservationalData:
        """Merge graph-bound vectors with the existing typed RDD context.

        The cutoff is part of RDDObservationalData because it defines treatment
        assignment. It is never inferred or defaulted from the vectors.
        """
        if isinstance(fallback_state, RDDObservationalData):
            payload = fallback_state.model_dump(mode="python")
        elif isinstance(fallback_state, Mapping):
            payload = dict(fallback_state)
        elif fallback_state is None:
            payload = {}
        else:
            raise TypeError("RDD input state must be RDDObservationalData or a mapping")
        payload.update(bound_inputs)
        return RDDObservationalData.model_validate(payload)

    @staticmethod
    def pure_step(state: RDDObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, RDDObservationalData)
            else RDDObservationalData.model_validate(state)
        )
        x_centered = data.running_variable - float(data.cutoff)
        bias_correction = params.get("bias_correction", False)
        treated_count = int(np.sum(x_centered >= 0))
        control_count = int(np.sum(x_centered < 0))
        if not isinstance(bias_correction, bool):
            reason = "bias_correction must be a boolean"
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=reason,
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
                method_params={"bias_correction": bias_correction},
                metadata={"capability": "invalid_bias_correction_flag"},
            )
            return wrap_causal_output(report, warnings=[reason])

        polynomial_order = params.get("polynomial_order", 1)
        if (
            isinstance(polynomial_order, bool)
            or not isinstance(polynomial_order, int)
            or polynomial_order not in {1, 2}
        ):
            reason = "polynomial_order must be an integer in {1, 2}"
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=reason,
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
                method_params={"polynomial_order": polynomial_order},
                metadata={"capability": "unsupported_polynomial_order"},
            )
            return wrap_causal_output(report, warnings=[reason])

        kernel_value = params.get("kernel", "triangular")
        if not isinstance(kernel_value, str) or kernel_value.lower() not in {
            "triangular",
            "epanechnikov",
            "uniform",
        }:
            reason = "kernel must be one of: triangular, epanechnikov, uniform"
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=reason,
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
                method_params={"kernel": kernel_value},
                metadata={"capability": "unsupported_kernel"},
            )
            return wrap_causal_output(report, warnings=[reason])
        kernel = kernel_value.lower()

        design = params.get("design", "sharp")
        if design != "sharp" or params.get("fuzzy") is not None:
            reason = "fuzzy RDD requires typed treatment/compliance input; only sharp is supported"
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason=reason,
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
                method_params={"bias_correction": bias_correction, "design": str(design)},
                metadata={"capability": "unsupported_fuzzy_treatment_input"},
            )
            return wrap_causal_output(report, warnings=[reason])

        poly_order = polynomial_order
        bandwidth = params.get("bandwidth")
        try:
            if isinstance(bandwidth, bool):
                raise ValueError("bandwidth must be finite and positive")
            if bias_correction and bandwidth is None:
                raise ValueError("RBC requires explicit fixed bandwidth and bias_bandwidth")
            bandwidth_value = (
                float(bandwidth) if bandwidth is not None else _auto_bandwidth(x_centered)
            )
        except (TypeError, ValueError) as exc:
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
        if not math.isfinite(bandwidth_value) or bandwidth_value <= 0:
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=f"invalid bandwidth={bandwidth_value}",
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

        bias_order = poly_order + 1
        bias_bandwidth_value = 0.0
        try:
            confidence_level = float(params.get("confidence_level", 0.95))
            z_critical = _normal_critical_value(confidence_level)
            if bias_correction:
                requested_q = params.get("bias_polynomial_order")
                if requested_q is not None:
                    if isinstance(requested_q, bool) or not isinstance(requested_q, int):
                        raise ValueError("bias_polynomial_order must be p+1")
                    bias_order = requested_q
                if bias_order != poly_order + 1:
                    raise ValueError("bias_polynomial_order must be p+1")
                b = params.get("bias_bandwidth")
                if isinstance(b, bool) or b is None:
                    raise ValueError("RBC requires finite positive bias_bandwidth")
                bias_bandwidth_value = float(b)
                if not math.isfinite(bias_bandwidth_value) or bias_bandwidth_value <= 0:
                    raise ValueError("RBC requires finite positive bias_bandwidth")
                for key, value in (
                    ("vce", "hc0"),
                    ("masspoints", "off"),
                    ("bandwidth_selector", "fixed"),
                ):
                    if params.get(key, value) != value:
                        raise ValueError(f"RBC supports only {key}={value}")
                if params.get("cluster") is not None:
                    raise ValueError("RBC HC0 profile does not support clustering")
        except (TypeError, ValueError) as exc:
            report = build_failure_report(
                method=CausalMethod.REGRESSION_DISCONTINUITY,
                status=EstimationStatus.INPUT_INVALID,
                reason=str(exc),
                estimand="LATE",
                sample_size=data.sample_size,
                n_treated=treated_count,
                n_control=control_count,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            )
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

        rbc_params: dict[str, Any] = {}
        try:
            if bias_correction:
                if np.unique(data.running_variable).size != data.sample_size:
                    raise ValueError("RBC first profile requires unique running-variable support")
                sides = [
                    _fit_rbc_polynomial(
                        x_centered,
                        data.outcome,
                        cutoff_side=side,
                        poly_order=poly_order,
                        bias_order=bias_order,
                        kernel=kernel,
                        bandwidth=bandwidth_value,
                        bias_bandwidth=bias_bandwidth_value,
                    )
                    for side in ("left", "right")
                ]
                left, right = sides
                tau_us = right[0] - left[0]
                tau_bc = right[1] - left[1]
                se_us = math.sqrt(left[2] + right[2])
                se_rb = math.sqrt(left[3] + right[3])
                left_mu, right_mu = left[1], right[1]
                left_se, right_se = math.sqrt(left[3]), math.sqrt(right[3])
                left_n, right_n = left[4], right[4]
                rbc_params = {
                    "profile": "sharp_cct_rbc_hc0_fixed",
                    "producer": "PolicyOS clean-room CCT2014 weights",
                    "tau_us": tau_us,
                    "tau_bc": tau_bc,
                    "bias": tau_us - tau_bc,
                    "se_us": se_us,
                    "se_rb": se_rb,
                    "bias_polynomial_order": bias_order,
                    "bias_bandwidth": bias_bandwidth_value,
                    "h": [bandwidth_value, bandwidth_value],
                    "b": [bias_bandwidth_value, bias_bandwidth_value],
                    "p": poly_order,
                    "q": bias_order,
                    "vce": "hc0",
                    "masspoints": "off",
                    "bandwidth_selector": "fixed",
                    "cluster": None,
                    "design": "sharp",
                    "cutoff": float(data.cutoff),
                    "n_bias_left": left[5],
                    "n_bias_right": right[5],
                    "input_sha256": _rdd_input_digest(data),
                    "confidence_level": confidence_level,
                    "authority_limit": "Sharp iid asymptotic profile; real-data continuity, no manipulation and bandwidth validity not established by computation",
                }
            else:
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
            n_treated=treated_count,
            n_control=control_count,
            pre_periods=0,
            post_periods=0,
            assumptions=dict(RegressionDiscontinuity.metadata.assumptions),
            method_params={
                "profile": "sharp_conventional_local_polynomial",
                "variance_profile": "weighted_residual_homoskedastic"
                if not bias_correction
                else "cct_corrected_weights_hc0",
                "bandwidth_selector": "heuristic_ik_like" if bandwidth is None else "fixed",
                "treatment_assignment": "running_variable>=cutoff",
                "bandwidth": bandwidth_value,
                "kernel": kernel,
                "polynomial_order": poly_order,
                "bias_correction": bias_correction,
                "confidence_procedure": "cct_rbc_normal_two_sided"
                if bias_correction
                else "normal_two_sided",
                "critical_value": z_critical,
                **rbc_params,
            },
        )
        return wrap_causal_output(report)


__all__ = ["RegressionDiscontinuity"]
