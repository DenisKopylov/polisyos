"""Estimate average treatment effects with panel Difference-in-Differences designs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from decimal import ROUND_CEILING, Decimal
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    compute_cohen_d,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
)

_DID_CITATIONS = (
    "Callaway, B., & Sant'Anna, P. (2021). Difference-in-Differences with Multiple Time Periods.",
    "Angrist, J., & Pischke, J. (2009). Mostly Harmless Econometrics.",
)
_DID_EQUATIONS = {
    "did_2x2": "ATT = (Y_treated_post - Y_treated_pre) - (Y_control_post - Y_control_pre)",
    "regression": "Y_it = a + b*Post_t + c*Treat_i + d*(Post_t*Treat_i) + e_it",
    "selected_participation": "theta_sel = sum_g P(G=g | ever treated) mean_{t in E_g} ATT(g,t)",
}
_DID_ASSUMPTIONS = {
    "parallel_trends": "Untreated potential outcomes follow parallel trends.",
    "no_anticipation": "No treatment effect before treatment start (unless explicitly modeled).",
    "stable_composition": "Group composition is stable over analysis horizon.",
}


def _normal_critical_value(confidence_level: float) -> float:
    """Return the two-sided normal critical value for a validated confidence level."""

    level = float(confidence_level)
    if not math.isfinite(level) or not 0.0 < level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    return float(NormalDist().inv_cdf((1.0 + level) / 2.0))


def _did_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(name="report", slot_type=SlotType.SCALAR, unit=Unit("report", "json")),
            SlotSpec(name="envelope", slot_type=SlotType.SCALAR, unit=Unit("uncertainty", "json")),
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("report", "json"),
            ),
            SlotSpec(
                name="uncertainty_envelope",
                slot_type=SlotType.SCALAR,
                unit=Unit("uncertainty", "json"),
            ),
            SlotSpec(
                name="warnings",
                slot_type=SlotType.SCALAR,
                unit=Unit("warning", "list"),
            ),
        }
    )


def _wrap_did_output(
    report: CausalEffectReport, *, warnings: list[str] | None = None
) -> dict[str, Any]:
    """Bind the actual DiD producer to its declared ports and historical consumer keys."""

    output = wrap_causal_output(report, warnings=warnings)
    output["result"] = report
    output["uncertainty_envelope"] = output["envelope"]
    return output


def _did_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelObservationalData,
        nested_keys=("panel_data", "panel_observational_data"),
    )


def _materialize_did_data(
    bound_inputs: Mapping[str, Any], fallback_state: Any
) -> PanelObservationalData:
    payload = _did_payload(fallback_state)
    payload.update(bound_inputs)
    return PanelObservationalData.model_validate(payload)


def _invalid_did_request_output(
    data: PanelObservationalData,
    reason: str,
) -> dict[str, Any]:
    """Return a typed failure for an ambiguous or unsupported DiD request."""

    treated_mask = data.treatment == 1
    report = build_failure_report(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        status=EstimationStatus.INPUT_INVALID,
        reason=reason,
        estimand="ATT",
        sample_size=data.n_units * data.n_periods,
        n_treated=int(treated_mask.sum()),
        n_control=int((data.treatment == 0).sum()),
        pre_periods=data.pre_periods,
        post_periods=data.post_periods,
        assumptions=dict(_DID_ASSUMPTIONS),
    )
    return _wrap_did_output(report, warnings=[reason])


def _legacy_staggered_flag(params: Mapping[str, Any]) -> bool:
    """Resolve the historical mode flag without truthiness-based coercion."""

    value = params.get("staggered", False)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    raise ValueError("staggered must be a boolean")


def _standard_did_input_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="outcome",
                slot_type=SlotType.MATRIX,
                unit=Unit("outcome", "value"),
                contract_id=PanelObservationalData.contract_id,
                shape=("n_units", "n_periods"),
            ),
            SlotSpec(
                name="treatment",
                slot_type=SlotType.VECTOR,
                unit=Unit("binary", "flag"),
                shape=("n_units",),
            ),
            SlotSpec(
                name="time_treatment",
                slot_type=SlotType.SCALAR,
                unit=Unit("time", "index"),
            ),
        }
    )


def _staggered_did_input_slots() -> frozenset[SlotSpec]:
    return _standard_did_input_slots() | frozenset(
        {
            SlotSpec(
                name="treatment_timing",
                slot_type=SlotType.VECTOR,
                unit=Unit("time", "index"),
                shape=("n_units",),
            )
        }
    )


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


def _ols_cluster_cr0(
    x_mat: np.ndarray,
    y_vec: np.ndarray,
    cluster_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit OLS with the uncorrected cluster-robust (CR0) covariance."""

    beta, *_ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
    residual = y_vec - x_mat @ beta
    xtx_inv = np.linalg.pinv(x_mat.T @ x_mat)
    meat = np.zeros((x_mat.shape[1], x_mat.shape[1]), dtype=float)
    for cluster in np.unique(cluster_ids):
        mask = cluster_ids == cluster
        score = x_mat[mask].T @ residual[mask]
        meat += np.outer(score, score)
    covariance = xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    return beta, se


