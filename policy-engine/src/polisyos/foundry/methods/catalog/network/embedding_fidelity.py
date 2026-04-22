"""Fail-closed diagnostics for causal faithfulness of network embeddings."""
from __future__ import annotations

from collections.abc import Mapping
from statistics import NormalDist
from typing import Any

import numpy as np

from polisyos.ir.analytics.network_embedding import (
    EmbeddingFidelityAction,
    EmbeddingFidelityStatus,
    NetworkEmbeddingFidelityCertificate,
)

_RESERVED_STATE_KEYS = {
    "adjacency",
    "adjacency_matrix",
    "ci_specs",
    "columns",
    "covariates",
    "directed",
    "edge_index",
    "edge_weight",
    "embedding",
    "embedding_family",
    "embedding_matrix",
    "environment",
    "environments",
    "network_data",
    "node_features",
    "node_ids",
    "node_states",
    "outcome",
    "separator_matrix",
    "separator_names",
    "separators",
    "treatment",
    "variables",
}


def compute_embedding_fidelity_certificate(
    state: Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute a task-relative network embedding fidelity certificate."""

    state_map = _flatten_state(state)
    params_map = dict(params or {})
    embedding = _coerce_matrix(
        _first_present(state_map, "embedding_matrix", "embedding", "transformed"),
        field_name="embedding_matrix",
    )
    n_obs = int(embedding.shape[0])
    family = str(
        _first_present(state_map, "embedding_family", "family", "method_name")
        or params_map.get("embedding_family")
        or "other"
    ).strip().lower()

    adjacency = _resolve_adjacency(state_map, n_obs=n_obs)
    covariates = _optional_matrix(
        _first_present(state_map, "covariates", "node_features"),
        n_obs=n_obs,
    )
    treatment = _optional_vector(state_map.get("treatment"), n_obs=n_obs)
    outcome = _optional_vector(state_map.get("outcome"), n_obs=n_obs)
    environment = _optional_vector(
        _first_present(state_map, "environment", "environments", "env", "domain"),
        n_obs=n_obs,
    )
    ci_specs = _normalize_ci_specs(state_map.get("ci_specs"))
    separators = _separator_mapping(state_map, n_obs=n_obs)

    assumptions = [
        "recoverability uses cross-fitted linear reconstruction from embedding and optional covariates",
        "residual dependence uses linear residualization and partial-correlation screening",
        "effect drift uses a linear backdoor proxy check on raw versus embedding-derived separators",
        "green certification remains task-relative to the provided CI specifications and raw separators",
    ]
    failure_modes: list[str] = []
    design = _combine_design(embedding, covariates)

    predicted_separators: dict[str, np.ndarray] = {}
    recoverability_scores: dict[str, float] = {}
    recoverability_meta: dict[str, dict[str, Any]] = {}
    if separators:
        predicted_separators, recoverability_scores, recoverability_meta = _crossfit_recoverability(
            design,
            separators,
            seed=int(params_map.get("seed", params_map.get("__seed__", 0))),
            n_splits=max(2, int(params_map.get("crossfit_folds", 3))),
            ridge=float(params_map.get("ridge", 1.0e-3)),
        )
    else:
        failure_modes.append("raw_separator_matrix_missing")

    variable_lookup = _variable_lookup(state_map, n_obs=n_obs)
    residual_dependence_scores: dict[str, float] = {}
    adjusted_p_values: dict[str, float] | None = None
    ci_meta: dict[str, dict[str, float | int]] = {}
    if ci_specs and predicted_separators:
        residual_dependence_scores, raw_p_values, ci_meta = _residual_dependence_diagnostics(
            ci_specs,
            variable_lookup,
            raw_separators=separators,
            embedding_separators=predicted_separators,
            covariates=covariates,
        )
        adjusted_p_values = _benjamini_hochberg(raw_p_values)
    elif ci_specs:
        failure_modes.append("ci_specs_present_without_recoverable_separators")
    else:
        failure_modes.append("ci_specs_missing")

    collision_rate, collision_meta = _collision_rate(
        embedding,
        adjacency=adjacency,
        separators=separators,
        treatment=treatment,
        seed=int(params_map.get("seed", params_map.get("__seed__", 0))),
        threshold=float(params_map.get("collision_summary_distance_threshold", 1.5)),
        max_nodes=max(16, int(params_map.get("collision_max_nodes", 256))),
    )

    effect_drift_z: float | None = None
    effect_meta: dict[str, float] = {}
    if treatment is not None and outcome is not None and separators and predicted_separators:
        effect_drift_z, effect_meta = _effect_drift(
            outcome,
            treatment,
            covariates=covariates,
            raw_separators=separators,
            embedding_separators=predicted_separators,
        )
    else:
        failure_modes.append("effect_drift_inputs_incomplete")

    environment_stability: dict[str, float] = {}
    if environment is not None and predicted_separators:
        environment_stability = _environment_stability(
            environment,
            separators,
            predicted_separators,
            recoverability_meta,
        )

    effective_sample_size = _effective_sample_size(adjacency, n_obs=n_obs)
    thresholds = {
        "recoverability_green": float(params_map.get("recoverability_green_threshold", 0.90)),
        "recoverability_red": float(params_map.get("recoverability_red_threshold", 0.75)),
        "residual_gap_green": float(params_map.get("residual_gap_green_threshold", 0.05)),
        "residual_gap_red": float(params_map.get("residual_gap_red_threshold", 0.15)),
        "collision_green": float(params_map.get("collision_green_threshold", 0.05)),
        "collision_red": float(params_map.get("collision_red_threshold", 0.15)),
        "effect_drift_green": float(params_map.get("effect_drift_green_threshold", 1.0)),
        "effect_drift_red": float(params_map.get("effect_drift_red_threshold", 2.0)),
        "effective_sample_size_green": float(
            params_map.get("effective_sample_size_green_threshold", 200.0)
        ),
    }
    status, recommended_action, status_failures = _aggregate_status(
        recoverability_scores,
        residual_dependence_scores,
        collision_rate=collision_rate,
        effect_drift_z=effect_drift_z,
        effective_sample_size=effective_sample_size,
        ci_specs=ci_specs,
        separators_present=bool(separators),
        thresholds=thresholds,
    )
    failure_modes = _dedupe_strings([*failure_modes, *status_failures])

    certificate = NetworkEmbeddingFidelityCertificate(
        family=family or "other",
        status=status,
        exact_faithfulness_claimed=bool(params_map.get("exact_faithfulness_claimed", False)),
        target_ci_specs=ci_specs,
        recoverability_scores=recoverability_scores,
        residual_dependence_scores=residual_dependence_scores,
        adjusted_p_values=adjusted_p_values or None,
        collision_rate=collision_rate,
        effect_drift_z=effect_drift_z,
        environment_stability=environment_stability,
        effective_sample_size=effective_sample_size,
        assumptions=_dedupe_strings(assumptions),
        failure_modes=failure_modes,
        recommended_action=recommended_action,
        metadata={
            "n_observations": n_obs,
            "embedding_dim": int(embedding.shape[1]),
            "recoverability_metrics": {
                name: dict(meta) for name, meta in recoverability_meta.items()
            },
            "ci_diagnostics": {
                name: dict(meta) for name, meta in ci_meta.items()
            },
            "collision_diagnostics": collision_meta,
            "effect_drift_diagnostics": effect_meta,
            "thresholds": thresholds,
        },
    )
    return certificate.model_dump(mode="json")


def _flatten_state(state: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(state)
    nested = payload.get("network_data")
    if isinstance(nested, Mapping):
        payload = dict(nested)
        payload.update({key: value for key, value in dict(state).items() if key != "network_data"})
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        merged = dict(metadata)
        merged.update({key: value for key, value in payload.items() if key != "metadata"})
        return merged
    return payload


def maybe_compute_embedding_fidelity_certificate(
    state: Mapping[str, Any],
    params: Mapping[str, Any] | None = None,
    *,
    embedding: Any | None = None,
    embedding_family: str | None = None,
) -> dict[str, Any] | None:
    """Return an existing certificate or compute one when an embedding is available."""

    state_map = _flatten_state(state)
    existing = state_map.get("embedding_fidelity_certificate")
    if existing is not None:
        return NetworkEmbeddingFidelityCertificate.model_validate(existing).model_dump(mode="json")

    payload = dict(state_map)
    if embedding is not None:
        payload["embedding_matrix"] = embedding
    if embedding_family is not None and payload.get("embedding_family") is None:
        payload["embedding_family"] = embedding_family
    if _first_present(payload, "embedding_matrix", "embedding", "transformed") is None:
        return None
    try:
        return compute_embedding_fidelity_certificate(payload, params=params)
    except Exception as exc:
        family = str(
            payload.get("embedding_family")
            or embedding_family
            or _first_present(state_map, "embedding_family", "family", "method_name")
            or "other"
        ).strip().lower()
        return NetworkEmbeddingFidelityCertificate(
            family=family or "other",
            status=EmbeddingFidelityStatus.YELLOW,
            exact_faithfulness_claimed=False,
            assumptions=[
                "certificate fallback emitted after diagnostic runtime error",
            ],
            failure_modes=[f"certificate_runtime_error:{type(exc).__name__.lower()}"],
            recommended_action=EmbeddingFidelityAction.ALLOW_AS_NUISANCE_ONLY,
            metadata={"runtime_error": type(exc).__name__},
        ).model_dump(mode="json")


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _coerce_matrix(value: Any, *, field_name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    if array.ndim != 2:
        raise ValueError(f"{field_name} must be a 2D matrix")
    if np.issubdtype(array.dtype, np.number):
        return array.astype(float)
    return np.column_stack([_encode_numeric_vector(array[:, index]) for index in range(array.shape[1])])


def _optional_matrix(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    array = _coerce_matrix(value, field_name="matrix")
    if array.shape[0] != n_obs:
        raise ValueError("matrix rows must align with embedding_matrix")
    return array


def _optional_vector(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    vector = _encode_numeric_vector(value)
    if vector.shape[0] != n_obs:
        raise ValueError("vector length must align with embedding_matrix")
    return vector


def _encode_numeric_vector(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 2 and array.shape[1] == 1:
        array = array[:, 0]
    if array.ndim != 1:
        raise ValueError("expected a 1D vector")
    if np.issubdtype(array.dtype, np.number):
        return array.astype(float)
    _, encoded = np.unique(array.astype(str), return_inverse=True)
    return encoded.astype(float)


def _separator_mapping(state: Mapping[str, Any], *, n_obs: int) -> dict[str, np.ndarray]:
    raw = _first_present(state, "separator_matrix", "separators")
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        output: dict[str, np.ndarray] = {}
        for key, value in raw.items():
            vector = _optional_vector(value, n_obs=n_obs)
            if vector is not None:
                output[str(key)] = vector
        return output
    matrix = _coerce_matrix(raw, field_name="separator_matrix")
    if matrix.shape[0] != n_obs:
        raise ValueError("separator_matrix rows must align with embedding_matrix")
    names = state.get("separator_names")
    if not isinstance(names, list) or len(names) != matrix.shape[1]:
        names = [f"separator_{index}" for index in range(matrix.shape[1])]
    return {str(name): matrix[:, index].astype(float) for index, name in enumerate(names)}


def _resolve_adjacency(state: Mapping[str, Any], *, n_obs: int) -> np.ndarray | None:
    raw = _first_present(state, "adjacency_matrix", "adjacency")
    if raw is not None:
        matrix = np.asarray(raw, dtype=float)
        if matrix.ndim != 2 or matrix.shape != (n_obs, n_obs):
            raise ValueError("adjacency_matrix must be square and align with embedding_matrix")
        return matrix
    edge_index = state.get("edge_index")
    if edge_index is None:
        return None
    edge_array = np.asarray(edge_index, dtype=int)
    if edge_array.ndim != 2:
        raise ValueError("edge_index must be a 2D array")
    if edge_array.shape[0] == 2:
        src, dst = edge_array[0], edge_array[1]
    elif edge_array.shape[1] == 2:
        src, dst = edge_array[:, 0], edge_array[:, 1]
    else:
        raise ValueError("edge_index must have shape (2, m) or (m, 2)")
    adjacency = np.zeros((n_obs, n_obs), dtype=float)
    weights = state.get("edge_weight")
    edge_weight = (
        np.asarray(weights, dtype=float).reshape(-1)
        if weights is not None
        else np.ones(src.shape[0], dtype=float)
    )
    directed = bool(state.get("directed", False))
    for i, j, weight in zip(src, dst, edge_weight, strict=False):
        if 0 <= int(i) < n_obs and 0 <= int(j) < n_obs:
            adjacency[int(i), int(j)] += float(weight)
            if not directed:
                adjacency[int(j), int(i)] += float(weight)
    return adjacency


def _combine_design(embedding: np.ndarray, covariates: np.ndarray | None) -> np.ndarray:
    if covariates is None or covariates.size == 0:
        return np.asarray(embedding, dtype=float)
    return np.column_stack([covariates, embedding])


def _build_folds(n_obs: int, *, n_splits: int, seed: int) -> list[np.ndarray]:
    n_splits = max(2, min(int(n_splits), n_obs))
    rng = np.random.default_rng(seed)
    order = rng.permutation(n_obs)
    return [part for part in np.array_split(order, n_splits) if part.size]


def _crossfit_recoverability(
    design: np.ndarray,
    separators: Mapping[str, np.ndarray],
    *,
    seed: int,
    n_splits: int,
    ridge: float,
) -> tuple[dict[str, np.ndarray], dict[str, float], dict[str, dict[str, Any]]]:
    predictions: dict[str, np.ndarray] = {}
    scores: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}
    folds = _build_folds(int(design.shape[0]), n_splits=n_splits, seed=seed)
    for name, target in separators.items():
        discrete = _is_discrete_target(target)
        prediction = np.zeros(target.shape[0], dtype=float)
        for fold in folds:
            mask = np.ones(target.shape[0], dtype=bool)
            mask[fold] = False
            if discrete:
                prediction[fold] = _linear_classify(
                    design[mask],
                    target[mask],
                    design[fold],
                    ridge=ridge,
                )
            else:
                prediction[fold] = _linear_predict(
                    design[mask],
                    target[mask],
                    design[fold],
                    ridge=ridge,
                )
        predictions[name] = prediction
        if discrete:
            scores[name] = _macro_f1(target, prediction)
            metric = "macro_f1"
        else:
            scores[name] = _r_squared(target, prediction)
            metric = "r_squared"
        metadata[name] = {
            "metric": metric,
            "discrete_target": discrete,
            "folds": len(folds),
        }
    return predictions, scores, metadata


def _is_discrete_target(values: np.ndarray) -> bool:
    unique = np.unique(values)
    if unique.size <= 1:
        return True
    if unique.size > min(16, max(3, values.shape[0] // 5)):
        return False
    return bool(np.allclose(unique, np.round(unique)))


def _linear_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    ridge: float,
) -> np.ndarray:
    train_scaled, test_scaled = _standardize_from_train(x_train, x_test)
    design = np.column_stack([np.ones(train_scaled.shape[0]), train_scaled])
    gram = design.T @ design + ridge * np.eye(design.shape[1])
    coef = np.linalg.solve(gram, design.T @ y_train)
    return np.column_stack([np.ones(test_scaled.shape[0]), test_scaled]) @ coef


def _linear_classify(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    ridge: float,
) -> np.ndarray:
    classes = np.unique(y_train)
    if classes.size == 1:
        return np.full(x_test.shape[0], float(classes[0]), dtype=float)
    train_scaled, test_scaled = _standardize_from_train(x_train, x_test)
    design = np.column_stack([np.ones(train_scaled.shape[0]), train_scaled])
    targets = np.column_stack([(y_train == cls).astype(float) for cls in classes])
    gram = design.T @ design + ridge * np.eye(design.shape[1])
    coef = np.linalg.solve(gram, design.T @ targets)
    test_design = np.column_stack([np.ones(test_scaled.shape[0]), test_scaled])
    scores = test_design @ coef
    return classes[np.argmax(scores, axis=1)].astype(float)


def _standardize_from_train(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.mean(train, axis=0, keepdims=True)
    std = np.std(train, axis=0, keepdims=True)
    std = np.where(std > 1.0e-12, std, 1.0)
    return (train - mean) / std, (test - mean) / std


def _r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    centered = np.asarray(y_true, dtype=float) - float(np.mean(y_true))
    denom = float(np.sum(centered**2))
    if denom <= 1.0e-12:
        return 1.0
    resid = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(1.0 - np.sum(resid**2) / denom)


def _macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    classes = np.unique(np.concatenate([y_true, y_pred]))
    scores: list[float] = []
    for cls in classes:
        true_mask = y_true == cls
        pred_mask = y_pred == cls
        tp = float(np.sum(true_mask & pred_mask))
        fp = float(np.sum(~true_mask & pred_mask))
        fn = float(np.sum(true_mask & ~pred_mask))
        precision = tp / max(tp + fp, 1.0)
        recall = tp / max(tp + fn, 1.0)
        if precision + recall <= 1.0e-12:
            scores.append(0.0)
        else:
            scores.append(2.0 * precision * recall / (precision + recall))
    return float(np.mean(scores)) if scores else 0.0


def _variable_lookup(state: Mapping[str, Any], *, n_obs: int) -> dict[str, np.ndarray]:
    lookup: dict[str, np.ndarray] = {}
    for nested_key in ("columns", "variables"):
        nested = state.get(nested_key)
        if isinstance(nested, Mapping):
            for key, value in nested.items():
                vector = _try_vector(value, n_obs=n_obs)
                if vector is not None:
                    lookup[str(key)] = vector
    for key, value in state.items():
        if key in _RESERVED_STATE_KEYS:
            continue
        vector = _try_vector(value, n_obs=n_obs)
        if vector is not None:
            lookup[str(key)] = vector
    for key in ("treatment", "outcome", "environment", "environments"):
        vector = _try_vector(state.get(key), n_obs=n_obs)
        if vector is not None:
            lookup[key] = vector
    return lookup


def _try_vector(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    try:
        vector = _encode_numeric_vector(value)
    except ValueError:
        return None
    return vector if vector.shape[0] == n_obs else None


def _normalize_ci_specs(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("ci_specs must be a list of mappings")
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError("each ci_spec must be a mapping")
        name = str(item.get("name") or f"ci_spec_{index}").strip() or f"ci_spec_{index}"
        output.append({**dict(item), "name": name})
    return output


def _residual_dependence_diagnostics(
    ci_specs: list[dict[str, Any]],
    variable_lookup: Mapping[str, np.ndarray],
    *,
    raw_separators: Mapping[str, np.ndarray],
    embedding_separators: Mapping[str, np.ndarray],
    covariates: np.ndarray | None,
) -> tuple[dict[str, float], dict[str, float], dict[str, dict[str, float | int]]]:
    scores: dict[str, float] = {}
    p_values: dict[str, float] = {}
    metadata: dict[str, dict[str, float | int]] = {}
    for spec in ci_specs:
        left = _resolve_spec_vector(spec, "left", variable_lookup)
        right = _resolve_spec_vector(spec, "right", variable_lookup)
        if left is None or right is None:
            continue
        separator_names = _separator_names_for_spec(spec, raw_separators)
        raw_conditioning = _conditioning_matrix(covariates, raw_separators, separator_names, n_obs=left.shape[0])
        embedding_conditioning = _conditioning_matrix(
            covariates,
            embedding_separators,
            separator_names,
            n_obs=left.shape[0],
        )
        raw_corr = _partial_corr_abs(left, right, raw_conditioning)
        embedding_corr = _partial_corr_abs(left, right, embedding_conditioning)
        scores[str(spec["name"])] = float(max(0.0, embedding_corr - raw_corr))
        p_values[str(spec["name"])] = _correlation_p_value(
            embedding_corr,
            n_obs=int(left.shape[0]),
            conditioning_dim=int(embedding_conditioning.shape[1]),
        )
        metadata[str(spec["name"])] = {
            "raw_partial_corr_abs": float(raw_corr),
            "embedding_partial_corr_abs": float(embedding_corr),
            "conditioning_dim": int(embedding_conditioning.shape[1]),
        }
    return scores, p_values, metadata


def _resolve_spec_vector(
    spec: Mapping[str, Any],
    field_name: str,
    lookup: Mapping[str, np.ndarray],
) -> np.ndarray | None:
    values = spec.get(f"{field_name}_values")
    if values is not None:
        return _encode_numeric_vector(values)
    name = spec.get(field_name)
    if isinstance(name, str):
        return lookup.get(name)
    return None


def _separator_names_for_spec(
    spec: Mapping[str, Any],
    separators: Mapping[str, np.ndarray],
) -> list[str]:
    raw = spec.get("separator_names")
    if isinstance(raw, list):
        names = [str(item) for item in raw if str(item).strip()]
    elif isinstance(raw, str) and raw.strip():
        names = [raw]
    else:
        names = list(separators)
    return [name for name in names if name in separators]


def _conditioning_matrix(
    covariates: np.ndarray | None,
    separators: Mapping[str, np.ndarray],
    separator_names: list[str],
    *,
    n_obs: int,
) -> np.ndarray:
    columns: list[np.ndarray] = []
    if covariates is not None and covariates.size:
        columns.append(np.asarray(covariates, dtype=float))
    if separator_names:
        columns.append(
            np.column_stack([np.asarray(separators[name], dtype=float) for name in separator_names])
        )
    if not columns:
        return np.empty((n_obs, 0), dtype=float)
    return np.column_stack(columns)


def _partial_corr_abs(left: np.ndarray, right: np.ndarray, conditioning: np.ndarray) -> float:
    if conditioning.size == 0:
        return abs(_safe_corr(left, right))
    left_resid = _residualize(left, conditioning)
    right_resid = _residualize(right, conditioning)
    return abs(_safe_corr(left_resid, right_resid))


def _residualize(target: np.ndarray, design: np.ndarray) -> np.ndarray:
    if design.ndim != 2 or design.shape[0] != target.shape[0]:
        raise ValueError("conditioning design must align with target")
    design_matrix = np.column_stack([np.ones(design.shape[0]), design])
    coef, *_ = np.linalg.lstsq(design_matrix, target, rcond=None)
    return np.asarray(target, dtype=float) - design_matrix @ coef


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    lhs = np.asarray(left, dtype=float).reshape(-1)
    rhs = np.asarray(right, dtype=float).reshape(-1)
    mask = np.isfinite(lhs) & np.isfinite(rhs)
    if int(np.sum(mask)) < 3:
        return 0.0
    lhs = lhs[mask]
    rhs = rhs[mask]
    if float(np.std(lhs)) <= 1.0e-12 or float(np.std(rhs)) <= 1.0e-12:
        return 0.0
    return float(np.clip(np.corrcoef(lhs, rhs)[0, 1], -1.0, 1.0))


def _correlation_p_value(correlation: float, *, n_obs: int, conditioning_dim: int) -> float:
    if n_obs <= conditioning_dim + 3:
        return 1.0
    rho = float(np.clip(correlation, -0.999999, 0.999999))
    z_score = abs(np.arctanh(rho)) * np.sqrt(max(n_obs - conditioning_dim - 3, 1))
    return float(2.0 * (1.0 - NormalDist().cdf(z_score)))


def _benjamini_hochberg(p_values: Mapping[str, float]) -> dict[str, float]:
    if not p_values:
        return {}
    ordered = sorted(
        ((name, float(np.clip(value, 0.0, 1.0))) for name, value in p_values.items()),
        key=lambda item: item[1],
    )
    adjusted: dict[str, float] = {}
    running = 1.0
    total = len(ordered)
    for offset, (name, value) in enumerate(reversed(ordered), start=1):
        adjusted_value = min(running, value * total / float(total - offset + 1))
        running = adjusted_value
        adjusted[name] = float(np.clip(adjusted_value, 0.0, 1.0))
    return adjusted


def _collision_rate(
    embedding: np.ndarray,
    *,
    adjacency: np.ndarray | None,
    separators: Mapping[str, np.ndarray],
    treatment: np.ndarray | None,
    seed: int,
    threshold: float,
    max_nodes: int,
) -> tuple[float, dict[str, float]]:
    emb = _zscore_matrix(embedding)
    summaries = _collision_summary_matrix(
        adjacency=adjacency,
        separators=separators,
        treatment=treatment,
        n_obs=emb.shape[0],
    )
    summary = _zscore_matrix(summaries)
    n_obs = emb.shape[0]
    if n_obs <= 1:
        return 0.0, {"mean_neighbor_summary_distance": 0.0}
    rng = np.random.default_rng(seed)
    focus = (
        np.sort(rng.choice(n_obs, size=max_nodes, replace=False))
        if n_obs > max_nodes
        else np.arange(n_obs)
    )
    collisions: list[bool] = []
    summary_distances: list[float] = []
    embedding_distances: list[float] = []
    for index in focus:
        distances = np.linalg.norm(emb - emb[index], axis=1)
        distances[index] = np.inf
        neighbor = int(np.argmin(distances))
        summary_distance = float(np.linalg.norm(summary[index] - summary[neighbor]))
        summary_distances.append(summary_distance)
        embedding_distances.append(float(distances[neighbor]))
        collisions.append(summary_distance > threshold)
    close_cutoff = (
        float(np.quantile(embedding_distances, 0.35))
        if embedding_distances
        else 0.0
    )
    close_mask = [
        distance <= max(close_cutoff, 1.0e-9)
        for distance in embedding_distances
    ]
    close_count = max(int(np.sum(close_mask)), 1)
    return (
        (
            float(
                np.sum(
                    [
                        collided and is_close
                        for collided, is_close in zip(collisions, close_mask, strict=False)
                    ]
                )
                / close_count
            )
            if collisions
            else 0.0
        ),
        {
            "mean_neighbor_summary_distance": float(np.mean(summary_distances)) if summary_distances else 0.0,
            "mean_neighbor_embedding_distance": float(np.mean(embedding_distances)) if embedding_distances else 0.0,
            "close_neighbor_cutoff": close_cutoff,
            "close_neighbor_count": float(close_count),
            "nodes_screened": float(len(focus)),
        },
    )


def _collision_summary_matrix(
    *,
    adjacency: np.ndarray | None,
    separators: Mapping[str, np.ndarray],
    treatment: np.ndarray | None,
    n_obs: int,
) -> np.ndarray:
    columns: list[np.ndarray] = []
    if separators:
        columns.append(np.column_stack([np.asarray(value, dtype=float) for value in separators.values()]))
    if adjacency is not None:
        matrix = np.asarray(adjacency, dtype=float)
        columns.append(np.sum(matrix, axis=1, keepdims=True))
        columns.append(np.count_nonzero(matrix, axis=1).reshape(-1, 1).astype(float))
        if treatment is not None and not separators:
            weights = matrix.copy()
            row_sums = np.sum(weights, axis=1, keepdims=True)
            row_sums[row_sums == 0.0] = 1.0
            exposure = (weights / row_sums) @ np.asarray(treatment, dtype=float)
            columns.append(exposure.reshape(-1, 1))
    if not columns:
        return np.zeros((n_obs, 1), dtype=float)
    return np.column_stack(columns)


def _zscore_matrix(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    mean = np.mean(array, axis=0, keepdims=True)
    std = np.std(array, axis=0, keepdims=True)
    std = np.where(std > 1.0e-12, std, 1.0)
    return (array - mean) / std


def _effect_drift(
    outcome: np.ndarray,
    treatment: np.ndarray,
    *,
    covariates: np.ndarray | None,
    raw_separators: Mapping[str, np.ndarray],
    embedding_separators: Mapping[str, np.ndarray],
) -> tuple[float | None, dict[str, float]]:
    tau_raw, se_raw = _treatment_effect_ols(outcome, treatment, covariates, raw_separators)
    tau_emb, se_emb = _treatment_effect_ols(outcome, treatment, covariates, embedding_separators)
    if tau_raw is None or tau_emb is None:
        return None, {}
    pooled = float(np.sqrt(max((se_raw or 0.0) ** 2 + (se_emb or 0.0) ** 2, 1.0e-12)))
    return (
        float(abs(tau_raw - tau_emb) / pooled),
        {
            "tau_raw": float(tau_raw),
            "tau_embedding": float(tau_emb),
            "se_raw": float(se_raw or 0.0),
            "se_embedding": float(se_emb or 0.0),
            "pooled_standard_error": pooled,
        },
    )


def _treatment_effect_ols(
    outcome: np.ndarray,
    treatment: np.ndarray,
    covariates: np.ndarray | None,
    separators: Mapping[str, np.ndarray],
) -> tuple[float | None, float | None]:
    columns: list[np.ndarray] = [np.ones(outcome.shape[0], dtype=float), np.asarray(treatment, dtype=float)]
    if covariates is not None and covariates.size:
        columns.append(np.asarray(covariates, dtype=float))
    if separators:
        columns.append(np.column_stack([np.asarray(value, dtype=float) for value in separators.values()]))
    design = np.column_stack(columns)
    if design.shape[0] <= design.shape[1]:
        return None, None
    xtx_inv = np.linalg.pinv(design.T @ design)
    beta = xtx_inv @ design.T @ outcome
    resid = outcome - design @ beta
    dof = max(design.shape[0] - design.shape[1], 1)
    sigma2 = float(np.sum(resid**2) / dof)
    covariance = sigma2 * xtx_inv
    return float(beta[1]), float(np.sqrt(max(covariance[1, 1], 0.0)))


def _environment_stability(
    environment: np.ndarray,
    separators: Mapping[str, np.ndarray],
    predictions: Mapping[str, np.ndarray],
    recoverability_meta: Mapping[str, Mapping[str, Any]],
) -> dict[str, float]:
    labels = np.unique(environment)
    if labels.size < 2:
        return {}
    scores: list[float] = []
    for label in labels:
        mask = environment == label
        if int(np.sum(mask)) < 8:
            continue
        per_env: list[float] = []
        for name, actual in separators.items():
            predicted = predictions.get(name)
            if predicted is None:
                continue
            metric = str(recoverability_meta.get(name, {}).get("metric", "r_squared"))
            if metric == "macro_f1":
                per_env.append(_macro_f1(actual[mask], predicted[mask]))
            else:
                per_env.append(_r_squared(actual[mask], predicted[mask]))
        if per_env:
            scores.append(float(np.mean(per_env)))
    if len(scores) < 2:
        return {"n_environments": float(labels.size)}
    return {
        "n_environments": float(labels.size),
        "recoverability_span": float(max(scores) - min(scores)),
        "mean_environment_recoverability": float(np.mean(scores)),
    }


def _effective_sample_size(adjacency: np.ndarray | None, *, n_obs: int) -> float:
    if adjacency is None or n_obs <= 1:
        return float(n_obs)
    matrix = np.asarray(adjacency, dtype=float)
    mean_degree = float(np.mean(np.count_nonzero(matrix, axis=1)))
    density = float(np.count_nonzero(matrix) / max(n_obs * (n_obs - 1), 1))
    dependence_factor = 1.0 + mean_degree * density
    return float(max(1.0, n_obs / max(dependence_factor, 1.0)))


def _aggregate_status(
    recoverability_scores: Mapping[str, float],
    residual_dependence_scores: Mapping[str, float],
    *,
    collision_rate: float | None,
    effect_drift_z: float | None,
    effective_sample_size: float | None,
    ci_specs: list[dict[str, Any]],
    separators_present: bool,
    thresholds: Mapping[str, float],
) -> tuple[EmbeddingFidelityStatus, EmbeddingFidelityAction, list[str]]:
    failures: list[str] = []
    if recoverability_scores and min(recoverability_scores.values()) < thresholds["recoverability_red"]:
        failures.append("separator_recoverability_below_red_threshold")
    if residual_dependence_scores and max(residual_dependence_scores.values()) > thresholds["residual_gap_red"]:
        failures.append("residual_dependence_gap_above_red_threshold")
    if collision_rate is not None and collision_rate > thresholds["collision_red"]:
        failures.append("collision_rate_above_red_threshold")
    if effect_drift_z is not None and effect_drift_z > thresholds["effect_drift_red"]:
        failures.append("effect_drift_above_red_threshold")
    if failures:
        action = (
            EmbeddingFidelityAction.REQUIRE_BOUNDS
            if effect_drift_z is not None and effect_drift_z > thresholds["effect_drift_red"]
            else EmbeddingFidelityAction.REQUIRE_RAW_GRAPH_SUMMARIES
        )
        return EmbeddingFidelityStatus.RED, action, failures

    green_requirements_met = (
        separators_present
        and bool(recoverability_scores)
        and bool(ci_specs)
        and bool(residual_dependence_scores)
        and collision_rate is not None
        and effect_drift_z is not None
        and effective_sample_size is not None
        and min(recoverability_scores.values()) >= thresholds["recoverability_green"]
        and max(residual_dependence_scores.values()) <= thresholds["residual_gap_green"]
        and collision_rate <= thresholds["collision_green"]
        and effect_drift_z <= thresholds["effect_drift_green"]
        and effective_sample_size >= thresholds["effective_sample_size_green"]
    )
    if green_requirements_met:
        return (
            EmbeddingFidelityStatus.GREEN,
            EmbeddingFidelityAction.ALLOW_AS_ADJUSTMENT,
            [],
        )

    yellow_failures: list[str] = []
    if not separators_present:
        yellow_failures.append("raw_separators_missing_for_green_verdict")
    if not ci_specs:
        yellow_failures.append("ci_specs_missing_for_green_verdict")
    if not residual_dependence_scores and ci_specs:
        yellow_failures.append("residual_dependence_diagnostics_incomplete")
    if not recoverability_scores and separators_present:
        yellow_failures.append("recoverability_diagnostics_incomplete")
    if effect_drift_z is None:
        yellow_failures.append("effect_drift_diagnostic_unavailable")
    if effective_sample_size is not None and effective_sample_size < thresholds["effective_sample_size_green"]:
        yellow_failures.append("effective_sample_size_below_green_threshold")
    if recoverability_scores and min(recoverability_scores.values()) < thresholds["recoverability_green"]:
        yellow_failures.append("separator_recoverability_below_green_threshold")
    if residual_dependence_scores and max(residual_dependence_scores.values()) > thresholds["residual_gap_green"]:
        yellow_failures.append("residual_dependence_gap_above_green_threshold")
    if collision_rate is not None and collision_rate > thresholds["collision_green"]:
        yellow_failures.append("collision_rate_above_green_threshold")
    if effect_drift_z is not None and effect_drift_z > thresholds["effect_drift_green"]:
        yellow_failures.append("effect_drift_above_green_threshold")
    return (
        EmbeddingFidelityStatus.YELLOW,
        EmbeddingFidelityAction.ALLOW_AS_NUISANCE_ONLY,
        yellow_failures,
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


__all__ = [
    "compute_embedding_fidelity_certificate",
    "maybe_compute_embedding_fidelity_certificate",
]
