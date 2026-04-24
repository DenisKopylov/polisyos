"""Helpers for running PolicyOS methods inside benchmark suites."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np

from benchmarks.estimator_profiles import benchmark_selection_manifest_from_params


@dataclasses.dataclass
class ExtractedPolicyOSResult:
    ate_pred: float
    ate_ci_lower: float
    ate_ci_upper: float
    cate_pred: np.ndarray | None
    cate_raw: np.ndarray | None = None
    cate_calibrated: np.ndarray | None = None
    cate_ci_lower_values: np.ndarray | None = None
    cate_ci_upper_values: np.ndarray | None = None
    feature_importances: np.ndarray | None = None
    nuisance_diagnostics: dict[str, Any] | None = None
    nuisance_contract: dict[str, Any] | None = None
    nuisance_config: dict[str, Any] | None = None
    selection_manifest: dict[str, Any] | None = None
    hte_metadata: dict[str, Any] | None = None
    failed: bool = False
    fail_reason: str = ""


def _feature_names(data: Any) -> list[str]:
    raw_names = getattr(data, "feature_names", None)
    if raw_names is None:
        n_features = int(np.asarray(data.covariates).shape[1])
        return [f"X{idx}" for idx in range(n_features)]
    return [str(name) for name in raw_names]


def _resolve_feature_index(
    raw_name: Any,
    *,
    n_features: int,
    feature_names: list[str],
) -> int | None:
    if raw_name is None:
        return None
    if isinstance(raw_name, (int, np.integer)):
        index = int(raw_name)
        return index if 0 <= index < n_features else None
    try:
        numeric = int(str(raw_name).strip())
        if 0 <= numeric < n_features:
            return numeric
    except Exception:
        pass
    label = str(raw_name).strip()
    if label in feature_names:
        return feature_names.index(label)
    normalized = label.lstrip("Xx")
    try:
        index = int(normalized)
    except Exception:
        return None
    return index if 0 <= index < n_features else None


def _normalize_numeric_feature_vector(
    raw_values: Any,
    *,
    n_features: int,
) -> np.ndarray | None:
    try:
        values = np.asarray(raw_values, dtype=float).reshape(-1)
    except Exception:
        return None
    if values.size == n_features + 1:
        values = values[1:]
    if values.size != n_features:
        return None
    values = np.abs(values)
    total = float(np.sum(values))
    if total <= 0:
        return None
    return values / total


def _normalize_feature_importances(
    raw_feature_importances: Any,
    *,
    n_features: int,
    feature_names: list[str],
) -> np.ndarray | None:
    if raw_feature_importances is None:
        return None

    numeric_vector = _normalize_numeric_feature_vector(
        raw_feature_importances,
        n_features=n_features,
    )
    if numeric_vector is not None:
        return numeric_vector

    if not isinstance(raw_feature_importances, (list, tuple)):
        return None

    values = list(raw_feature_importances)
    if not values:
        return None

    by_index = np.zeros(n_features, dtype=float)
    populated = False
    positional_scores: list[float] = []

    for item in values:
        if isinstance(item, dict):
            raw_name = (
                item.get("feature_name")
                or item.get("name")
                or item.get("feature")
                or item.get("index")
            )
            raw_score = (
                item.get("importance_score")
                if item.get("importance_score") is not None
                else item.get("importance")
            )
            if raw_score is None:
                raw_score = item.get("score", item.get("value"))
        else:
            raw_name = (
                getattr(item, "feature_name", None)
                or getattr(item, "name", None)
                or getattr(item, "feature", None)
                or getattr(item, "index", None)
            )
            raw_score = getattr(item, "importance_score", None)
            if raw_score is None:
                raw_score = getattr(item, "importance", None)
            if raw_score is None:
                raw_score = getattr(item, "score", None)
            if raw_score is None:
                raw_score = getattr(item, "value", None)

        try:
            numeric_score = abs(float(raw_score))
        except Exception:
            continue

        positional_scores.append(numeric_score)
        index = _resolve_feature_index(
            raw_name,
            n_features=n_features,
            feature_names=feature_names,
        )
        if index is None:
            continue
        by_index[index] = numeric_score
        populated = True

    if populated:
        total = float(np.sum(by_index))
        return by_index / total if total > 0 else None

    return _normalize_numeric_feature_vector(positional_scores, n_features=n_features)


def build_observational_state(data: Any) -> dict[str, Any]:
    return {
        "X": np.asarray(data.covariates, dtype=float),
        "treatment": np.asarray(data.treatment, dtype=float),
        "outcome": np.asarray(data.outcome, dtype=float),
    }


def invoke_policyos_method(
    method_class: type,
    data: Any,
    params: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    for state in (data, build_observational_state(data)):
        try:
            return method_class.pure_step(state, params)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("; ".join(error for error in errors if error) or "PolicyOS method failed")


def extract_policyos_result(
    method_class: type,
    data: Any,
    result: dict[str, Any],
) -> ExtractedPolicyOSResult:
    def _selection_manifest_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        nuisance_contract = payload.get("nuisance_contract") or {}
        nuisance_diagnostics = payload.get("nuisance_diagnostics") or {}
        selection_manifest = payload.get("selection_manifest")
        if isinstance(selection_manifest, dict):
            return selection_manifest
        return benchmark_selection_manifest_from_params(
            {
                "propensity_backend": next(
                    iter(nuisance_diagnostics.get("propensity_backends", [])), None
                )
                or nuisance_contract.get("propensity_backend"),
                "outcome_backend": next(
                    iter(nuisance_diagnostics.get("outcome_backends", [])), None
                )
                or nuisance_contract.get("outcome_backend"),
                "propensity_backend_candidates": nuisance_contract.get(
                    "propensity_backend_candidates"
                ),
                "outcome_backend_candidates": nuisance_contract.get("outcome_backend_candidates"),
                "selection_objective": nuisance_contract.get("selection_objective"),
                "split_policy": nuisance_contract.get("overlap_diagnostic_policy"),
                "calibration_mode": next(
                    iter(nuisance_diagnostics.get("calibration_modes", [])), None
                ),
            }
        )

    report = result.get("report")
    hte = result.get("hte_result")
    if report is not None and getattr(report, "point_estimate", None) is not None:
        ate_pred = float(report.point_estimate)
        interval = getattr(report, "confidence_interval", None)
        if interval is not None and len(interval) == 2:
            ate_ci_lower = float(interval[0])
            ate_ci_upper = float(interval[1])
        elif (
            getattr(report, "ci_lower", None) is not None
            and getattr(report, "ci_upper", None) is not None
        ):
            ate_ci_lower = float(report.ci_lower)
            ate_ci_upper = float(report.ci_upper)
        elif (
            hte is not None
            and getattr(hte, "ate_ci_lower", None) is not None
            and getattr(hte, "ate_ci_upper", None) is not None
        ):
            ate_ci_lower = float(hte.ate_ci_lower)
            ate_ci_upper = float(hte.ate_ci_upper)
        else:
            ate_ci_lower = ate_pred - 0.5
            ate_ci_upper = ate_pred + 0.5

        cate_pred = None
        raw_cate_values = getattr(hte, "cate_values", None) if hte is not None else None
        if raw_cate_values is not None:
            cate_pred = np.asarray(raw_cate_values, dtype=float)
        cate_ci_lower_values = None
        cate_ci_upper_values = None
        if hte is not None and getattr(hte, "cate_ci_lower_values", None) is not None:
            cate_ci_lower_values = np.asarray(getattr(hte, "cate_ci_lower_values"), dtype=float)
        if hte is not None and getattr(hte, "cate_ci_upper_values", None) is not None:
            cate_ci_upper_values = np.asarray(getattr(hte, "cate_ci_upper_values"), dtype=float)

        feature_importances = None
        raw_feature_importances = (
            getattr(hte, "feature_importances", None) if hte is not None else None
        )
        if raw_feature_importances is not None:
            n_features = int(np.asarray(data.covariates).shape[1])
            feature_importances = _normalize_feature_importances(
                raw_feature_importances,
                n_features=n_features,
                feature_names=_feature_names(data),
            )

        method_params = getattr(report, "method_params", None) or {}
        hte_meta = getattr(hte, "metadata", None) if hte is not None else {}
        selection_manifest = benchmark_selection_manifest_from_params(
            {
                **dict(method_params),
                "selection_objective": (hte_meta or {}).get("selection_objective")
                or method_params.get("selection_objective"),
                "split_policy": (hte_meta or {}).get("split_policy")
                or method_params.get("split_policy"),
                "calibration_mode": (hte_meta or {}).get("calibration_mode")
                or method_params.get("calibration_mode"),
            },
            method_label=method_class.__name__,
        )

        return ExtractedPolicyOSResult(
            ate_pred=ate_pred,
            ate_ci_lower=ate_ci_lower,
            ate_ci_upper=ate_ci_upper,
            cate_pred=cate_pred,
            cate_raw=cate_pred,
            cate_calibrated=cate_pred,
            cate_ci_lower_values=cate_ci_lower_values,
            cate_ci_upper_values=cate_ci_upper_values,
            feature_importances=feature_importances,
            selection_manifest=selection_manifest,
            hte_metadata=getattr(hte, "metadata", None) if hte is not None else None,
        )

    payload = result.get("result")
    if isinstance(payload, dict) and payload.get("ate") is not None:
        ate_pred = float(payload["ate"])
        ate_ci_lower = float(payload.get("ci_lower", ate_pred - 0.5))
        ate_ci_upper = float(payload.get("ci_upper", ate_pred + 0.5))

        cate_pred = None
        raw_cate = payload.get("cate_predictions")
        if raw_cate is not None:
            cate_pred = np.asarray(raw_cate, dtype=float)
        cate_ci_lower_values = None
        cate_ci_upper_values = None
        if payload.get("cate_ci_lower_values") is not None:
            cate_ci_lower_values = np.asarray(payload.get("cate_ci_lower_values"), dtype=float)
        if payload.get("cate_ci_upper_values") is not None:
            cate_ci_upper_values = np.asarray(payload.get("cate_ci_upper_values"), dtype=float)

        feature_importances = None
        raw_feature_importances = payload.get("feature_importances") or payload.get(
            "cate_feature_importances"
        )
        if raw_feature_importances is not None:
            n_features = int(np.asarray(data.covariates).shape[1])
            feature_importances = _normalize_feature_importances(
                raw_feature_importances,
                n_features=n_features,
                feature_names=_feature_names(data),
            )

        raw_coeffs = payload.get("cate_coefficients")
        if feature_importances is None and raw_coeffs is not None:
            feature_importances = _normalize_numeric_feature_vector(
                raw_coeffs,
                n_features=int(np.asarray(data.covariates).shape[1]),
            )

        return ExtractedPolicyOSResult(
            ate_pred=ate_pred,
            ate_ci_lower=ate_ci_lower,
            ate_ci_upper=ate_ci_upper,
            cate_pred=cate_pred,
            cate_raw=cate_pred,
            cate_calibrated=cate_pred,
            cate_ci_lower_values=cate_ci_lower_values,
            cate_ci_upper_values=cate_ci_upper_values,
            feature_importances=feature_importances,
            nuisance_diagnostics=payload.get("nuisance_diagnostics"),
            nuisance_contract=payload.get("nuisance_contract"),
            nuisance_config=payload.get("nuisance_config"),
            selection_manifest=_selection_manifest_from_payload(payload),
            hte_metadata=payload.get("metadata"),
        )

    fail_reason = getattr(report, "status_reason", None) if report is not None else None
    return ExtractedPolicyOSResult(
        ate_pred=float("nan"),
        ate_ci_lower=float("nan"),
        ate_ci_upper=float("nan"),
        cate_pred=None,
        feature_importances=None,
        failed=True,
        fail_reason=fail_reason
        or f"unsupported PolicyOS benchmark payload from {method_class.__name__}",
    )