def _unit_cluster_ids(data: PanelObservationalData, params: Mapping[str, Any]) -> np.ndarray:
    """Return one cluster label per panel row, preserving unit membership."""

    cluster_spec = params.get("cluster_var")
    named_cluster = cluster_spec.strip().lower() if isinstance(cluster_spec, str) else None
    uses_panel_unit_ids = cluster_spec is None or named_cluster in {"unit", "unit_id", "unit_ids"}
    if uses_panel_unit_ids:
        if data.unit_ids is None:
            raise ValueError("cluster covariance requires unit_ids")
        unit_clusters = np.asarray(data.unit_ids)
    else:
        candidate = np.asarray(cluster_spec)
        if candidate.ndim != 1:
            raise ValueError("cluster_var must be a one-dimensional array")
        if candidate.size == data.n_units:
            unit_clusters = candidate
        elif candidate.size == data.n_units * data.n_periods:
            candidate_by_unit = candidate.reshape(data.n_units, data.n_periods)
            if not np.all(candidate_by_unit == candidate_by_unit[:, :1]):
                raise ValueError("cluster_var must be constant within each unit")
            unit_clusters = candidate_by_unit[:, 0]
        else:
            raise ValueError("cluster_var must have one label per unit or observation")

    if unit_clusters.ndim != 1 or unit_clusters.size != data.n_units:
        raise ValueError("cluster_var must have one label per unit")
    if np.unique(unit_clusters).size != data.n_units:
        if uses_panel_unit_ids:
            raise ValueError("unit_ids must be unique for unit-cluster covariance")
        raise ValueError("cluster_var must identify each unit uniquely")
    cluster_ids = np.repeat(unit_clusters, data.n_periods)
    if np.unique(cluster_ids).size < 2:
        raise ValueError("cluster covariance requires at least two clusters")
    return cluster_ids


def _parallel_trend_diagnostic(
    outcome: np.ndarray,
    treatment: np.ndarray,
    *,
    t0: int,
) -> DiagnosticTest:
    """Describe pretrend evidence; never certify the identifying assumption."""

    limitation = {
        "identification_authority": False,
        "limitation": "Non-rejection cannot establish untreated potential-outcome parallel trends.",
    }
    treated_mask = treatment == 1
    control_mask = treatment == 0
    if t0 < 3 or not treated_mask.any() or not control_mask.any():
        return DiagnosticTest(
            test_name="pre_trend_parallelism",
            statistic=None,
            p_value=None,
            passed=False,
            details={
                **limitation,
                "status": "not_testable",
                "reason": "insufficient_pre_periods"
                if t0 < 3
                else "treated_or_control_group_missing",
            },
        )

    diff = outcome[treated_mask, :t0].mean(axis=0) - outcome[control_mask, :t0].mean(axis=0)
    x_mat = np.column_stack([np.ones(t0), np.arange(t0, dtype=float)])
    beta, se = _ols_hc1(x_mat, diff)
    slope, slope_se = float(beta[1]), float(se[1])
    if slope_se <= np.finfo(float).eps * max(1.0, float(np.max(np.abs(diff)))):
        # A deterministic nonzero differential trend is a violation, not z=0.
        p_value = (
            1.0
            if abs(slope) <= np.finfo(float).eps * max(1.0, float(np.max(np.abs(diff))))
            else 0.0
        )
        z_score = None
    else:
        z_score = slope / slope_se
        p_value = _normal_two_sided_pvalue(z_score)
    status = "evidence_of_violation" if p_value <= 0.05 else "no_detected_pretrend"
    return DiagnosticTest(
        test_name="pre_trend_parallelism",
        statistic=slope,
        p_value=p_value,
        passed=status == "no_detected_pretrend",
        details={**limitation, "status": status, "slope_se": slope_se, "z_score": z_score},
    )


