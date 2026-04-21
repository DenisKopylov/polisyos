"""Operator-valued causal estimators for multi-output and functional effects."""
from __future__ import annotations

import hashlib
import json
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
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal.treatment_effects import _logistic_propensity
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.kernel_causal import (
    KernelRegularization,
    OperatorConvergenceGuarantee,
    OperatorEffectBundle,
    OperatorEstimatorFamily,
    OperatorProbeExport,
)


def _operator_input_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("outcome", SlotType.MATRIX, Unit("outcome", "value")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "value")),
            SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value")),
        }
    )


def _operator_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("report", SlotType.SCALAR, Unit("report", "json")),
            SlotSpec("envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            SlotSpec("warnings", SlotType.SCALAR, Unit("warning", "list")),
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec("operator_effect_bundle", SlotType.SCALAR, Unit("result", "json")),
        }
    )


def _probe_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec("applied_probe", SlotType.SCALAR, Unit("result", "json")),
        }
    )


def _export_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec("probe_exports", SlotType.SCALAR, Unit("result", "json")),
        }
    )


def _as_matrix(value: Any, *, name: str, n_rows: int | None = None) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a vector or matrix")
    if n_rows is not None and arr.shape[0] != n_rows:
        raise ValueError(f"{name} must have {n_rows} rows")
    return arr


def _as_vector(value: Any, *, name: str, n_rows: int | None = None) -> np.ndarray:
    arr = np.asarray(value, dtype=float).reshape(-1)
    if n_rows is not None and arr.shape[0] != n_rows:
        raise ValueError(f"{name} must have {n_rows} rows")
    return arr


def _operator_payload(state: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    outcome = _as_matrix(state["outcome"], name="outcome")
    n_obs = outcome.shape[0]
    treatment = _as_vector(state["treatment"], name="treatment", n_rows=n_obs)
    covariates = _as_matrix(state.get("covariates", np.arange(n_obs, dtype=float).reshape(-1, 1)), name="covariates", n_rows=n_obs)
    effect_modifier = _as_matrix(state.get("effect_modifier", covariates), name="effect_modifier", n_rows=n_obs)
    metadata = dict(state.get("metadata", {})) if isinstance(state.get("metadata"), Mapping) else {}
    return outcome, treatment, covariates, effect_modifier, metadata


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _space_id(raw: Any, *, fallback: str) -> str:
    if isinstance(raw, Mapping):
        for key in ("space_id", "kernel_ref", "kind"):
            value = raw.get(key)
            if value:
                return str(value)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return fallback


def _resolve_regularization(params: Mapping[str, Any]) -> KernelRegularization:
    raw = params.get("regularization", params.get("operator_regularization"))
    if isinstance(raw, Mapping):
        try:
            return KernelRegularization.model_validate(dict(raw))
        except Exception:
            pass
    if isinstance(raw, (int, float)):
        return KernelRegularization(lambda_value=float(raw))
    return KernelRegularization()


def _resolve_treatment_values(treatment: np.ndarray, params: Mapping[str, Any]) -> tuple[float, float]:
    unique = np.unique(np.round(treatment.astype(float), 8))
    if unique.size == 0:
        raise ValueError("treatment vector is empty")
    raw_ref = params.get("reference_treatment")
    if isinstance(raw_ref, (int, float)):
        reference = float(raw_ref)
    else:
        reference = float(unique.min())
    raw_active = params.get("active_treatment_value")
    if isinstance(raw_active, (int, float)):
        active = float(raw_active)
    else:
        candidates = [float(value) for value in unique if not np.isclose(value, reference)]
        active = candidates[-1] if candidates else reference
    return active, reference


def _with_intercept(matrix: np.ndarray) -> np.ndarray:
    arr = np.asarray(matrix, dtype=float)
    if arr.ndim != 2:
        raise ValueError("design matrix must be 2D")
    return np.column_stack([np.ones(arr.shape[0]), arr])


def _ridge_solve(
    design: np.ndarray,
    target: np.ndarray,
    *,
    ridge: float,
    sample_weight: np.ndarray | None = None,
) -> np.ndarray:
    x = np.asarray(design, dtype=float)
    y = np.asarray(target, dtype=float)
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    if sample_weight is not None:
        w = np.sqrt(np.clip(np.asarray(sample_weight, dtype=float).reshape(-1), 1.0e-8, None))
        x = x * w[:, None]
        y = y * w[:, None]
    gram = x.T @ x + float(ridge) * np.eye(x.shape[1])
    rhs = x.T @ y
    return np.linalg.solve(gram, rhs)


def _rbf_kernel(left: np.ndarray, right: np.ndarray, *, lengthscale: float) -> np.ndarray:
    lhs = np.asarray(left, dtype=float)
    rhs = np.asarray(right, dtype=float)
    lhs_norm = np.sum(lhs * lhs, axis=1, keepdims=True)
    rhs_norm = np.sum(rhs * rhs, axis=1, keepdims=True).T
    sqdist = np.maximum(lhs_norm + rhs_norm - 2.0 * lhs @ rhs.T, 0.0)
    denom = max(lengthscale ** 2, 1.0e-8)
    return np.exp(-sqdist / (2.0 * denom))


def _median_lengthscale(features: np.ndarray) -> float:
    arr = np.asarray(features, dtype=float)
    if arr.shape[0] < 2:
        return 1.0
    diffs = arr[:, None, :] - arr[None, :, :]
    sqdist = np.sum(diffs * diffs, axis=2)
    values = sqdist[np.triu_indices(arr.shape[0], k=1)]
    values = values[np.isfinite(values) & (values > 0.0)]
    if values.size == 0:
        return 1.0
    return float(np.sqrt(np.median(values)))


def _krr_predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    eval_x: np.ndarray,
    *,
    ridge: float,
) -> np.ndarray:
    x_train = np.asarray(train_x, dtype=float)
    y_train = np.asarray(train_y, dtype=float)
    x_eval = np.asarray(eval_x, dtype=float)
    if y_train.ndim == 1:
        y_train = y_train.reshape(-1, 1)
    lengthscale = _median_lengthscale(x_train)
    gram = _rbf_kernel(x_train, x_train, lengthscale=lengthscale)
    alpha = np.linalg.solve(gram + float(ridge) * np.eye(gram.shape[0]), y_train)
    return _rbf_kernel(x_eval, x_train, lengthscale=lengthscale) @ alpha


