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
from polisyos.foundry.methods.catalog.causal._common import (
    bootstrap_ci,
    build_failure_report,
    build_success_report,
    compute_cohen_d,
    compute_rmspe,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.causal import CausalMethod, DiagnosticTest, EstimationStatus, PlaceboResult


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
    try:
        from scipy.optimize import minimize
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency runtime
        return np.array([]), False, f"scipy missing: {exc}"

    n_donors = y_donors_pre.shape[0]
    if n_donors == 0:
        return np.array([]), False, "no donor units available"

    x0 = np.full(n_donors, 1.0 / n_donors, dtype=float)
    bounds = [(0.0, 1.0)] * n_donors
    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]

    def objective(weights: np.ndarray) -> float:
        synthetic_pre = weights @ y_donors_pre
        loss = np.mean((y_treated_pre - synthetic_pre) ** 2)
        if (
            covariates_weight > 0
            and x_treated is not None
            and x_donors is not None
            and x_donors.size > 0
        ):
            synthetic_x = weights @ x_donors
            loss += covariates_weight * np.mean((x_treated - synthetic_x) ** 2)
        return float(loss)

    result = minimize(
        objective,
        x0=x0,
        method=method,
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": max_iter, "ftol": tolerance},
    )

    if not result.success:
        return np.array([]), False, str(result.message)
    weights = np.asarray(result.x, dtype=float)
    if not np.isfinite(weights).all():
        return np.array([]), False, "optimizer returned non-finite donor weights"
    weights = np.clip(weights, 0.0, 1.0)
    w_sum = float(np.sum(weights))
    if w_sum <= 0:
        return np.array([]), False, "optimizer returned zero-sum donor weights"
    weights = weights / w_sum
    return weights, True, ""


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={"causal", "quasi-experimental", "synthetic-control"},
)
class SyntheticControlMethod:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="synthetic_control",
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
                SlotSpec(
                    name="donor_weights",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("weight", "proportion"),
                ),
                SlotSpec(
                    name="counterfactual_series",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="n_placebo_runs", default="all"),
            ParameterSpec(name="optimization_method", default="SLSQP"),
            ParameterSpec(name="max_iter", default=1000),
            ParameterSpec(name="tolerance", default=1e-8),
            ParameterSpec(name="covariates_weight", default=0.0),
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
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
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
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])
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
            return wrap_causal_output(report, warnings=[report.status_reason or "invalid input"])

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
            return wrap_causal_output(
                report, warnings=[report.status_reason or "optimizer failure"]
            )

        counterfactual = donor_weights @ data.outcome[donor_idx, :]
        effects = data.outcome[treated, :] - counterfactual
        post_effects = effects[t0:]
        att = float(np.mean(post_effects))

        rmspe_pre = compute_rmspe(data.outcome[treated, :t0], counterfactual[:t0])
        rmspe_post = compute_rmspe(data.outcome[treated, t0:], counterfactual[t0:])
        rmspe_ratio = float(rmspe_post / max(rmspe_pre, 1e-12))
        diagnostics.append(
            DiagnosticTest(
                test_name="pre_treatment_fit_rmspe",
                statistic=rmspe_pre,
                passed=bool(rmspe_pre < np.std(data.outcome[treated, :t0]) + 1e-12),
                details={"rmspe_post": rmspe_post, "rmspe_ratio": rmspe_ratio},
            )
        )

        placebo_results: list[PlaceboResult] = []
        placebo_atts: list[float] = []
        placebo_ratios: list[float] = []
        requested_runs = params.get("n_placebo_runs", "all")
        donor_order = donor_idx.tolist()
        if isinstance(requested_runs, int):
            donor_order = donor_order[: max(0, requested_runs)]

        for pseudo_treated in donor_order:
            pseudo_donors = np.array([idx for idx in donor_idx if idx != pseudo_treated], dtype=int)
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

        placebo_p_value: float | None = None
        confidence_level = float(params.get("confidence_level", 0.95))
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
                "donor_weights": donor_weights.tolist(),
                "donor_ids": donor_idx.astype(int).tolist(),
                "treated_id": int(treated),
            },
        )
        return wrap_causal_output(
            report,
            extras={
                "weights": donor_weights,
                "counterfactual": counterfactual,
            },
        )


__all__ = ["SyntheticControlMethod"]