def _run_standard_did(data: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
    t0 = data.time_treatment
    treated_mask = data.treatment == 1
    control_mask = data.treatment == 0
    if t0 <= 0:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.INPUT_INVALID,
            reason="standard DiD requires at least one pre-treatment period",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int(treated_mask.sum()),
            n_control=int(control_mask.sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "invalid input"])
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
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "invalid input"])

    raw_cov_type = params.get("cov_type", "HC1")
    cov_type = str(raw_cov_type).strip().lower()
    if cov_type == "hc1":
        covariance_procedure = "hc1"
    elif cov_type in {"cluster", "clustered", "unit_cluster"}:
        covariance_procedure = "unit_cluster_cr0"
    else:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.INPUT_INVALID,
            reason=f"unsupported covariance profile: {raw_cov_type}",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int(treated_mask.sum()),
            n_control=int(control_mask.sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "invalid input"])

    try:
        confidence_level = float(params.get("confidence_level", 0.95))
        z_critical = _normal_critical_value(confidence_level)
    except (TypeError, ValueError) as exc:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.INPUT_INVALID,
            reason=str(exc),
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int(treated_mask.sum()),
            n_control=int(control_mask.sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "invalid input"])

    y = data.outcome.reshape(-1)
    post = np.tile(np.arange(data.n_periods) >= t0, data.n_units).astype(float)
    treat = np.repeat(data.treatment.astype(float), data.n_periods)
    interaction = post * treat
    x_mat = np.column_stack([np.ones_like(y), post, treat, interaction])

    try:
        if covariance_procedure == "hc1":
            beta, se = _ols_hc1(x_mat, y)
            n_clusters = None
        else:
            cluster_ids = _unit_cluster_ids(data, params)
            beta, se = _ols_cluster_cr0(x_mat, y, cluster_ids)
            n_clusters = int(np.unique(cluster_ids).size)
    except (TypeError, ValueError) as exc:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.INPUT_INVALID,
            reason=str(exc),
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int(treated_mask.sum()),
            n_control=int(control_mask.sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "invalid input"])

    att = float(beta[3])
    att_se = float(se[3]) if se.shape[0] > 3 else 0.0
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
                details={
                    "message": "Pretrend evidence is limited; it does not establish identification.",
                    "status": pre_diag.details["status"],
                    "identification_authority": False,
                },
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
        assumptions=dict(_DID_ASSUMPTIONS),
        method_params={
            "staggered": False,
            "cov_type": str(raw_cov_type),
            "covariance_procedure": covariance_procedure,
            "confidence_procedure": "normal_two_sided",
            "critical_value": z_critical,
            "delta_hat": att,
            "inference_scope": "iid_rows"
            if covariance_procedure == "hc1"
            else "large_independent_units",
            "finite_cluster_guarantee": False,
            "parallel_trends_identified": False,
            "pretrend_status": pre_diag.details["status"],
            **({"n_clusters": n_clusters} if n_clusters is not None else {}),
        },
    )
    return _wrap_did_output(report)