def _evaluation_design(effect_modifier: np.ndarray, params: Mapping[str, Any]) -> tuple[np.ndarray, tuple[str, ...]]:
    raw_eval = params.get("evaluation_points")
    if raw_eval is not None:
        eval_points = _as_matrix(raw_eval, name="evaluation_points")
    else:
        max_points = int(params.get("max_evaluation_points", 32))
        max_points = max(1, min(max_points, effect_modifier.shape[0]))
        indices = np.linspace(0, effect_modifier.shape[0] - 1, num=max_points, dtype=int)
        eval_points = np.asarray(effect_modifier[indices], dtype=float)
    axis = tuple(f"v_{idx}" for idx in range(eval_points.shape[0]))
    return eval_points, axis


def _probe_basis(outcome_dim: int, params: Mapping[str, Any]) -> tuple[str, ...]:
    raw = params.get("probe_basis")
    if isinstance(raw, (list, tuple)) and raw:
        return tuple(str(item) for item in raw)
    return tuple(f"coord_{idx}" for idx in range(outcome_dim))


def _operator_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _residual_scale(residuals: np.ndarray) -> float:
    arr = np.asarray(residuals, dtype=float)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr * arr)))


def _probe_exports(
    operator_matrix: np.ndarray,
    *,
    probe_basis: tuple[str, ...],
    codomain_axis: tuple[str, ...],
    evaluation_points_ref: str | None = None,
) -> tuple[OperatorProbeExport, ...]:
    matrix = np.asarray(operator_matrix, dtype=float)
    exports: list[OperatorProbeExport] = []
    for index, probe_ref in enumerate(probe_basis):
        values = matrix[:, index] if matrix.size else np.array([], dtype=float)
        summary = {
            "mean_effect": float(np.mean(values)) if values.size else 0.0,
            "max_abs_effect": float(np.max(np.abs(values))) if values.size else 0.0,
        }
        exports.append(
            OperatorProbeExport(
                probe_ref=probe_ref,
                label=probe_ref,
                evaluation_points_ref=evaluation_points_ref,
                codomain_axis=codomain_axis,
                values=tuple(float(item) for item in values),
                summary=summary,
            )
        )
    return tuple(exports)


def _report_method(family: OperatorEstimatorFamily) -> CausalMethod:
    return {
        OperatorEstimatorFamily.CME_KRR: CausalMethod.KERNEL_CME,
        OperatorEstimatorFamily.OPERATOR_R_LEARNER: CausalMethod.DOUBLE_ML,
        OperatorEstimatorFamily.KIV: CausalMethod.KERNEL_IV,
        OperatorEstimatorFamily.PROXIMAL_MINIMAX: CausalMethod.KERNEL_PROXIMAL_MINIMAX,
    }[family]


