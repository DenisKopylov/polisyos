"""Estimate treated-unit counterfactuals with donor-weight synthetic control."""

from __future__ import annotations

import math
from collections.abc import Mapping
from fractions import Fraction
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
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    compute_cohen_d,
    compute_rmspe,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import (
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    PlaceboResult,
)


def _fit_scm_weights(
    y_treated_pre: np.ndarray,
    y_donors_pre: np.ndarray,
    *,
    method: str,
    max_iter: int,
    tolerance: float,
    covariates_weight: float,
    x_treated: np.ndarray | None = None,
    x_donors: np.ndarray | None = None,
) -> tuple[np.ndarray, bool, str]:
    """Verify a simplex solution to the original weighted convex quadratic.

    The optimizer sees one common normalization of the full objective. Admission
    independently checks nonnegative returned weights, unit sum to tolerance,
    and an exact-binary64 convex gap at the weights' exact simplex projection.
    The gap bounds suboptimality of the original objective divided by
    ``max(abs(active data))**2 * max(1, covariates_weight)``. This is a numerical
    computation contract, not evidence of donor overlap or causal validity.
    """
    try:
        from scipy.optimize import minimize
    except ModuleNotFoundError as exc:
        return np.array([]), False, f"scipy missing: {exc}"

    def refuse(message: str) -> tuple[np.ndarray, bool, str]:
        return np.array([]), False, message

    if method != "SLSQP":
        return refuse("verified SCM solver requires SLSQP")
    if not math.isfinite(tolerance) or not 0.0 < tolerance < 1.0 or max_iter < 1:
        return refuse("invalid verified SCM solver tolerance or iteration limit")
    if not math.isfinite(covariates_weight) or covariates_weight < 0.0:
        return refuse("invalid covariate weight")
    y = np.asarray(y_treated_pre, dtype=float)
    donors = np.asarray(y_donors_pre, dtype=float)
    if y.ndim != 1 or not y.size or donors.ndim != 2 or donors.shape[1] != y.size:
        return refuse("invalid outcome matrix shape")
    n_donors = donors.shape[0]
    if not n_donors:
        return refuse("no donor units available")
    active_covariates = covariates_weight > 0.0
    if active_covariates and (x_treated is None or x_donors is None):
        return refuse("requested covariate objective block is incomplete")
    covariates = None
    covariate_donors = None
    arrays = [y, donors]
    if active_covariates:
        covariates = np.asarray(x_treated, dtype=float)
        covariate_donors = np.asarray(x_donors, dtype=float)
        if (
            covariates.ndim != 1
            or not covariates.size
            or covariate_donors.shape != (n_donors, covariates.size)
        ):
            return refuse("invalid covariate matrix shape")
        arrays.extend([covariates, covariate_donors])
    if not all(np.isfinite(array).all() for array in arrays):
        return refuse("non-finite SCM objective input")
    scale = max(float(np.max(np.abs(array))) for array in arrays)
    scale = scale if scale else 1.0
    weight_scale = max(1.0, covariates_weight) if active_covariates else 1.0
    outcome_factor = 1.0 / math.sqrt(weight_scale)
    targets = [y / scale * (outcome_factor / math.sqrt(y.size))]
    columns = [donors / scale * (outcome_factor / math.sqrt(y.size))]
    if active_covariates:
        factor = math.sqrt(covariates_weight) / math.sqrt(weight_scale)
        targets.append(covariates / scale * (factor / math.sqrt(covariates.size)))
        columns.append(covariate_donors / scale * (factor / math.sqrt(covariates.size)))
    target = np.concatenate(targets)
    matrix = np.concatenate(columns, axis=1)

    def objective(weights: np.ndarray) -> float:
        residual = weights @ matrix - target
        return float(residual @ residual)

    def gradient(weights: np.ndarray) -> np.ndarray:
        return 2.0 * (matrix @ (weights @ matrix - target))

    result = minimize(
        objective,
        np.full(n_donors, 1.0 / n_donors),
        jac=gradient,
        method=method,
        bounds=[(0.0, 1.0)] * n_donors,
        constraints=[
            {
                "type": "eq",
                "fun": lambda w: float(np.sum(w) - 1.0),
                "jac": lambda w: np.ones(n_donors),
            }
        ],
        options={"maxiter": max_iter, "ftol": tolerance * tolerance},
    )
    try:
        weights = np.asarray(result.x, dtype=float)
    except (AttributeError, TypeError, ValueError):
        return refuse("optimizer returned invalid donor weight vector")
    if weights.shape != (n_donors,) or not np.isfinite(weights).all():
        return refuse("optimizer returned invalid donor weight vector")
    if (
        float(np.min(weights)) < -tolerance
        or float(np.max(weights)) > 1.0 + tolerance
        or abs(math.fsum(map(float, weights)) - 1.0) > tolerance
    ):
        return refuse("optimizer simplex feasibility check failed")
    weights = np.clip(weights, 0.0, 1.0)
    weights /= math.fsum(map(float, weights))
    rational_weights = [Fraction.from_float(float(value)) for value in weights]
    weight_sum = sum(rational_weights, Fraction(0))
    if abs(weight_sum - 1) > Fraction.from_float(tolerance):
        return refuse("emitted simplex feasibility check failed")
    rational_weights = [value / weight_sum for value in rational_weights]
    exact_gradient = [Fraction(0) for _ in range(n_donors)]
    blocks = [(y, donors, Fraction(1))]
    if active_covariates:
        blocks.append((covariates, covariate_donors, Fraction.from_float(covariates_weight)))
    for values, predictors, multiplier in blocks:
        for index, value in enumerate(values):
            column = [Fraction.from_float(float(item)) for item in predictors[:, index]]
            residual = sum(
                (weight * item for weight, item in zip(rational_weights, column, strict=True)),
                Fraction(0),
            ) - Fraction.from_float(float(value))
            for donor, item in enumerate(column):
                exact_gradient[donor] += 2 * multiplier * item * residual / len(values)
    gap = sum(
        (weight * value for weight, value in zip(rational_weights, exact_gradient, strict=True)),
        Fraction(0),
    ) - min(exact_gradient)
    normalizer = Fraction.from_float(scale) ** 2 * Fraction.from_float(weight_scale)
    if gap > Fraction.from_float(tolerance) * normalizer:
        return refuse(f"optimizer convex optimality gap check failed: {float(gap / normalizer)}")
    return weights, True, ""