def _staggered_target_contract(
    data: PanelObservationalData, params: Mapping[str, Any]
) -> dict[str, Any]:
    """Recompute the fixed estimand and its data/unit alignment binding."""

    timing = data.treatment_timing
    if timing is None:
        raise ValueError("staggered DiD requires treatment_timing array")
    if np.asarray(timing).dtype.kind not in "iu" or np.any(timing < -1):
        raise ValueError(
            "treatment_timing must contain integer cohort indices or -1 for never treated"
        )
    if not np.array_equal(data.treatment, (timing >= 0).astype(int)):
        raise ValueError("treatment must agree with ever-treated cohort membership")
    horizon = params.get("study_horizon")
    if horizon is None:
        horizon = data.n_periods
    if (
        isinstance(horizon, (bool, np.bool_))
        or not isinstance(horizon, (int, np.integer))
        or not 1 < horizon <= data.n_periods
    ):
        raise ValueError("study_horizon must be an integer between 2 and n_periods")
    groups = [int(g) for g in np.unique(timing) if g >= 0]
    if not groups:
        raise ValueError("staggered DiD requires an ever-treated cohort")
    if any(g >= horizon for g in groups):
        raise ValueError(
            "every requested cohort must have a post period within the fixed study_horizon"
        )
    control = params.get("control_group", "never_treated")
    if control not in {"never_treated", "not_yet_treated"}:
        raise ValueError(f"unsupported control_group: {control}")
    anticipation = params.get("anticipation", 0)
    if (
        isinstance(anticipation, (bool, np.bool_))
        or not isinstance(anticipation, (int, np.integer))
        or anticipation < 0
    ):
        raise ValueError("anticipation must be a nonnegative integer")
    declared = params.get("eligible_periods")
    if declared is None:
        periods = {str(g): list(range(g, int(horizon))) for g in groups}
    else:
        if not isinstance(declared, Mapping) or len(declared) != len(groups):
            raise ValueError("eligible_periods must declare every requested cohort exactly once")
        periods = {}
        for key, values in declared.items():
            if isinstance(key, (bool, np.bool_)) or not (
                isinstance(key, (int, np.integer))
                or (isinstance(key, str) and key in {str(g) for g in groups})
            ):
                raise ValueError("eligible_periods has an invalid cohort key")
            group = int(key)
            if group not in groups or str(group) in periods:
                raise ValueError(
                    "eligible_periods must declare every requested cohort exactly once"
                )
            if not isinstance(values, (list, tuple, np.ndarray)) or len(values) == 0:
                raise ValueError("each cohort requires a nonempty fixed eligible-period set")
            if any(
                isinstance(t, (bool, np.bool_))
                or not isinstance(t, (int, np.integer))
                or not group <= t < horizon
                for t in values
            ):
                raise ValueError(
                    "eligible periods must be integer post periods within study_horizon"
                )
            if len(set(values)) != len(values):
                raise ValueError("eligible periods must be unique")
            periods[str(group)] = sorted(int(t) for t in values)
        if set(periods) != {str(g) for g in groups}:
            raise ValueError("eligible_periods must declare every requested cohort exactly once")
    unit_ids = data.unit_ids if data.unit_ids is not None else np.arange(data.n_units)
    try:
        if np.unique(unit_ids).size != data.n_units:
            raise ValueError("staggered bootstrap requires unique unit_ids")
    except TypeError as exc:
        raise ValueError("unit_ids must have comparable unique scalar labels") from exc
    counts = {str(g): int(np.sum(timing == g)) for g in groups}
    selected = sum(counts.values())
    contract = {
        "estimand": "theta_sel",
        "sampling_unit": "independent_panel_unit",
        "unit_identity": "unit_ids" if data.unit_ids is not None else "row_index",
        "n_units": data.n_units,
        "study_horizon": int(horizon),
        "eligible_periods": periods,
        "cohort_counts": counts,
        "cohort_shares": {g: count / selected for g, count in counts.items()},
        "control_group": control,
        "anticipation": int(anticipation),
    }
    payload = {
        "outcome": np.asarray(data.outcome, dtype=float).tolist(),
        "treatment": data.treatment.tolist(),
        "treatment_timing": timing.tolist(),
        "unit_ids": unit_ids.tolist(),
        "time_index": None if data.time_index is None else data.time_index.tolist(),
    }
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        contract["data_sha256"] = hashlib.sha256(encoded).hexdigest()
        bound = json.dumps(
            contract, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "panel/unit identities must have finite JSON scalar representations"
        ) from exc
    return {"target_contract": contract, "target_binding": hashlib.sha256(bound).hexdigest()}