def _default_guarantee(family: OperatorEstimatorFamily) -> OperatorConvergenceGuarantee:
    if family is OperatorEstimatorFamily.CME_KRR:
        return OperatorConvergenceGuarantee(
            guarantee_type="induced_operator",
            norm_kind="hy_to_l2_pv",
            rate_symbol="r_n",
            rate_statement="||T_hat - T||_op <= ||m_hat_a-m_a|| + ||m_hat_a'-m_a'||",
            theorem_family="induced_operator_from_embedding_regression",
            assumptions=(
                "conditional_exogeneity",
                "support_overlap",
                "bounded_kernel",
                "ridge_regularization",
            ),
            notes="Operator error inherits the embedding-valued regression rate.",
        )
    if family is OperatorEstimatorFamily.OPERATOR_R_LEARNER:
        return OperatorConvergenceGuarantee(
            guarantee_type="orthogonal_operator",
            norm_kind="hy_to_l2_pv",
            rate_symbol="r_n",
            theorem_family="orthogonal_r_learner_lift",
            assumptions=(
                "cross_fitting_or_stable_nuisances",
                "product_rate_restriction",
                "bounded_second_moments",
            ),
            notes="Orthogonalization reduces first-order nuisance bias before multi-output regression.",
        )
    if family is OperatorEstimatorFamily.KIV:
        return OperatorConvergenceGuarantee(
            guarantee_type="two_stage_operator",
            norm_kind="hy_to_l2_pv",
            rate_symbol="r_n",
            theorem_family="operator_kiv_consistency",
            assumptions=("valid_instrument", "relevance", "bounded_kernel", "ridge_regularization"),
            notes="Two-stage operator regression uses fitted treatment signal from instruments.",
        )
    return OperatorConvergenceGuarantee(
        guarantee_type="bridge_operator",
        norm_kind="hy_to_l2_pv",
        rate_symbol="r_n",
        theorem_family="proximal_minimax_operator",
        assumptions=("valid_proxy_bridge", "bounded_kernel", "regularized_bridge_solver"),
        notes="Proxy-augmented orthogonal surrogate for operator-valued bridge estimation.",
    )


def _operator_summary(
    operator_matrix: np.ndarray,
    *,
    family: OperatorEstimatorFamily,
    active_treatment: float,
    reference_treatment: float,
    codomain_axis: tuple[str, ...],
    probe_basis: tuple[str, ...],
    operator_norm_error_bound: float,
) -> dict[str, Any]:
    matrix = np.asarray(operator_matrix, dtype=float)
    row_means = np.mean(matrix, axis=1) if matrix.size else np.zeros(len(codomain_axis), dtype=float)
    point_estimate = float(np.mean(row_means)) if row_means.size else 0.0
    std_error = float(np.std(row_means, ddof=1) / np.sqrt(max(row_means.size, 1))) if row_means.size > 1 else 0.0
    return {
        "family": family.value,
        "active_treatment_value": active_treatment,
        "reference_treatment_value": reference_treatment,
        "point_estimate": point_estimate,
        "standard_error": std_error,
        "operator_norm_error_bound": float(operator_norm_error_bound),
        "n_evaluation_points": len(codomain_axis),
        "n_probes": len(probe_basis),
        "probe_basis": list(probe_basis),
        "codomain_axis": list(codomain_axis),
        "operator_matrix": matrix.tolist(),
    }