def _fit_ridge_correction(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Fit a tiny ridge regression used by the augmented SCM correction."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    X_aug = np.column_stack([np.ones(X.shape[0]), X])
    reg = alpha * np.eye(X_aug.shape[1])
    reg[0, 0] = 0.0
    beta, *_ = np.linalg.lstsq(X_aug.T @ X_aug + reg, X_aug.T @ y, rcond=None)
    return beta


def _predict_ridge_correction(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    X_aug = np.column_stack([np.ones(X.shape[0]), X])
    return X_aug @ beta


def augmented_synthetic_control(
    y_treated: np.ndarray,
    y_donors: np.ndarray,
    *,
    t0: int,
    donor_weights: np.ndarray,
    ridge_alpha: float = 1.0,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Augmented synthetic control with ridge bias correction and jackknife CI."""
    y_treated = np.asarray(y_treated, dtype=float)
    y_donors = np.asarray(y_donors, dtype=float)
    donor_weights = np.asarray(donor_weights, dtype=float)

    if y_donors.ndim != 2:
        raise ValueError("y_donors must be a 2D array")
    if y_treated.ndim != 1:
        raise ValueError("y_treated must be a 1D array")

    def _core(
        y_treated_local: np.ndarray, y_donors_local: np.ndarray, weights_local: np.ndarray
    ) -> dict[str, Any]:
        base_cf_local = weights_local @ y_donors_local
        residual_pre_local = y_treated_local[:t0] - base_cf_local[:t0]
        correction_beta_local = _fit_ridge_correction(
            y_donors_local[:, :t0].T,
            residual_pre_local,
            alpha=ridge_alpha,
        )
        correction_all_local = _predict_ridge_correction(y_donors_local.T, correction_beta_local)
        correction_all_local = correction_all_local - float(np.mean(correction_all_local[:t0]))
        augmented_cf_local = base_cf_local + correction_all_local
        effects_local = y_treated_local - augmented_cf_local
        att_local = float(np.mean(effects_local[t0:]))
        return {
            "att": att_local,
            "counterfactual": augmented_cf_local,
            "effects": effects_local,
            "correction_beta": correction_beta_local,
            "base_counterfactual": base_cf_local,
        }

    core = _core(y_treated, y_donors, donor_weights)
    att = float(core["att"])
    augmented_cf = core["counterfactual"]
    effects = core["effects"]
    correction_beta = core["correction_beta"]
    base_cf = core["base_counterfactual"]

    jackknife: list[float] = []
    n_donors = y_donors.shape[0]
    if n_donors >= 3:
        for leave_out in range(n_donors):
            donor_mask = np.array([j != leave_out for j in range(n_donors)], dtype=bool)
            if donor_mask.sum() < 2:
                continue
            subset_weights, ok, _ = _fit_scm_weights(
                y_treated_pre=y_treated[:t0],
                y_donors_pre=y_donors[donor_mask, :t0],
                method="SLSQP",
                max_iter=1000,
                tolerance=1e-8,
                covariates_weight=0.0,
            )
            if not ok:
                continue
            subset_result = _core(y_treated, y_donors[donor_mask], subset_weights)
            jackknife.append(float(subset_result["att"]))

    if len(jackknife) >= 2:
        jack = np.asarray(jackknife, dtype=float)
        jack_mean = float(np.mean(jack))
        jack_se = float(
            np.sqrt(max((len(jack) - 1) / len(jack) * np.sum((jack - jack_mean) ** 2), 0.0))
        )
        ci = (att - 1.96 * jack_se, att + 1.96 * jack_se)
        inference_method = "jackknife"
    else:
        ci = bootstrap_ci(effects[t0:], confidence_level=confidence_level)
        inference_method = "bootstrap"

    return {
        "att": att,
        "counterfactual": augmented_cf,
        "effects": effects,
        "ci": ci,
        "inference_method": inference_method,
        "correction_beta": correction_beta,
        "base_counterfactual": base_cf,
        "jackknife_att": jackknife,
    }


def _synthetic_control_output(
    report: Any,
    *,
    warnings: list[str] | None = None,
    weights: np.ndarray | None = None,
    counterfactual: np.ndarray | None = None,
    augmented: bool = False,
) -> dict[str, Any]:
    output = wrap_causal_output(
        report,
        warnings=warnings,
        extras={
            "weights": weights,
            "counterfactual": counterfactual,
            "augmented": augmented,
        },
    )
    if not output["warnings"]:
        output["warnings"] = None
    return output


@foundry_method(
    namespace="causal.inference",
    version="2.0.0",
    tags={"causal", "quasi-experimental", "synthetic-control"},
)
class SyntheticControlMethod:
    """Compute donor weights with verified normalized convex optimality.

    Version 2 checks simplex feasibility and a convex suboptimality bound for
    the original weighted outcome/covariate objective. Successful numerical
    computation does not establish donor overlap, identification, or accuracy;
    pre-treatment fit and the existing causal requirements still apply.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="synthetic_control",
        namespace="",
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
                    name="report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
                SlotSpec(
                    name="envelope",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("uncertainty", "json"),
                ),
                SlotSpec(
                    name="warnings",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("warning", "list"),
                ),
                SlotSpec(
                    name="weights",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("weight", "proportion"),
                    shape=("n_donors",),
                ),
                SlotSpec(
                    name="counterfactual",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_periods",),
                ),
                SlotSpec(
                    name="augmented",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("flag", "boolean"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="n_placebo_runs", default="all"),
            ParameterSpec(name="optimization_method", default="SLSQP"),
            ParameterSpec(name="max_iter", default=1000),
            ParameterSpec(
                name="tolerance",
                default=1e-8,
                description=(
                    "Strictly between zero and one; bounds simplex feasibility and "
                    "original weighted-objective convex gap after common normalization."
                ),
            ),
            ParameterSpec(name="covariates_weight", default=0.0),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="estimation_mode", default="standard"),
            ParameterSpec(name="ridge_alpha", default=1.0),
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
            "Synthetic Control Method (Abadie et al.) using constrained donor weights and "
            "placebo/permutation inference."
        ),
        tags=frozenset({"causal", "quasi-experimental", "synthetic-control"}),
        citations=(
            "Abadie, A., Diamond, A., & Hainmueller, J. (2010). "
            "Synthetic Control Methods for Comparative Case Studies.",
            "Abadie, A. (2021). Using Synthetic Controls: Feasibility, "
            "Data Requirements, and Methodological Aspects.",
        ),
        equations={
            "objective": "min_W ||Y1_pre - W @ Y0_pre||^2, s.t. W >= 0, sum(W)=1",
            "att": "tau_t = Y1_t - W_hat @ Y0_t",
            "placebo_p": "(sum(I(ratio_j >= ratio_treated))+1)/(J+1)",
        },
        assumptions={
            "single_treated_unit": "A single treated unit must be identifiable.",
            "convex_hull_overlap": "Treated pre-period trajectory lies in donor convex hull.",
            "no_interference": "No interference/spillovers between treated and donor units.",
        },
        when_to_use="Single treated unit; comparative case study; no suitable control group; good pre-treatment fit (<15 donor units)",
        when_not_to_use="Many treated units; short pre-treatment period (<5 periods); poor synthetic control fit",
        typical_min_obs=30,
        output_interpretation="ATT trajectory post-treatment: gap between treated unit and synthetic control. In-space/in-time placebos validate inference.",
    )

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        assumptions = dict(SyntheticControlMethod.metadata.assumptions)
        diagnostics: list[DiagnosticTest] = []

        treated_idx = np.where(data.treatment == 1)[0]
        donor_idx = np.where(data.treatment == 0)[0]
        if treated_idx.shape[0] != 1:
            report = build_failure_report(
                method=CausalMethod.SYNTHETIC_CONTROL,
                status=EstimationStatus.INPUT_INVALID,
                reason=f"SCM requires exactly one treated unit, got {treated_idx.shape[0]}",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=int(treated_idx.shape[0]),
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return _synthetic_control_output(
                report,
                warnings=[report.status_reason or "invalid input"],
                weights=None,
                counterfactual=None,
                augmented=False,
            )
        if donor_idx.shape[0] < 2:
            report = build_failure_report(
                method=CausalMethod.SYNTHETIC_CONTROL,
                status=EstimationStatus.INPUT_INVALID,
                reason="SCM requires at least two donor units",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return _synthetic_control_output(
                report,
                warnings=[report.status_reason or "invalid input"],
                weights=None,
                counterfactual=None,
                augmented=False,
            )
        if data.time_treatment <= 0 or data.time_treatment >= data.n_periods:
            report = build_failure_report(
                method=CausalMethod.SYNTHETIC_CONTROL,
                status=EstimationStatus.INPUT_INVALID,
                reason=(
                    f"time_treatment={data.time_treatment} must lie in [1, {data.n_periods - 1}]"
                ),
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return _synthetic_control_output(
                report,
                warnings=[report.status_reason or "invalid input"],
                weights=None,
                counterfactual=None,
                augmented=False,
            )

        t0 = data.time_treatment
        treated = int(treated_idx[0])
        y_treated_pre = data.outcome[treated, :t0]
        y_donors_pre = data.outcome[donor_idx, :t0]

        x_treated = None
        x_donors = None
        covariates_weight = float(params.get("covariates_weight", 0.0))
        if data.covariates is not None and covariates_weight > 0:
            x_treated = data.covariates[treated]
            x_donors = data.covariates[donor_idx]

        donor_weights, ok, err = _fit_scm_weights(
            y_treated_pre=y_treated_pre,
            y_donors_pre=y_donors_pre,
            method=str(params.get("optimization_method", "SLSQP")),
            max_iter=int(params.get("max_iter", 1000)),
            tolerance=float(params.get("tolerance", 1e-8)),
            covariates_weight=covariates_weight,
            x_treated=x_treated,
            x_donors=x_donors,
        )
        if not ok:
            report = build_failure_report(
                method=CausalMethod.SYNTHETIC_CONTROL,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"SCM optimizer failed: {err}",
                estimand="ATT",
                sample_size=data.n_units * data.n_periods,
                n_treated=1,
                n_control=int(donor_idx.shape[0]),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=assumptions,
            )
            return _synthetic_control_output(
                report,
                warnings=[report.status_reason or "optimizer failure"],
                weights=None,
                counterfactual=None,
                augmented=False,
            )

        estimation_mode = str(params.get("estimation_mode", "standard"))
        confidence_level = float(params.get("confidence_level", 0.95))

        if estimation_mode == "augmented":
            augmented = augmented_synthetic_control(
                data.outcome[treated],
                data.outcome[donor_idx],
                t0=t0,
                donor_weights=donor_weights,
                ridge_alpha=float(params.get("ridge_alpha", 1.0)),
                confidence_level=confidence_level,
            )
            counterfactual = np.asarray(augmented["counterfactual"], dtype=float)
            effects = np.asarray(augmented["effects"], dtype=float)
            att = float(augmented["att"])
            ci = tuple(float(x) for x in augmented["ci"])
            inference_method = str(augmented["inference_method"])
            placebo_results = []
            placebo_atts = []
            placebo_ratios = []
            placebo_p_value = None
            rmspe_pre = compute_rmspe(data.outcome[treated, :t0], counterfactual[:t0])
            rmspe_post = compute_rmspe(data.outcome[treated, t0:], counterfactual[t0:])
            rmspe_ratio = float(rmspe_post / max(rmspe_pre, 1e-12))
        else:
            counterfactual = donor_weights @ data.outcome[donor_idx, :]
            effects = data.outcome[treated, :] - counterfactual
            post_effects = effects[t0:]
            att = float(np.mean(post_effects))

            rmspe_pre = compute_rmspe(data.outcome[treated, :t0], counterfactual[:t0])
            rmspe_post = compute_rmspe(data.outcome[treated, t0:], counterfactual[t0:])
            rmspe_ratio = float(rmspe_post / max(rmspe_pre, 1e-12))

            placebo_results = []
            placebo_atts = []
            placebo_ratios = []
            requested_runs = params.get("n_placebo_runs", "all")
            donor_order = donor_idx.tolist()
            if isinstance(requested_runs, int):
                donor_order = donor_order[: max(0, requested_runs)]

            for pseudo_treated in donor_order:
                pseudo_donors = np.array(
                    [idx for idx in donor_idx if idx != pseudo_treated], dtype=int
                )
                if pseudo_donors.size == 0:
                    continue
                pseudo_weights, pseudo_ok, _ = _fit_scm_weights(
                    y_treated_pre=data.outcome[pseudo_treated, :t0],
                    y_donors_pre=data.outcome[pseudo_donors, :t0],
                    method=str(params.get("optimization_method", "SLSQP")),
                    max_iter=int(params.get("max_iter", 1000)),
                    tolerance=float(params.get("tolerance", 1e-8)),
                    covariates_weight=0.0,
                )
                if not pseudo_ok:
                    continue
                pseudo_counterfactual = pseudo_weights @ data.outcome[pseudo_donors, :]
                pseudo_effects = data.outcome[pseudo_treated, :] - pseudo_counterfactual
                pseudo_att = float(np.mean(pseudo_effects[t0:]))
                pseudo_rmspe_pre = compute_rmspe(
                    data.outcome[pseudo_treated, :t0],
                    pseudo_counterfactual[:t0],
                )
                pseudo_rmspe_post = compute_rmspe(
                    data.outcome[pseudo_treated, t0:],
                    pseudo_counterfactual[t0:],
                )
                pseudo_ratio = float(pseudo_rmspe_post / max(pseudo_rmspe_pre, 1e-12))
                placebo_results.append(
                    PlaceboResult(
                        unit_id=int(pseudo_treated),
                        effect_estimate=pseudo_att,
                        rmspe_pre=pseudo_rmspe_pre,
                        rmspe_post=pseudo_rmspe_post,
                        rmspe_ratio=pseudo_ratio,
                    )
                )
                placebo_atts.append(pseudo_att)
                placebo_ratios.append(pseudo_ratio)

            placebo_p_value = None
            if placebo_ratios:
                placebo_p_value = float(
                    (sum(1 for ratio in placebo_ratios if ratio >= rmspe_ratio) + 1)
                    / (len(placebo_ratios) + 1)
                )

            if len(placebo_atts) >= 5:
                null = np.asarray(placebo_atts, dtype=float)
                lo_null = float(np.percentile(null, 100.0 * (1.0 - confidence_level) / 2.0))
                hi_null = float(np.percentile(null, 100.0 * (1.0 + confidence_level) / 2.0))
                ci = (att - hi_null, att - lo_null)
                inference_method = "placebo_permutation"
            else:
                rng = params["__rng__"]
                n_boot = 1000
                samples = np.array(
                    [
                        np.mean(rng.choice(post_effects, size=post_effects.shape[0], replace=True))
                        for _ in range(n_boot)
                    ]
                )
                ci = bootstrap_ci(samples, confidence_level=confidence_level)
                inference_method = "bootstrap"

        diagnostics.append(
            DiagnosticTest(
                test_name="pre_treatment_fit_rmspe",
                statistic=rmspe_pre,
                passed=bool(rmspe_pre < np.std(data.outcome[treated, :t0]) + 1e-12),
                details={"rmspe_post": rmspe_post, "rmspe_ratio": rmspe_ratio},
            )
        )

        effect_size = compute_cohen_d(
            effect=att,
            treated_outcome=data.outcome[treated, t0:],
            control_outcome=np.mean(data.outcome[donor_idx, t0:], axis=0),
        )
        report = build_success_report(
            method=CausalMethod.SYNTHETIC_CONTROL,
            estimand="ATT",
            point_estimate=att,
            confidence_interval=ci,
            confidence_level=confidence_level,
            p_value=placebo_p_value,
            placebo_p_value=placebo_p_value,
            placebo_results=placebo_results,
            inference_method=inference_method,
            effect_size_cohen_d=effect_size,
            pre_treatment_fit={
                "rmspe": rmspe_pre,
                "rmspe_post": rmspe_post,
                "rmspe_ratio": rmspe_ratio,
            },
            diagnostics=diagnostics,
            sample_size=data.n_units * data.n_periods,
            n_treated=1,
            n_control=int(donor_idx.shape[0]),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=assumptions,
            time_effects={
                "period": list(range(data.n_periods)),
                "effect": [float(value) for value in effects],
            },
            method_params={
                "numerical_solution_rule": "scm_normalized_simplex_convex_gap_v1",
                "numerical_solution_tolerance": float(params.get("tolerance", 1e-8)),
                "donor_weights": donor_weights.tolist(),
                "donor_ids": donor_idx.astype(int).tolist(),
                "treated_id": int(treated),
                "estimation_mode": estimation_mode,
            },
        )
        return _synthetic_control_output(
            report,
            warnings=None,
            weights=donor_weights,
            counterfactual=counterfactual,
            augmented=estimation_mode == "augmented",
        )


__all__ = ["SyntheticControlMethod", "augmented_synthetic_control"]