def _cohort_time_cells(
    data: PanelObservationalData,
    *,
    control_group: str,
    anticipation: int,
    eligible_periods: Mapping[str, list[int]] | None = None,
) -> tuple[list[dict[str, Any]], list[tuple[int, int]], list[int]]:
    """Keep every requested ATT(g,t), including explicit unsupported-cell gaps."""

    assert data.treatment_timing is not None
    timing = data.treatment_timing
    periods = eligible_periods or {
        str(int(g)): list(range(int(g), data.n_periods)) for g in np.unique(timing) if g >= 0
    }
    cells, no_control_cells, missing_baseline_groups = [], [], []
    for group_key, times in sorted(periods.items(), key=lambda item: int(item[0])):
        group_start = int(group_key)
        baseline_t = group_start - 1 - anticipation
        if baseline_t < 0:
            missing_baseline_groups.append(group_start)
            continue
        treated_indices = np.flatnonzero(timing == group_start)
        for t in times:
            control_mask = (
                (timing == -1) | (timing > t + anticipation)
                if control_group == "not_yet_treated"
                else timing == -1
            )
            control_indices = np.flatnonzero(control_mask)
            if not control_indices.size:
                no_control_cells.append((group_start, t))
                continue
            cells.append(
                {
                    "group": group_start,
                    "period": t,
                    "baseline": baseline_t,
                    "treated_indices": treated_indices,
                    "control_indices": control_indices,
                    "treated_delta": np.asarray(
                        data.outcome[treated_indices, t]
                        - data.outcome[treated_indices, baseline_t],
                        dtype=float,
                    ),
                    "control_delta": np.asarray(
                        data.outcome[control_indices, t]
                        - data.outcome[control_indices, baseline_t],
                        dtype=float,
                    ),
                    "weight": float(treated_indices.size),
                }
            )
    return cells, no_control_cells, missing_baseline_groups