def _wrap_operator_success(
    *,
    family: OperatorEstimatorFamily,
    operator_matrix: np.ndarray,
    active_treatment: float,
    reference_treatment: float,
    n_obs: int,
    n_treated: int,
    n_control: int,
    bundle: OperatorEffectBundle,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    matrix = np.asarray(operator_matrix, dtype=float)
    row_means = np.mean(matrix, axis=1) if matrix.size else np.zeros(1, dtype=float)
    point_estimate = float(np.mean(row_means)) if row_means.size else 0.0
    if row_means.size > 1:
        std_error = float(np.std(row_means, ddof=1) / np.sqrt(row_means.size))
        ci = (point_estimate - 1.96 * std_error, point_estimate + 1.96 * std_error)
    else:
        ci = (point_estimate, point_estimate)
    report = build_success_report(
        method=_report_method(family),
        estimand="operator-valued causal effect",
        point_estimate=point_estimate,
        confidence_interval=ci,
        inference_method=f"{family.value}_finite_basis",
        sample_size=n_obs,
        n_treated=n_treated,
        n_control=n_control,
        pre_periods=0,
        post_periods=0,
        assumptions={
            "operator_target": "induced from multi-output causal regression",
            "probe_space": bundle.probe_space_ref,
            "codomain_space": bundle.codomain_space_ref,
        },
        metadata={
            "operator_ref": bundle.operator_ref,
            "operator_norm_error_bound": bundle.operator_norm_error_bound,
            "probe_basis": bundle.probe_basis,
            "codomain_axis": bundle.codomain_axis,
        },
    )
    result = _operator_summary(
        matrix,
        family=family,
        active_treatment=active_treatment,
        reference_treatment=reference_treatment,
        codomain_axis=bundle.codomain_axis,
        probe_basis=bundle.probe_basis,
        operator_norm_error_bound=bundle.operator_norm_error_bound or 0.0,
    )
    return wrap_causal_output(
        report,
        warnings=warnings or [],
        extras={
            "result": result,
            "operator_effect_bundle": bundle.model_dump(mode="json"),
            "applied_probe_exports": [item.model_dump(mode="json") for item in bundle.applied_probe_exports],
        },
    )


def _wrap_operator_failure(
    *,
    family: OperatorEstimatorFamily,
    reason: str,
) -> dict[str, Any]:
    report = build_failure_report(
        method=_report_method(family),
        status=EstimationStatus.INPUT_INVALID,
        reason=reason,
        estimand="operator-valued causal effect",
        sample_size=0,
        n_treated=0,
        n_control=0,
        pre_periods=0,
        post_periods=0,
        assumptions={"operator_target": "unsupported"},
    )
    return wrap_causal_output(
        report,
        warnings=[reason],
        extras={"result": {"status": "failed", "reason": reason}, "operator_effect_bundle": None},
    )


def _build_bundle(
    *,
    family: OperatorEstimatorFamily,
    operator_matrix: np.ndarray,
    probe_space_ref: str,
    codomain_space_ref: str,
    codomain_axis: tuple[str, ...],
    probe_basis: tuple[str, ...],
    regularization: KernelRegularization,
    operator_norm_error_bound: float,
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> OperatorEffectBundle:
    digest_payload = {
        "family": family.value,
        "probe_space_ref": probe_space_ref,
        "codomain_space_ref": codomain_space_ref,
        "probe_basis": probe_basis,
        "codomain_axis": codomain_axis,
        "base_estimand_ref": params.get("base_estimand_ref"),
        "metadata": metadata,
    }
    operator_ref = f"operator:{family.value}:{_operator_digest(digest_payload)}"
    evaluation_points_ref = str(params.get("evaluation_points_ref")) if params.get("evaluation_points_ref") else None
    return OperatorEffectBundle(
        operator_ref=operator_ref,
        estimand_hash=_operator_digest(digest_payload),
        probe_space_ref=probe_space_ref,
        codomain_space_ref=codomain_space_ref,
        estimator_family=family,
        regularization=regularization,
        probe_basis=probe_basis,
        codomain_axis=codomain_axis,
        operator_matrix=tuple(tuple(float(item) for item in row) for row in np.asarray(operator_matrix, dtype=float)),
        operator_norm_error_bound=float(max(operator_norm_error_bound, 0.0)),
        convergence_guarantee=_default_guarantee(family),
        applied_probe_exports=_probe_exports(
            np.asarray(operator_matrix, dtype=float),
            probe_basis=probe_basis,
            codomain_axis=codomain_axis,
            evaluation_points_ref=evaluation_points_ref,
        ),
        metadata=dict(metadata),
    )


def _cme_operator_fit(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    outcome, treatment, _, effect_modifier, metadata = _operator_payload(state)
    regularization = _resolve_regularization(params)
    active, reference = _resolve_treatment_values(treatment, params)
    treated_mask = np.isclose(treatment, active)
    control_mask = np.isclose(treatment, reference)
    if int(np.sum(treated_mask)) == 0 or int(np.sum(control_mask)) == 0:
        raise ValueError("operator cme/krr requires both active and reference treatment groups")
    eval_x, codomain_axis = _evaluation_design(effect_modifier, params)
    pred_treated = _krr_predict(
        effect_modifier[treated_mask],
        outcome[treated_mask],
        eval_x,
        ridge=regularization.lambda_value,
    )
    pred_control = _krr_predict(
        effect_modifier[control_mask],
        outcome[control_mask],
        eval_x,
        ridge=regularization.lambda_value,
    )
    operator_matrix = pred_treated - pred_control
    residuals = np.vstack(
        [
            outcome[treated_mask] - _krr_predict(effect_modifier[treated_mask], outcome[treated_mask], effect_modifier[treated_mask], ridge=regularization.lambda_value),
            outcome[control_mask] - _krr_predict(effect_modifier[control_mask], outcome[control_mask], effect_modifier[control_mask], ridge=regularization.lambda_value),
        ]
    )
    probe_basis = _probe_basis(outcome.shape[1], params)
    bundle = _build_bundle(
        family=OperatorEstimatorFamily.CME_KRR,
        operator_matrix=operator_matrix,
        probe_space_ref=_space_id(params.get("probe_space"), fallback="hy"),
        codomain_space_ref=_space_id(params.get("codomain_space"), fallback="hv"),
        codomain_axis=codomain_axis,
        probe_basis=probe_basis,
        regularization=regularization,
        operator_norm_error_bound=_residual_scale(residuals),
        params=params,
        metadata={
            **metadata,
            "operator_semantics": params.get("operator_semantics", "conditional_mean_embedding_operator"),
            "identification_scope": params.get("identification_scope", "backdoor"),
        },
    )
    return _wrap_operator_success(
        family=OperatorEstimatorFamily.CME_KRR,
        operator_matrix=operator_matrix,
        active_treatment=active,
        reference_treatment=reference,
        n_obs=outcome.shape[0],
        n_treated=int(np.sum(treated_mask)),
        n_control=int(np.sum(control_mask)),
        bundle=bundle,
    )


def _rlearner_operator_fit(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    outcome, treatment, covariates, effect_modifier, metadata = _operator_payload(state)
    regularization = _resolve_regularization(params)
    active, reference = _resolve_treatment_values(treatment, params)
    binary_treatment = np.isclose(treatment, active).astype(float)
    propensity = _logistic_propensity(covariates, binary_treatment)
    outcome_coef = _ridge_solve(_with_intercept(covariates), outcome, ridge=regularization.lambda_value)
    mu_hat = _with_intercept(covariates) @ outcome_coef
    treatment_residual = np.clip(binary_treatment - propensity, -0.95, 0.95)
    pseudo = (outcome - mu_hat) / np.clip(treatment_residual[:, None], -0.95, 0.95)
    tau_coef = _ridge_solve(
        _with_intercept(effect_modifier),
        pseudo,
        ridge=regularization.lambda_value,
        sample_weight=treatment_residual ** 2,
    )
    eval_x, codomain_axis = _evaluation_design(effect_modifier, params)
    operator_matrix = _with_intercept(eval_x) @ tau_coef
    residuals = pseudo - (_with_intercept(effect_modifier) @ tau_coef)
    probe_basis = _probe_basis(outcome.shape[1], params)
    bundle = _build_bundle(
        family=OperatorEstimatorFamily.OPERATOR_R_LEARNER,
        operator_matrix=operator_matrix,
        probe_space_ref=_space_id(params.get("probe_space"), fallback="hy"),
        codomain_space_ref=_space_id(params.get("codomain_space"), fallback="hv"),
        codomain_axis=codomain_axis,
        probe_basis=probe_basis,
        regularization=regularization,
        operator_norm_error_bound=_residual_scale(residuals),
        params=params,
        metadata={
            **metadata,
            "operator_semantics": params.get("operator_semantics", "counterfactual_probe_operator"),
            "identification_scope": params.get("identification_scope", "backdoor"),
        },
    )
    return _wrap_operator_success(
        family=OperatorEstimatorFamily.OPERATOR_R_LEARNER,
        operator_matrix=operator_matrix,
        active_treatment=active,
        reference_treatment=reference,
        n_obs=outcome.shape[0],
        n_treated=int(np.sum(binary_treatment > 0.5)),
        n_control=int(np.sum(binary_treatment <= 0.5)),
        bundle=bundle,
    )


def _interaction_design(effect_modifier: np.ndarray, signal: np.ndarray) -> np.ndarray:
    base = _as_matrix(effect_modifier, name="effect_modifier")
    scalar_signal = _as_vector(signal, name="signal", n_rows=base.shape[0])
    return np.column_stack([np.ones(base.shape[0]), base, scalar_signal[:, None], base * scalar_signal[:, None]])


def _interaction_effect_matrix(
    coef: np.ndarray,
    eval_x: np.ndarray,
    *,
    active_treatment: float,
    reference_treatment: float,
) -> np.ndarray:
    design_active = _interaction_design(eval_x, np.full(eval_x.shape[0], active_treatment, dtype=float))
    design_reference = _interaction_design(eval_x, np.full(eval_x.shape[0], reference_treatment, dtype=float))
    return design_active @ coef - design_reference @ coef


def _kiv_operator_fit(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    outcome, treatment, covariates, effect_modifier, metadata = _operator_payload(state)
    instrument = _as_matrix(state.get("instrument"), name="instrument", n_rows=outcome.shape[0])
    regularization = _resolve_regularization(params)
    active, reference = _resolve_treatment_values(treatment, params)
    stage1_coef = _ridge_solve(
        _with_intercept(np.column_stack([instrument, covariates])),
        treatment,
        ridge=regularization.lambda_value,
    )
    fitted_treatment = (_with_intercept(np.column_stack([instrument, covariates])) @ stage1_coef).reshape(-1)
    stage2_coef = _ridge_solve(
        _interaction_design(effect_modifier, fitted_treatment),
        outcome,
        ridge=regularization.lambda_value,
    )
    eval_x, codomain_axis = _evaluation_design(effect_modifier, params)
    operator_matrix = _interaction_effect_matrix(
        stage2_coef,
        eval_x,
        active_treatment=active,
        reference_treatment=reference,
    )
    residuals = outcome - (_interaction_design(effect_modifier, fitted_treatment) @ stage2_coef)
    probe_basis = _probe_basis(outcome.shape[1], params)
    bundle = _build_bundle(
        family=OperatorEstimatorFamily.KIV,
        operator_matrix=operator_matrix,
        probe_space_ref=_space_id(params.get("probe_space"), fallback="hy"),
        codomain_space_ref=_space_id(params.get("codomain_space"), fallback="hv"),
        codomain_axis=codomain_axis,
        probe_basis=probe_basis,
        regularization=regularization,
        operator_norm_error_bound=_residual_scale(residuals),
        params=params,
        metadata={
            **metadata,
            "operator_semantics": params.get("operator_semantics", "conditional_mean_embedding_operator"),
            "identification_scope": params.get("identification_scope", "iv"),
        },
    )
    treated_mask = np.isclose(treatment, active)
    control_mask = np.isclose(treatment, reference)
    return _wrap_operator_success(
        family=OperatorEstimatorFamily.KIV,
        operator_matrix=operator_matrix,
        active_treatment=active,
        reference_treatment=reference,
        n_obs=outcome.shape[0],
        n_treated=int(np.sum(treated_mask)),
        n_control=int(np.sum(control_mask)),
        bundle=bundle,
    )


def _proximal_operator_fit(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    outcome, treatment, covariates, effect_modifier, metadata = _operator_payload(state)
    regularization = _resolve_regularization(params)
    active, reference = _resolve_treatment_values(treatment, params)
    treatment_proxy = _as_matrix(
        state.get("treatment_proxy", state.get("instrument", covariates)),
        name="treatment_proxy",
        n_rows=outcome.shape[0],
    )
    outcome_proxy = _as_matrix(
        state.get("outcome_proxy", covariates),
        name="outcome_proxy",
        n_rows=outcome.shape[0],
    )
    proxy_design = np.column_stack([covariates, treatment_proxy, outcome_proxy])
    binary_treatment = np.isclose(treatment, active).astype(float)
    propensity = _logistic_propensity(proxy_design, binary_treatment)
    outcome_coef = _ridge_solve(_with_intercept(proxy_design), outcome, ridge=regularization.lambda_value)
    mu_hat = _with_intercept(proxy_design) @ outcome_coef
    treatment_residual = np.clip(binary_treatment - propensity, -0.95, 0.95)
    pseudo = (outcome - mu_hat) / np.clip(treatment_residual[:, None], -0.95, 0.95)
    tau_coef = _ridge_solve(
        _with_intercept(effect_modifier),
        pseudo,
        ridge=regularization.lambda_value,
        sample_weight=treatment_residual ** 2,
    )
    eval_x, codomain_axis = _evaluation_design(effect_modifier, params)
    operator_matrix = _with_intercept(eval_x) @ tau_coef
    residuals = pseudo - (_with_intercept(effect_modifier) @ tau_coef)
    probe_basis = _probe_basis(outcome.shape[1], params)
    bundle = _build_bundle(
        family=OperatorEstimatorFamily.PROXIMAL_MINIMAX,
        operator_matrix=operator_matrix,
        probe_space_ref=_space_id(params.get("probe_space"), fallback="hy"),
        codomain_space_ref=_space_id(params.get("codomain_space"), fallback="hv"),
        codomain_axis=codomain_axis,
        probe_basis=probe_basis,
        regularization=regularization,
        operator_norm_error_bound=_residual_scale(residuals),
        params=params,
        metadata={
            **metadata,
            "operator_semantics": params.get("operator_semantics", "conditional_mean_embedding_operator"),
            "identification_scope": params.get("identification_scope", "proximal"),
        },
    )
    return _wrap_operator_success(
        family=OperatorEstimatorFamily.PROXIMAL_MINIMAX,
        operator_matrix=operator_matrix,
        active_treatment=active,
        reference_treatment=reference,
        n_obs=outcome.shape[0],
        n_treated=int(np.sum(binary_treatment > 0.5)),
        n_control=int(np.sum(binary_treatment <= 0.5)),
        bundle=bundle,
    )


def _load_bundle(payload: Any) -> OperatorEffectBundle:
    if isinstance(payload, OperatorEffectBundle):
        return payload
    if isinstance(payload, Mapping):
        return OperatorEffectBundle.model_validate(dict(payload))
    raise TypeError("operator_effect_bundle must be a mapping payload")


def _resolve_probe_weights(
    bundle: OperatorEffectBundle,
    params: Mapping[str, Any],
) -> tuple[str, np.ndarray]:
    probe_ref = params.get("probe_ref")
    if probe_ref is not None:
        probe_ref = str(probe_ref)
        for export in bundle.applied_probe_exports:
            if export.probe_ref == probe_ref:
                return probe_ref, np.asarray(export.values, dtype=float)
        if probe_ref in bundle.probe_basis:
            index = bundle.probe_basis.index(probe_ref)
            matrix = np.asarray(bundle.operator_matrix, dtype=float)
            return probe_ref, matrix[:, index]
    raw_weights = params.get("probe_weights")
    if isinstance(raw_weights, Mapping):
        weights = np.zeros(len(bundle.probe_basis), dtype=float)
        for key, value in raw_weights.items():
            if str(key) not in bundle.probe_basis:
                continue
            weights[bundle.probe_basis.index(str(key))] = float(value)
        matrix = np.asarray(bundle.operator_matrix, dtype=float)
        return "linear_combination", matrix @ weights
    raise ValueError("probe_ref or probe_weights must reference a valid operator probe")


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "rkhs", "cme", "krr"},
)
class OperatorCMEKRREstimator:
    """Estimate an operator-valued causal effect via multi-output conditional mean regression."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cme_krr",
        namespace="",
        version="0.0.0",
        input_slots=_operator_input_slots(),
        output_slots=_operator_output_slots(),
        parameters=(
            ParameterSpec(name="reference_treatment", default=0.0),
            ParameterSpec(name="max_evaluation_points", default=32),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Operator-valued plug-in estimator based on multi-output kernel ridge regression.",
        tags=frozenset({"causal", "operator-valued", "rkhs", "cme", "krr"}),
        citations=(
            "Micchelli, C.A. & Pontil, M. (2005). On learning vector-valued functions.",
            "Kadri, H. et al. (2016). Operator-valued kernels for learning from functional response data.",
        ),
        equations={
            "induced_operator": "(T_hat g)(v) = <m_hat_a(v) - m_hat_a'(v), g>_H",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Backdoor/frontdoor identified multi-output or functional causal targets with bounded RKHS probes.",
        when_not_to_use="No overlap between treatment groups, no bounded kernel choice, or operator lift not certified.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=100,
        output_interpretation="Finite-basis approximation to an operator-valued causal effect with probe exports for audit.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return _cme_operator_fit(state, params)
        except Exception as exc:
            return _wrap_operator_failure(
                family=OperatorEstimatorFamily.CME_KRR,
                reason=str(exc),
            )


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "orthogonal", "r-learner"},
)
class OperatorRLearnerEstimator:
    """Estimate an operator-valued effect with orthogonal residualization before multi-output regression."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="operator_r_learner",
        namespace="",
        version="0.0.0",
        input_slots=_operator_input_slots(),
        output_slots=_operator_output_slots(),
        parameters=(
            ParameterSpec(name="reference_treatment", default=0.0),
            ParameterSpec(name="max_evaluation_points", default=32),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Orthogonal operator-valued R-learner for multi-output causal effects.",
        tags=frozenset({"causal", "operator-valued", "orthogonal", "r-learner"}),
        citations=("Nie, X. & Wager, S. (2021). Quasi-oracle estimation of heterogeneous treatment effects.",),
        equations={"orthogonal_loss": "min_tau E[||Y-mu(X)-(A-e(X))tau(V)||^2 + lambda||tau||^2]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Binary treatment with operator targets where orthogonalization is preferred.",
        when_not_to_use="No usable propensity model or near-degenerate treatment residuals.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=150,
        output_interpretation="Finite-basis operator estimate using residualized multi-output treatment effect regression.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return _rlearner_operator_fit(state, params)
        except Exception as exc:
            return _wrap_operator_failure(
                family=OperatorEstimatorFamily.OPERATOR_R_LEARNER,
                reason=str(exc),
            )


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "iv", "kiv"},
)
class OperatorKIVEstimator:
    """Estimate an operator-valued causal effect with an instrument-driven two-stage regression."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="kiv",
        namespace="",
        version="0.0.0",
        input_slots=_operator_input_slots(),
        output_slots=_operator_output_slots(),
        parameters=(
            ParameterSpec(name="reference_treatment", default=0.0),
            ParameterSpec(name="max_evaluation_points", default=32),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Operator-valued IV estimator using a fitted treatment signal from instruments.",
        tags=frozenset({"causal", "operator-valued", "iv", "kiv"}),
        citations=("Singh, R., Sahani, M. & Gretton, A. (2019). Kernel instrumental variable regression.",),
        equations={"two_stage": "Y = f(V, A_hat) with A_hat learned from instruments"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Proof-certified IV operator targets with valid instruments and multi-output outcomes.",
        when_not_to_use="Weak instruments or missing instrument payload in runtime state.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=200,
        output_interpretation="Finite-basis operator estimate learned from a two-stage IV surrogate.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return _kiv_operator_fit(state, params)
        except Exception as exc:
            return _wrap_operator_failure(
                family=OperatorEstimatorFamily.KIV,
                reason=str(exc),
            )


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "proximal", "minimax"},
)
class OperatorProximalMinimaxEstimator:
    """Estimate an operator-valued proximal effect using proxy-augmented orthogonal regression."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="proximal_minimax",
        namespace="",
        version="0.0.0",
        input_slots=_operator_input_slots(),
        output_slots=_operator_output_slots(),
        parameters=(
            ParameterSpec(name="reference_treatment", default=0.0),
            ParameterSpec(name="max_evaluation_points", default=32),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Operator-valued proximal minimax surrogate with proxy-augmented residualization.",
        tags=frozenset({"causal", "operator-valued", "proximal", "minimax"}),
        citations=("Ghassami, A. et al. (2022). Minimax estimation of proximal causal effects.",),
        equations={"proxy_bridge": "tau(V) learned after proxy-augmented nuisance removal"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Proof-certified proximal operator targets with negative controls or proxy variables.",
        when_not_to_use="No proxy variables or bridge certificate is absent.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=200,
        output_interpretation="Finite-basis operator estimate from a proxy-augmented orthogonal surrogate.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return _proximal_operator_fit(state, params)
        except Exception as exc:
            return _wrap_operator_failure(
                family=OperatorEstimatorFamily.PROXIMAL_MINIMAX,
                reason=str(exc),
            )


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "probe-application"},
)
class OperatorApplyProbeMethod:
    """Apply a finite probe or probe combination to an operator-valued effect bundle."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="apply_probe",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=_probe_output_slots(),
        parameters=(
            ParameterSpec(name="probe_ref", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Apply a probe from the RKHS audit basis to a learned operator bundle.",
        tags=frozenset({"causal", "operator-valued", "probe-application"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Auditing or replaying a full operator artifact on a fixed probe.",
        when_not_to_use="No operator bundle is available upstream.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=0,
        output_interpretation="Function-valued or trajectory-valued effect induced by a specific probe.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        bundle_payload = state.get("operator_effect_bundle", state.get("result"))
        bundle = _load_bundle(bundle_payload)
        probe_ref, values = _resolve_probe_weights(bundle, params)
        applied_probe = {
            "probe_ref": probe_ref,
            "codomain_axis": list(bundle.codomain_axis),
            "values": [float(item) for item in values],
            "mean_effect": float(np.mean(values)) if values.size else 0.0,
            "max_abs_effect": float(np.max(np.abs(values))) if values.size else 0.0,
            "operator_ref": bundle.operator_ref,
        }
        return {"result": applied_probe, "applied_probe": applied_probe}


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "basis-export"},
)
class OperatorExportBasisMethod:
    """Export the finite probe audit basis from an operator-valued effect bundle."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="export_basis",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=_export_output_slots(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Export the finite audit basis carried by an operator-valued causal effect bundle.",
        tags=frozenset({"causal", "operator-valued", "basis-export"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Benchmarking, replay, or UI materialization of operator probe exports.",
        when_not_to_use="No operator bundle is available.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=0,
        output_interpretation="List of finite probe exports that make the operator artifact auditable.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        bundle_payload = state.get("operator_effect_bundle", state.get("result"))
        bundle = _load_bundle(bundle_payload)
        exports = [item.model_dump(mode="json") for item in bundle.applied_probe_exports]
        return {
            "result": {
                "operator_ref": bundle.operator_ref,
                "probe_basis": list(bundle.probe_basis),
                "codomain_axis": list(bundle.codomain_axis),
                "n_exports": len(exports),
            },
            "probe_exports": exports,
        }


@foundry_method(
    namespace="causal.operator",
    version="1.0.0",
    tags={"causal", "operator-valued", "unsupported"},
)
class OperatorUnsupportedTargetMethod:
    """Structured refusal for unsupported operator-valued target combinations."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ()
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="unsupported_target",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(),
        output_slots=_operator_output_slots(),
        parameters=(ParameterSpec(name="degraded_reason", default="unsupported_operator_combo"),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fail fast when an operator-valued target is outside the supported proof/runtime contract.",
        tags=frozenset({"causal", "operator-valued", "unsupported"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Compiler degraded mode when no supported operator backend exists.",
        when_not_to_use="A valid operator backend is available.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=0,
        output_interpretation="Non-actionable failure payload explaining why the operator target is unsupported.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del state
        reason = str(params.get("degraded_reason", "unsupported_operator_combo"))
        return _wrap_operator_failure(
            family=OperatorEstimatorFamily.CME_KRR,
            reason=reason,
        )


__all__ = [
    "OperatorApplyProbeMethod",
    "OperatorCMEKRREstimator",
    "OperatorExportBasisMethod",
    "OperatorKIVEstimator",
    "OperatorProximalMinimaxEstimator",
    "OperatorRLearnerEstimator",
    "OperatorUnsupportedTargetMethod",
]