def _cohort_time_att(
    data: PanelObservationalData, *, control_group: str, anticipation: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return descriptive cell means; the scalar estimator owns its fixed target."""

    bound = _staggered_target_contract(
        data, {"control_group": control_group, "anticipation": anticipation}
    )
    cells, _, _ = _cohort_time_cells(
        data,
        control_group=control_group,
        anticipation=anticipation,
        eligible_periods=bound["target_contract"]["eligible_periods"],
    )
    return np.asarray(
        [cell["treated_delta"].mean() - cell["control_delta"].mean() for cell in cells], dtype=float
    ), np.asarray([cell["weight"] for cell in cells], dtype=float)


def _selected_participation_influence(
    data: PanelObservationalData, cells: list[dict[str, Any]]
) -> tuple[float, np.ndarray, list[dict[str, Any]]]:
    """Differentiate cohort means and estimated ever-treated share ratios jointly."""

    n = data.n_units
    groups = sorted({cell["group"] for cell in cells})
    selected_count = int(np.sum(data.treatment_timing >= 0))
    cohort_values = {}
    influence = np.zeros(n, dtype=float)
    summaries = []
    for group in groups:
        selected_cells = [cell for cell in cells if cell["group"] == group]
        count = selected_cells[0]["treated_indices"].size
        share = count / selected_count
        values = []
        for cell in selected_cells:
            treated, control = cell["treated_delta"], cell["control_delta"]
            treated_mean, control_mean = float(treated.mean()), float(control.mean())
            cell_att = treated_mean - control_mean
            values.append(cell_att)
            factor = share / len(selected_cells)
            influence[cell["treated_indices"]] += (
                factor * n / treated.size * (treated - treated_mean)
            )
            influence[cell["control_indices"]] -= (
                factor * n / control.size * (control - control_mean)
            )
            summaries.append(
                {
                    "cohort": group,
                    "period": cell["period"],
                    "baseline": cell["baseline"],
                    "n_treated": int(treated.size),
                    "n_control": int(control.size),
                    "att": cell_att,
                }
            )
        cohort_values[group] = float(np.mean(values))
    point = sum(
        int(np.sum(data.treatment_timing == group)) / selected_count * cohort_values[group]
        for group in groups
    )
    for group in groups:
        influence[data.treatment_timing == group] += (
            n / selected_count * (cohort_values[group] - point)
        )
    # Center numerical roundoff only; each analytic score component has mean zero.
    influence -= influence.mean()
    return float(point), influence, summaries


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
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "invalid input"])

    raw_control_group = params.get("control_group", "never_treated")
    if not isinstance(raw_control_group, str) or raw_control_group not in {
        "never_treated",
        "not_yet_treated",
    }:
        return _invalid_did_request_output(
            data,
            f"unsupported control_group: {raw_control_group}",
        )
    control_group = raw_control_group
    raw_anticipation = params.get("anticipation", 0)
    if (
        isinstance(raw_anticipation, (bool, np.bool_))
        or not isinstance(raw_anticipation, (int, np.integer))
        or raw_anticipation < 0
    ):
        return _invalid_did_request_output(
            data,
            "anticipation must be a nonnegative integer",
        )
    anticipation = int(raw_anticipation)
    try:
        target = _staggered_target_contract(data, params)
        confidence_level = float(params.get("confidence_level", 0.95))
        _normal_critical_value(confidence_level)
        raw_bootstrap = params.get("n_bootstrap", 1000)
        if (
            isinstance(raw_bootstrap, (bool, np.bool_))
            or not isinstance(raw_bootstrap, (int, np.integer))
            or raw_bootstrap < 2
        ):
            raise ValueError("n_bootstrap must be an integer of at least 2")
        n_bootstrap = int(raw_bootstrap)
        # The confidence level is a declared decimal probability, not a binary
        # subtraction such as 1-.95 that can spuriously reject p=.05.
        significance = Decimal(1) - Decimal(str(confidence_level))
        minimum_accepted_tail = int(
            (significance * (n_bootstrap + 1) - 1).to_integral_value(rounding=ROUND_CEILING)
        )
        critical_index = n_bootstrap - minimum_accepted_tail
        if minimum_accepted_tail <= 0:
            raise ValueError(
                "n_bootstrap is insufficient for the requested confidence-level test inversion"
            )
        null_effect = float(params.get("null_effect", 0.0))
        if not math.isfinite(null_effect):
            raise ValueError("null_effect must be finite")
    except (TypeError, ValueError) as exc:
        if str(exc) == "staggered bootstrap requires unique unit_ids":
            report = build_failure_report(
                method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
                status=EstimationStatus.ASSUMPTION_FAILED,
                reason=str(exc),
                estimand="theta_sel",
                sample_size=data.n_units * data.n_periods,
                n_treated=int((data.treatment == 1).sum()),
                n_control=int((data.treatment == 0).sum()),
                pre_periods=data.pre_periods,
                post_periods=data.post_periods,
                assumptions=dict(_DID_ASSUMPTIONS),
            )
            return _wrap_did_output(report, warnings=[str(exc)])
        return _invalid_did_request_output(data, str(exc))
    cells, no_control_cells, missing_baseline_groups = _cohort_time_cells(
        data,
        control_group=control_group,
        anticipation=anticipation,
        eligible_periods=target["target_contract"]["eligible_periods"],
    )
    if missing_baseline_groups:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.ASSUMPTION_FAILED,
            reason="no valid baseline for one or more staggered cohorts",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int((data.treatment == 1).sum()),
            n_control=int((data.treatment == 0).sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
            method_params={
                "staggered": True,
                "control_group": control_group,
                "anticipation": anticipation,
                "missing_baseline_groups": sorted(set(missing_baseline_groups)),
            },
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "assumption failed"])

    if no_control_cells:
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.ASSUMPTION_FAILED,
            reason="no admissible controls for one or more staggered ATT(g,t) cells",
            estimand="ATT",
            sample_size=data.n_units * data.n_periods,
            n_treated=int((data.treatment == 1).sum()),
            n_control=int((data.treatment == 0).sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
            method_params={
                "staggered": True,
                "control_group": control_group,
                "anticipation": anticipation,
                "no_control_cells": [list(cell) for cell in no_control_cells],
            },
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "assumption failed"])

    if not cells:
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
            assumptions=dict(_DID_ASSUMPTIONS),
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "assumption failed"])

    att, influence, cell_summaries = _selected_participation_influence(data, cells)
    standard_error = float(np.linalg.norm(influence) / data.n_units)
    diagnostics = [_parallel_trend_diagnostic(data.outcome, data.treatment, t0=data.time_treatment)]
    method_params = {
        "staggered": True,
        **target,
        "control_group": control_group,
        "anticipation": anticipation,
        "n_cells": len(cells),
        "cell_estimates": cell_summaries,
        "bootstrap_independence": "panel_unit",
        "bootstrap_shared_draw": True,
        "bootstrap_unit_identity": target["target_contract"]["unit_identity"],
        "cohort_share_influence": True,
        "multiplier_distribution": "iid_mammen",
        "null_statistic": "centered_studentized_scalar",
        "null_effect": null_effect,
        "inference_scope": "large_independent_units_pointwise_scalar",
        "finite_cluster_guarantee": False,
        "simultaneous_bands": False,
        "parallel_trends_identified": False,
        "confidence_procedure": "finite_B_plus_one_scalar_test_inversion",
        "confidence_level": confidence_level,
    }
    if standard_error <= np.finfo(float).eps * max(1.0, abs(att)):
        report = build_failure_report(
            method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
            status=EstimationStatus.ASSUMPTION_FAILED,
            reason="staggered scalar inference requires nondegenerate unit influence",
            estimand="theta_sel",
            point_estimate=att,
            n_bootstrap_samples=n_bootstrap,
            diagnostics=diagnostics,
            sample_size=data.n_units * data.n_periods,
            n_treated=int((data.treatment == 1).sum()),
            n_control=int((data.treatment == 0).sum()),
            pre_periods=data.pre_periods,
            post_periods=data.post_periods,
            assumptions=dict(_DID_ASSUMPTIONS),
            method_params={**method_params, "inference_limitation": "degenerate_unit_influence"},
        )
        return _wrap_did_output(report, warnings=[report.status_reason or "limited inference"])

    rng = params["__rng__"]
    root_five = math.sqrt(5.0)
    values = np.array([(1.0 - root_five) / 2.0, (1.0 + root_five) / 2.0])
    probabilities = [(root_five + 1.0) / (2.0 * root_five), (root_five - 1.0) / (2.0 * root_five)]
    absolute_statistics = np.empty(n_bootstrap, dtype=float)
    # Batching limits temporary allocation, without changing draws or the fixed target.
    for start in range(0, n_bootstrap, 128):
        size = min(128, n_bootstrap - start)
        unit_draws = rng.choice(values, size=(size, data.n_units), p=probabilities)
        absolute_statistics[start : start + size] = np.abs(
            unit_draws @ influence / (data.n_units * standard_error)
        )
    # Equivalent to |Z_b| >= |Tobs| in real arithmetic, but evaluated on the
    # very same closed effect-scale intervals as the reported CI. This keeps
    # reconstructed endpoints and their immediately adjacent floats consistent.
    radii = absolute_statistics * standard_error
    tail_count = int(np.count_nonzero((att - radii <= null_effect) & (null_effect <= att + radii)))
    p_value = float((1 + tail_count) / (n_bootstrap + 1))
    critical = float(np.sort(absolute_statistics)[critical_index])
    report = build_success_report(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="theta_sel",
        point_estimate=att,
        confidence_interval=(att - critical * standard_error, att + critical * standard_error),
        confidence_level=confidence_level,
        standard_error=standard_error,
        p_value=p_value,
        inference_method="bootstrap",
        n_bootstrap_samples=n_bootstrap,
        diagnostics=diagnostics,
        sample_size=data.n_units * data.n_periods,
        n_treated=int((data.treatment == 1).sum()),
        n_control=int((data.treatment == 0).sum()),
        pre_periods=data.pre_periods,
        post_periods=data.post_periods,
        assumptions=dict(_DID_ASSUMPTIONS),
        method_params={
            **method_params,
            "critical_value": critical,
            "critical_order_index_zero_based": critical_index,
            "test_rejection_rule": "null_tail_count < minimum_accepted_tail_count",
            "significance_level": float(significance),
            "null_tail_count": tail_count,
            "minimum_accepted_tail_count": minimum_accepted_tail,
            "null_rejected": tail_count < minimum_accepted_tail,
        },
    )
    return _wrap_did_output(report)


@foundry_method(
    namespace="causal.inference",
    version="1.0.0",
    tags={
        "causal",
        "quasi-experimental",
        "difference-in-differences",
        "deprecated:aggregate-wrapper",
    },
)
class DifferenceInDifferences:
    """Historical direct-import replay adapter; default planning registers dedicated owners only."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="difference_in_differences",
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
        output_slots=_did_output_slots(),
        parameters=(
            ParameterSpec(name="staggered", default=False),
            ParameterSpec(name="control_group", default="never_treated"),
            ParameterSpec(name="n_bootstrap", default=1000),
            ParameterSpec(name="study_horizon", default=None),
            ParameterSpec(name="eligible_periods", default=None),
            ParameterSpec(name="null_effect", default=0.0),
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
        citations=_DID_CITATIONS,
        equations=dict(_DID_EQUATIONS),
        assumptions=dict(_DID_ASSUMPTIONS),
        when_to_use="Quasi-experimental design with dense panel data; untreated potential-outcome parallel trends assumption",
        when_not_to_use="Treatment and control have diverging pre-trends; no pre-period data; spillovers contaminate control",
        typical_min_obs=50,
        output_interpretation="ATT under declared identifying assumptions; pretrend diagnostics cannot establish identification.",
    )

    @staticmethod
    def pure_step(
        state: PanelObservationalData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        try:
            staggered = _legacy_staggered_flag(params)
        except ValueError as exc:
            return _invalid_did_request_output(data, str(exc))
        if staggered:
            return StaggeredDifferenceInDifferences.pure_step(data, params)
        return StandardDifferenceInDifferences.pure_step(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        for legacy_name, dedicated_name in (
            ("outcome_panel", "outcome"),
            ("treatment_indicator", "treatment"),
        ):
            if legacy_name in bound_inputs and dedicated_name in bound_inputs:
                raise ValueError(f"{legacy_name} and {dedicated_name} cannot both be supplied")
        payload = _did_payload(fallback_state)
        if "outcome_panel" in bound_inputs and "outcome" not in bound_inputs:
            payload["outcome"] = bound_inputs["outcome_panel"]
        if "treatment_indicator" in bound_inputs and "treatment" not in bound_inputs:
            payload["treatment"] = bound_inputs["treatment_indicator"]
        payload.update(
            {
                key: value
                for key, value in bound_inputs.items()
                if key not in {"outcome_panel", "treatment_indicator"}
            }
        )
        return PanelObservationalData.model_validate(payload)


@foundry_method(
    namespace="causal.inference.did",
    version="1.0.0",
    tags={"causal", "difference-in-differences"},
)
class StandardDifferenceInDifferences:
    """Dedicated standard 2x2 Difference-in-Differences estimator."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="standard",
        namespace="",
        version="0.0.0",
        input_slots=_standard_did_input_slots(),
        output_slots=_did_output_slots(),
        parameters=(
            ParameterSpec(name="cov_type", default="HC1"),
            ParameterSpec(name="cluster_var", default=None),
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
        description="Standard 2x2 DiD estimator.",
        tags=frozenset({"causal", "difference-in-differences"}),
        citations=_DID_CITATIONS,
        equations={"did_2x2": _DID_EQUATIONS["did_2x2"]},
        assumptions=dict(_DID_ASSUMPTIONS),
        when_to_use="Quasi-experimental design with dense panel data; untreated potential-outcome parallel trends assumption",
        when_not_to_use="Treatment and control have diverging pre-trends; no pre-period data; spillovers contaminate control",
        typical_min_obs=50,
        output_interpretation="ATT under declared identifying assumptions; pretrend diagnostics cannot establish identification.",
    )

    @staticmethod
    def pure_step(
        state: PanelObservationalData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        return _run_standard_did(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        return _materialize_did_data(bound_inputs, fallback_state)


@foundry_method(
    namespace="causal.inference.did",
    version="1.0.0",
    tags={"causal", "difference-in-differences"},
)
class StaggeredDifferenceInDifferences:
    """Estimate the fixed cohort-share scalar with iid panel-unit Mammen inference."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="staggered",
        namespace="",
        version="0.0.0",
        input_slots=_staggered_did_input_slots(),
        output_slots=_did_output_slots(),
        parameters=(
            ParameterSpec(name="control_group", default="never_treated"),
            ParameterSpec(name="n_bootstrap", default=1000),
            ParameterSpec(name="study_horizon", default=None),
            ParameterSpec(name="eligible_periods", default=None),
            ParameterSpec(name="null_effect", default=0.0),
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
        description="Fixed-horizon theta_sel DiD with estimated cohort shares and unit-shared Mammen inference.",
        tags=frozenset({"causal", "difference-in-differences"}),
        citations=_DID_CITATIONS,
        equations=dict(_DID_EQUATIONS),
        assumptions=dict(_DID_ASSUMPTIONS),
        when_to_use="Quasi-experimental design with dense panel data; untreated potential-outcome parallel trends assumption",
        when_not_to_use="Treatment and control have diverging pre-trends; no pre-period data; spillovers contaminate control",
        typical_min_obs=50,
        output_interpretation="ATT under declared identifying assumptions; pretrend diagnostics cannot establish identification.",
    )

    @staticmethod
    def target_contract(
        state: PanelObservationalData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Recompute the fixed scalar/data binding for a fresh native consumer."""

        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        return _staggered_target_contract(data, params)

    @staticmethod
    def pure_step(
        state: PanelObservationalData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        return _run_staggered_did(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        return _materialize_did_data(bound_inputs, fallback_state)


__all__ = [
    "DifferenceInDifferences",
    "StaggeredDifferenceInDifferences",
    "StandardDifferenceInDifferences",
]
