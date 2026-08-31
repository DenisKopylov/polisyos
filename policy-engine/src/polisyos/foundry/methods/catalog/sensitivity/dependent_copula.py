"""Dependent-copula sensitivity estimators for correlated inputs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel

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

_DEFAULT_REFERENCE_COPULA_ID = "product_reference"
_DEFAULT_SIGN_TOLERANCE = 1e-10
_VALID_STRUCTURAL_LEVELS = {"distributional", "ordered_generating", "causal"}


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", by_alias=True)
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"expected mapping-like payload, got {type(value).__name__}")


def _get(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _copula_family(copula: Mapping[str, Any] | None, *, default: str = "gaussian") -> str:
    if not copula:
        return default
    return str(_get(copula, "family", default=default)).strip().lower()


def _copula_id(copula: Mapping[str, Any] | None, *, default: str) -> str:
    if not copula:
        return default
    return str(_get(copula, "id", default=default)).strip() or default


def _reference_copula_id_from_params(params: Mapping[str, Any]) -> str | None:
    explicit = params.get("reference_copula_id") or params.get("referenceCopulaId")
    if explicit:
        return str(explicit)
    estimator = _as_mapping(params.get("estimator") or params.get("estimatorSpec"))
    explicit = estimator.get("reference_copula_id") or estimator.get("referenceCopulaId")
    if explicit:
        return str(explicit)
    estimators = params.get("estimators")
    if isinstance(estimators, Sequence) and not isinstance(estimators, (str, bytes)):
        first = _as_mapping(estimators[0] if estimators else None)
        explicit = first.get("reference_copula_id") or first.get("referenceCopulaId")
        if explicit:
            return str(explicit)
    return None


def _select_reference_copula(
    reference_payload: Any,
    *,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    requested_id = _reference_copula_id_from_params(params)
    if isinstance(reference_payload, Sequence) and not isinstance(reference_payload, (str, bytes)):
        references = [_as_mapping(item) for item in reference_payload]
        if requested_id:
            for reference in references:
                if _copula_id(reference, default="") == requested_id:
                    return reference
            raise ValueError(f"unknown reference_copula_id: {requested_id!r}")
        return _as_mapping(references[0] if references else None)

    reference = _as_mapping(reference_payload)
    if requested_id and reference and _copula_id(reference, default="") != requested_id:
        raise ValueError(f"unknown reference_copula_id: {requested_id!r}")
    return reference


def _extract_distribution(params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    joint = _as_mapping(params.get("joint_distribution") or params.get("jointDistribution"))
    observed = _as_mapping(
        params.get("observed_copula")
        or params.get("observedCopula")
        or joint.get("observed_copula")
        or joint.get("observedCopula")
        or {"id": "observed", "family": "gaussian"}
    )

    reference_payload = (
        params.get("reference_copula")
        or params.get("referenceCopula")
        or params.get("reference_copulas")
        or params.get("referenceCopulas")
        or joint.get("reference_copulas")
        or joint.get("referenceCopulas")
    )
    reference = _select_reference_copula(reference_payload, params=params)
    if not reference:
        reference = {"id": _DEFAULT_REFERENCE_COPULA_ID, "family": "product"}
    return observed, reference


def _has_declared_distribution(params: Mapping[str, Any], key: str, camel_key: str) -> bool:
    joint = _as_mapping(params.get("joint_distribution") or params.get("jointDistribution"))
    return key in params or camel_key in params or key in joint or camel_key in joint


def _extract_conditional_sampler(params: Mapping[str, Any]) -> dict[str, Any]:
    joint = _as_mapping(params.get("joint_distribution") or params.get("jointDistribution"))
    sampler = _as_mapping(
        params.get("conditional_sampler")
        or params.get("conditionalSampler")
        or joint.get("conditional_sampler")
        or joint.get("conditionalSampler")
    )
    return sampler


def _validate_distribution_contract(params: Mapping[str, Any]) -> dict[str, Any]:
    require_declared = bool(params.get("require_declared_joint_distribution", True))
    sampler = _extract_conditional_sampler(params)
    if require_declared:
        missing = []
        if not _has_declared_distribution(params, "observed_copula", "observedCopula"):
            missing.append("observed_copula")
        if not _has_declared_distribution(params, "reference_copulas", "referenceCopulas") and (
            "reference_copula" not in params and "referenceCopula" not in params
        ):
            missing.append("reference_copula")
        if not sampler:
            missing.append("conditional_sampler")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"dependent sensitivity requires declared {joined}")
    return sampler or {"type": "analytic_gaussian", "exact": True, "supportsCoalitions": True}


def _structural_claim_level(params: Mapping[str, Any]) -> str:
    joint = _as_mapping(params.get("joint_distribution") or params.get("jointDistribution"))
    graph = _as_mapping(joint.get("structural_graph") or joint.get("structuralGraph"))
    level = str(
        params.get("structural_claim_level")
        or params.get("structuralClaimLevel")
        or graph.get("claim_level")
        or graph.get("claimLevel")
        or "distributional"
    )
    if level not in _VALID_STRUCTURAL_LEVELS:
        raise ValueError("structural_claim_level must be distributional, ordered_generating, or causal")
    return level


def _coerce_names(state: Mapping[str, Any], params: Mapping[str, Any], n_features: int) -> list[str]:
    raw = (
        params.get("input_names")
        or params.get("param_names")
        or params.get("feature_names")
        or state.get("input_names")
        or state.get("param_names")
        or state.get("feature_names")
    )
    if raw is None:
        return [f"x{i + 1}" for i in range(n_features)]
    names = [str(item) for item in raw]
    if len(names) != n_features:
        raise ValueError("input_names length must match the number of input columns")
    if len(names) != len(set(names)):
        raise ValueError("input_names must be unique")
    return names


def _coerce_matrix(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a 2D matrix")
    if arr.shape[0] < 2 or arr.shape[1] < 1:
        raise ValueError(f"{name} must have at least two rows and one column")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _coerce_vector(value: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D vector")
    if arr.shape[0] < 2:
        raise ValueError(f"{name} must contain at least two values")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _state_matrix(state: Mapping[str, Any]) -> np.ndarray | None:
    for key in ("input_samples", "inputs_matrix", "X"):
        if key in state:
            return _coerce_matrix(state[key], name=key)
    return None


def _state_outputs(state: Mapping[str, Any]) -> np.ndarray | None:
    for key in ("outputs", "model_outputs", "Y"):
        if key in state:
            return _coerce_vector(state[key], name=key)
    return None


def _matrix_from_payload(value: Any, *, name: str) -> np.ndarray | None:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(f"{name} must be a square matrix")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _covariance_from_samples(samples: np.ndarray) -> np.ndarray:
    cov = np.cov(samples, rowvar=False, ddof=1)
    cov = np.atleast_2d(np.asarray(cov, dtype=float))
    if cov.shape[0] != samples.shape[1] or cov.shape[1] != samples.shape[1]:
        raise ValueError("sample covariance shape does not match input_samples")
    return 0.5 * (cov + cov.T)


def _covariance_from_copula(
    copula: Mapping[str, Any],
    *,
    variances: np.ndarray,
    fallback: np.ndarray,
) -> np.ndarray:
    family = _copula_family(copula)
    if family == "product":
        return np.diag(variances)

    parameters = _as_mapping(_get(copula, "parameters", default={}))
    corr_payload = _get(
        parameters,
        "correlation_matrix",
        "correlationMatrix",
        "rank_correlation_matrix",
        "rankCorrelationMatrix",
    )
    corr = _matrix_from_payload(corr_payload, name="correlation_matrix")
    if corr is None:
        return fallback
    if corr.shape != fallback.shape:
        raise ValueError("declared copula correlation matrix shape does not match inputs")
    std = np.sqrt(np.maximum(variances, 0.0))
    return corr * np.outer(std, std)


def _covariance_to_correlation(covariance: np.ndarray) -> list[list[float]]:
    diag = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    denom = np.outer(diag, diag)
    corr = np.divide(
        covariance,
        denom,
        out=np.zeros_like(covariance, dtype=float),
        where=denom > 0.0,
    )
    np.fill_diagonal(corr, 1.0)
    return corr.tolist()


def _linear_coefficients(
    *,
    samples: np.ndarray | None,
    outputs: np.ndarray | None,
    state: Mapping[str, Any],
    n_features: int,
) -> np.ndarray:
    if "linear_coefficients" in state:
        beta = np.asarray(state["linear_coefficients"], dtype=float)
        if beta.shape != (n_features,):
            raise ValueError("linear_coefficients length must match the number of inputs")
        if not np.all(np.isfinite(beta)):
            raise ValueError("linear_coefficients must be finite")
        return beta
    if samples is None or outputs is None:
        raise ValueError("input_samples and outputs are required unless linear_coefficients is set")
    if samples.shape[0] != outputs.shape[0]:
        raise ValueError("input_samples and outputs must have the same row count")
    x_centered = samples - np.mean(samples, axis=0)
    y_centered = outputs - np.mean(outputs)
    beta, _, _, _ = np.linalg.lstsq(x_centered, y_centered, rcond=None)
    return np.asarray(beta, dtype=float)


def _variance_for_model(
    *,
    beta: np.ndarray,
    covariance: np.ndarray,
    outputs: np.ndarray | None,
    state_key: str,
    state: Mapping[str, Any],
) -> float:
    if state_key in state:
        variance = float(state[state_key])
    elif outputs is not None:
        variance = float(np.var(outputs, ddof=1))
    else:
        variance = float(beta @ covariance @ beta)
    if not np.isfinite(variance) or variance <= 0.0:
        raise ValueError(f"{state_key} must be positive and finite")
    return variance


def _regularized_pinv(matrix: np.ndarray, *, ridge: float) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    regularized = matrix if ridge <= 0.0 else matrix + np.eye(matrix.shape[0]) * ridge
    return np.linalg.pinv(regularized, hermitian=True)


def _coalition_value_from_linear_projection(
    *,
    mask: int,
    beta: np.ndarray,
    covariance: np.ndarray,
    variance: float,
    ridge: float,
    allocate_total_variance: bool,
) -> float:
    if mask == 0:
        return 0.0
    n_features = beta.shape[0]
    full_mask = (1 << n_features) - 1
    if allocate_total_variance and mask == full_mask:
        return float(variance)
    indices = [idx for idx in range(n_features) if mask & (1 << idx)]
    sigma_aa = covariance[np.ix_(indices, indices)]
    cov_y_a = beta @ covariance[:, indices]
    value = float(cov_y_a @ _regularized_pinv(sigma_aa, ridge=ridge) @ cov_y_a.T)
    return max(value, 0.0)


def _build_linear_coalition_values(
    *,
    masks: set[int],
    beta: np.ndarray,
    covariance: np.ndarray,
    variance: float,
    ridge: float,
    allocate_total_variance: bool,
) -> dict[int, float]:
    return {
        mask: _coalition_value_from_linear_projection(
            mask=mask,
            beta=beta,
            covariance=covariance,
            variance=variance,
            ridge=ridge,
            allocate_total_variance=allocate_total_variance,
        )
        for mask in sorted(masks)
    }


def _parse_mask(key: Any, *, n_features: int, input_names: Sequence[str]) -> int:
    full_mask = (1 << n_features) - 1
    if isinstance(key, int):
        mask = key
    else:
        text = str(key).strip()
        if text in {"", "empty", "[]", "{}"}:
            return 0
        if text in {"full", "all"}:
            return full_mask
        if text.isdigit():
            mask = int(text)
        else:
            names = {name.strip() for name in text.replace("|", ",").split(",") if name.strip()}
            unknown = names - set(input_names)
            if unknown:
                raise ValueError(f"unknown coalition names: {sorted(unknown)}")
            mask = 0
            for idx, name in enumerate(input_names):
                if name in names:
                    mask |= 1 << idx
    if mask < 0 or mask > full_mask:
        raise ValueError(f"coalition mask {mask!r} is outside the input range")
    return mask


def _coalition_values_from_payload(
    payload: Any,
    *,
    n_features: int,
    input_names: Sequence[str],
) -> dict[int, float] | None:
    if payload is None:
        return None
    mapping = _as_mapping(payload)
    values: dict[int, float] = {}
    for key, value in mapping.items():
        mask = _parse_mask(key, n_features=n_features, input_names=input_names)
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("coalition values must be finite")
        values[mask] = number
    return values


def _paired_covariance(y_a: np.ndarray, y_b: np.ndarray) -> float:
    if y_a.shape != y_b.shape or y_a.ndim != 1:
        raise ValueError("conditional paired outputs must be aligned 1D arrays")
    if y_a.size < 2:
        raise ValueError("conditional paired outputs need at least two pairs")
    if not np.all(np.isfinite(y_a)) or not np.all(np.isfinite(y_b)):
        raise ValueError("conditional paired outputs must be finite")
    return float(np.cov(y_a, y_b, ddof=1)[0, 1])


def _coalition_values_from_conditional_pairs(
    payload: Any,
    *,
    n_features: int,
    input_names: Sequence[str],
) -> dict[int, float] | None:
    if payload is None:
        return None
    values: dict[int, float] = {}
    full_mask = (1 << n_features) - 1
    for key, raw_pairs in _as_mapping(payload).items():
        mask = _parse_mask(key, n_features=n_features, input_names=input_names)
        if mask == 0:
            values[mask] = 0.0
            continue
        if isinstance(raw_pairs, (Mapping, BaseModel)):
            pairs = _as_mapping(raw_pairs)
            y_a = np.asarray(_get(pairs, "a", "y_a", "yA", "outputs_a", "outputsA"), dtype=float)
            y_b = np.asarray(_get(pairs, "b", "y_b", "yB", "outputs_b", "outputsB"), dtype=float)
        else:
            arr = np.asarray(raw_pairs, dtype=float)
            if arr.ndim != 2 or arr.shape[0] != 2:
                raise ValueError("conditional pair payload must be {a,b} or a 2 x n array")
            y_a, y_b = arr[0], arr[1]
        values[mask] = float(np.var(y_a, ddof=1)) if mask == full_mask and np.array_equal(y_a, y_b) else _paired_covariance(y_a, y_b)
    return values


def _required_support_policy(
    *,
    reference_copula: Mapping[str, Any],
    params: Mapping[str, Any],
    state: Mapping[str, Any],
) -> tuple[int, list[str]]:
    warnings: list[str] = []
    support_policy = _as_mapping(
        reference_copula.get("support_policy") or reference_copula.get("supportPolicy")
    )
    violations = int(
        state.get("support_violations")
        or state.get("supportViolations")
        or params.get("support_violations")
        or params.get("supportViolations")
        or 0
    )
    if _copula_family(reference_copula, default="product") == "product":
        allow = bool(
            _get(
                support_policy,
                "allow_product_reference_outside_observed_support",
                "allowProductReferenceOutsideObservedSupport",
                default=False,
            )
        )
        policy = str(
            _get(
                support_policy,
                "invalid_point_policy",
                "invalidPointPolicy",
                default="error",
            )
        )
        if violations > 0 and not allow and policy == "error":
            raise ValueError(
                "product reference generated support violations and support policy is error"
            )
        if violations > 0:
            warnings.append("support_violations_present_for_reference_copula")
    return violations, warnings


def _latent_innovation_payload(
    *,
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    n_features: int,
) -> list[dict[str, dict[str, float]]]:
    payload = [{} for _ in range(n_features)]
    gradients_raw = (
        state.get("latent_gradients")
        or state.get("latentGradientSamples")
        or params.get("latent_gradients")
        or params.get("latentGradientSamples")
    )
    dgsm_raw = state.get("latent_dgsm") or state.get("latentDgsm") or params.get("latent_dgsm")
    if gradients_raw is not None:
        gradients = np.asarray(gradients_raw, dtype=float)
        if gradients.ndim != 2 or gradients.shape[1] != n_features:
            raise ValueError("latent_gradients must have shape n_samples x n_inputs")
        if not np.all(np.isfinite(gradients)):
            raise ValueError("latent_gradients must be finite")
        dgsm = np.mean(gradients**2, axis=0)
    elif dgsm_raw is not None:
        dgsm = np.asarray(dgsm_raw, dtype=float)
        if dgsm.shape != (n_features,):
            raise ValueError("latent_dgsm must match the number of inputs")
    else:
        dgsm = None
    if dgsm is not None:
        for idx, value in enumerate(dgsm):
            payload[idx]["dgsm"] = {"value": float(value)}

    effects_raw = (
        state.get("latent_elementary_effects")
        or state.get("latentElementaryEffects")
        or params.get("latent_elementary_effects")
        or params.get("latentElementaryEffects")
    )
    if effects_raw is not None:
        effects = np.asarray(effects_raw, dtype=float)
        if effects.ndim != 2 or effects.shape[1] != n_features:
            raise ValueError("latent_elementary_effects must have shape n_trajectories x n_inputs")
        if not np.all(np.isfinite(effects)):
            raise ValueError("latent_elementary_effects must be finite")
        mu_star = np.mean(np.abs(effects), axis=0)
        sigma = np.std(effects, axis=0, ddof=1) if effects.shape[0] > 1 else np.zeros(n_features)
        for idx in range(n_features):
            payload[idx]["morrisMuStar"] = {"value": float(mu_star[idx])}
            payload[idx]["morrisSigma"] = {"value": float(sigma[idx])}
    return payload


def _exact_masks(n_features: int) -> set[int]:
    return set(range(1 << n_features))


def _random_permutation_masks(
    *,
    n_features: int,
    permutations: int,
    seed: int,
) -> tuple[list[tuple[int, ...]], set[int]]:
    rng = np.random.default_rng(seed)
    orderings: list[tuple[int, ...]] = []
    masks = {0}
    for _ in range(permutations):
        ordering = tuple(int(item) for item in rng.permutation(n_features))
        orderings.append(ordering)
        mask = 0
        masks.add(mask)
        for idx in ordering:
            mask |= 1 << idx
            masks.add(mask)
    return orderings, masks


def _shapley_exact(values: Mapping[int, float], *, n_features: int) -> np.ndarray:
    phi = np.zeros(n_features, dtype=float)
    factorial = np.array([math.factorial(k) for k in range(n_features + 1)], dtype=float)
    denom = float(math.factorial(n_features))
    for idx in range(n_features):
        bit = 1 << idx
        for mask in range(1 << n_features):
            if mask & bit:
                continue
            size = int(mask.bit_count())
            weight = factorial[size] * factorial[n_features - size - 1] / denom
            phi[idx] += weight * (float(values[mask | bit]) - float(values[mask]))
    return phi


def _shapley_random(
    values: Mapping[int, float],
    *,
    orderings: Sequence[Sequence[int]],
    n_features: int,
) -> np.ndarray:
    if not orderings:
        raise ValueError("at least one random permutation is required")
    phi = np.zeros(n_features, dtype=float)
    for ordering in orderings:
        mask = 0
        previous_value = float(values[mask])
        for idx in ordering:
            next_mask = mask | (1 << idx)
            next_value = float(values[next_mask])
            phi[idx] += next_value - previous_value
            mask = next_mask
            previous_value = next_value
    return phi / float(len(orderings))


def _edge_contributions_from_payload(
    *,
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    full_variance: float,
    sign_tolerance: float,
) -> list[dict[str, Any]]:
    edge_names_raw = (
        state.get("edge_names")
        or state.get("edgeNames")
        or params.get("edge_names")
        or params.get("edgeNames")
    )
    values_raw = (
        state.get("edge_variance_values")
        or state.get("edgeVarianceValues")
        or params.get("edge_variance_values")
        or params.get("edgeVarianceValues")
    )
    if edge_names_raw is None or values_raw is None:
        return []
    edge_names = [str(edge) for edge in edge_names_raw]
    if len(edge_names) != len(set(edge_names)):
        raise ValueError("edge_names must be unique")
    n_edges = len(edge_names)
    values = _coalition_values_from_payload(
        values_raw,
        n_features=n_edges,
        input_names=edge_names,
    )
    if values is None:
        return []
    required = set(range(1 << n_edges))
    missing = required - set(values)
    if missing:
        raise ValueError(f"missing edge variance values for masks: {sorted(missing)[:8]}")
    phi = _shapley_exact(values, n_features=n_edges)
    contributions = []
    for edge, value in zip(edge_names, phi, strict=True):
        sign = _sign(float(value), tolerance=sign_tolerance)
        contributions.append(
            {
                "edge": edge,
                "contribution": _estimate(float(value), denominator=full_variance),
                "normalizedContribution": {"value": float(value / full_variance)},
                "interpretation": {
                    "amplifying": "amplifies_variance",
                    "dampening": "dampens_variance",
                    "near_zero": "near_zero",
                }[sign],
            }
        )
    return contributions


def _estimate(value: float, *, denominator: float) -> dict[str, float]:
    return {"value": float(value), "normalized": float(value / denominator)}


def _sign(value: float, *, tolerance: float) -> str:
    if value > tolerance:
        return "amplifying"
    if value < -tolerance:
        return "dampening"
    return "near_zero"


def _build_indices(
    *,
    input_names: Sequence[str],
    full_values: Mapping[int, float],
    reference_values: Mapping[int, float],
    full_shapley: np.ndarray,
    reference_shapley: np.ndarray,
    full_variance: float,
    reference_variance: float,
    reference_copula_id: str,
    sign_tolerance: float,
    latent_innovation: Sequence[dict[str, dict[str, float]]] | None = None,
) -> list[dict[str, Any]]:
    n_features = len(input_names)
    full_mask = (1 << n_features) - 1
    rows: list[dict[str, Any]] = []
    for idx, name in enumerate(input_names):
        bit = 1 << idx
        without = full_mask ^ bit
        full_first = float(full_values[bit] / full_variance)
        full_total = float((full_variance - full_values[without]) / full_variance)
        reference_first = float(reference_values[bit] / full_variance)
        reference_total = float((reference_variance - reference_values[without]) / full_variance)
        structural_shapley = float(full_shapley[idx] - reference_shapley[idx])
        structural_first = full_first - reference_first
        structural_total = full_total - reference_total
        row = {
            "input": name,
            "full": {
                "shapley": _estimate(float(full_shapley[idx]), denominator=full_variance),
                "first": _estimate(full_first * full_variance, denominator=full_variance),
                "total": _estimate(full_total * full_variance, denominator=full_variance),
            },
            "marginalReference": {
                "referenceCopulaId": reference_copula_id,
                "shapley": _estimate(float(reference_shapley[idx]), denominator=full_variance),
                "first": _estimate(
                    reference_first * full_variance,
                    denominator=full_variance,
                ),
                "total": _estimate(
                    reference_total * full_variance,
                    denominator=full_variance,
                ),
            },
            "structuralDelta": {
                "referenceCopulaId": reference_copula_id,
                "shapley": _estimate(structural_shapley, denominator=full_variance),
                "first": _estimate(structural_first * full_variance, denominator=full_variance),
                "total": _estimate(structural_total * full_variance, denominator=full_variance),
                "sign": _sign(structural_shapley, tolerance=sign_tolerance),
            },
        }
        if latent_innovation is not None and latent_innovation[idx]:
            row["latentInnovation"] = latent_innovation[idx]
        rows.append(row)
    return rows


@foundry_method(
    namespace="sensitivity.global",
    version="1.0.0",
    tags={"sensitivity", "global", "dependent", "copula", "shapley", "sobol", "tabular"},
)
class DependentCopulaSensitivityEstimator:
    """Estimate full, marginal-reference, and structural sensitivity for dependent inputs."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dependent_copula_sensitivity",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "input_samples",
                    SlotType.MATRIX,
                    Unit("parameter", "value"),
                    shape=("n_samples", "n_inputs"),
                ),
                SlotSpec("outputs", SlotType.VECTOR, Unit("response", "value"), shape=("n_samples",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="input_names", default=None),
            ParameterSpec(name="observed_copula", default={"id": "observed", "family": "gaussian"}),
            ParameterSpec(
                name="reference_copula",
                default={"id": _DEFAULT_REFERENCE_COPULA_ID, "family": "product"},
            ),
            ParameterSpec(name="estimator_family", default="dependent_shapley_copula"),
            ParameterSpec(name="structural_claim_level", default="distributional"),
            ParameterSpec(name="exact_enumeration_max_inputs", default=10),
            ParameterSpec(name="permutations", default=2048),
            ParameterSpec(name="regularization", default=0.0),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_EXP,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "DC-SAFE dependent-copula sensitivity estimator with full, "
            "marginal-reference, and structural delta contributions."
        ),
        tags=frozenset({"sensitivity", "global", "dependent", "copula", "shapley", "sobol"}),
        citations=(
            "Song, Nelson & Staum (2016). Shapley effects for global sensitivity analysis.",
            "Owen & Prieur (2017). On Shapley effects for sensitivity analysis.",
            "Kucherenko, Tarantola & Annoni (2012). Estimation of global sensitivity indices for dependent variables.",
        ),
        equations={
            "coalition": "v(A)=Var(E[Y|X_A])",
            "shapley": "phi_i=sum_A |A|!(d-|A|-1)!/d! * (v(A+i)-v(A))",
            "structural": "phi_structural=phi_full-phi_marginal_reference",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Global sensitivity analysis when inputs are correlated or constrained and "
            "the joint distribution/reference copula must be declared."
        ),
        when_not_to_use=(
            "Undeclared or unidentified dependence structure; causal edge attribution without "
            "an external causal graph; high-dimensional exact Shapley without a sampling budget."
        ),
        output_interpretation=(
            "Ranks inputs by full dependent Shapley share and reports how much of each share "
            "comes from marginal uncertainty versus declared dependence structure."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        conditional_sampler = _validate_distribution_contract(params)
        structural_level = _structural_claim_level(params)
        observed_copula, reference_copula = _extract_distribution(params)
        samples = _state_matrix(state)
        outputs = _state_outputs(state)
        support_violations, support_warnings = _required_support_policy(
            reference_copula=reference_copula,
            params=params,
            state=state,
        )

        covariance_payload = (
            state.get("covariance_matrix")
            or params.get("covariance_matrix")
            or params.get("covarianceMatrix")
        )
        fallback_covariance = (
            _matrix_from_payload(covariance_payload, name="covariance_matrix")
            if covariance_payload is not None
            else None
        )
        if fallback_covariance is None:
            if samples is None:
                raise ValueError("input_samples or covariance_matrix must be supplied")
            fallback_covariance = _covariance_from_samples(samples)

        n_features = int(fallback_covariance.shape[0])
        if fallback_covariance.shape != (n_features, n_features):
            raise ValueError("covariance_matrix must be square")
        if samples is not None and samples.shape[1] != n_features:
            raise ValueError("input_samples column count must match covariance_matrix")
        input_names = _coerce_names(state, params, n_features)

        variances_payload = state.get("input_variances") or params.get("input_variances")
        if variances_payload is None:
            variances = np.diag(fallback_covariance).astype(float)
        else:
            variances = np.asarray(variances_payload, dtype=float)
        if variances.shape != (n_features,) or np.any(variances < 0.0):
            raise ValueError("input_variances must be a non-negative vector matching inputs")

        observed_covariance = _covariance_from_copula(
            observed_copula,
            variances=variances,
            fallback=fallback_covariance,
        )
        beta = _linear_coefficients(
            samples=samples,
            outputs=outputs,
            state=state,
            n_features=n_features,
        )

        full_variance = _variance_for_model(
            beta=beta,
            covariance=observed_covariance,
            outputs=outputs,
            state_key="full_variance",
            state=state,
        )

        exact_max = int(params.get("exact_enumeration_max_inputs", 10))
        permutations = int(params.get("permutations", 2048))
        seed = int(params.get("seed", 42))
        use_exact = n_features <= exact_max
        orderings: list[tuple[int, ...]] = []
        if use_exact:
            masks = _exact_masks(n_features)
        else:
            orderings, masks = _random_permutation_masks(
                n_features=n_features,
                permutations=permutations,
                seed=seed,
            )

        full_pairs = _coalition_values_from_conditional_pairs(
            state.get("conditional_pairs_full")
            or state.get("conditionalPairsFull")
            or params.get("conditional_pairs_full")
            or params.get("conditionalPairsFull"),
            n_features=n_features,
            input_names=input_names,
        )
        full_payload = _coalition_values_from_payload(
            state.get("coalition_values_full") or params.get("coalition_values_full"),
            n_features=n_features,
            input_names=input_names,
        )
        if full_payload is None and full_pairs is not None:
            full_values = full_pairs
            estimator_semantics = "conditional_paired_sampling"
        elif full_payload is None:
            full_values = _build_linear_coalition_values(
                masks=masks,
                beta=beta,
                covariance=observed_covariance,
                variance=full_variance,
                ridge=float(params.get("regularization", 0.0)),
                allocate_total_variance=bool(params.get("allocate_total_variance", True)),
            )
            estimator_semantics = "linear_gaussian_surrogate"
        else:
            full_values = full_payload
            estimator_semantics = "declared_conditional_coalition_values"

        reference_copula_id = _copula_id(reference_copula, default=_DEFAULT_REFERENCE_COPULA_ID)
        same_product_reference = (
            _copula_family(observed_copula) == "product" and _copula_family(reference_copula) == "product"
        )
        reference_pairs = _coalition_values_from_conditional_pairs(
            state.get("conditional_pairs_reference")
            or state.get("conditionalPairsReference")
            or state.get("conditional_pairs_ref")
            or state.get("conditionalPairsRef")
            or params.get("conditional_pairs_reference")
            or params.get("conditionalPairsReference"),
            n_features=n_features,
            input_names=input_names,
        )
        reference_payload = _coalition_values_from_payload(
            state.get("coalition_values_reference")
            or state.get("coalition_values_ref")
            or params.get("coalition_values_reference")
            or params.get("coalition_values_ref"),
            n_features=n_features,
            input_names=input_names,
        )
        reference_outputs = (
            _coerce_vector(state["outputs_reference"], name="outputs_reference")
            if "outputs_reference" in state
            else None
        )
        reference_samples = (
            _coerce_matrix(state["input_samples_reference"], name="input_samples_reference")
            if "input_samples_reference" in state
            else None
        )
        if (
            same_product_reference
            and reference_payload is None
            and reference_pairs is None
            and reference_outputs is None
        ):
            reference_covariance = observed_covariance
            reference_variance = full_variance
            reference_values = dict(full_values)
        else:
            reference_fallback = (
                _covariance_from_samples(reference_samples)
                if reference_samples is not None
                else fallback_covariance
            )
            reference_covariance = _covariance_from_copula(
                reference_copula,
                variances=variances,
                fallback=reference_fallback,
            )
            if reference_payload is None and reference_pairs is not None:
                reference_values = reference_pairs
                full_mask = (1 << n_features) - 1
                reference_variance = float(
                    state.get("reference_variance", reference_values.get(full_mask, 0.0))
                )
                if reference_variance <= 0.0:
                    raise ValueError("reference_variance must be positive")
            elif reference_payload is None:
                reference_variance = _variance_for_model(
                    beta=beta,
                    covariance=reference_covariance,
                    outputs=reference_outputs,
                    state_key="reference_variance",
                    state=state,
                )
                reference_values = _build_linear_coalition_values(
                    masks=masks,
                    beta=beta,
                    covariance=reference_covariance,
                    variance=reference_variance,
                    ridge=float(params.get("regularization", 0.0)),
                    allocate_total_variance=True,
                )
            else:
                reference_values = reference_payload
                full_mask = (1 << n_features) - 1
                reference_variance = float(
                    state.get("reference_variance", reference_values.get(full_mask, 0.0))
                )
                if reference_variance <= 0.0:
                    raise ValueError("reference_variance must be positive")

        required_masks = masks
        missing_full = required_masks - set(full_values)
        missing_reference = required_masks - set(reference_values)
        if missing_full:
            raise ValueError(f"missing full coalition values for masks: {sorted(missing_full)[:8]}")
        if missing_reference:
            raise ValueError(
                f"missing reference coalition values for masks: {sorted(missing_reference)[:8]}"
            )

        if use_exact:
            full_shapley = _shapley_exact(full_values, n_features=n_features)
            reference_shapley = _shapley_exact(reference_values, n_features=n_features)
            shapley_mode = "exact_enumeration"
        else:
            full_shapley = _shapley_random(
                full_values,
                orderings=orderings,
                n_features=n_features,
            )
            reference_shapley = _shapley_random(
                reference_values,
                orderings=orderings,
                n_features=n_features,
            )
            shapley_mode = "random_permutations"

        structural_variance_delta = float(full_variance - reference_variance)
        sign_tolerance = float(params.get("sign_tolerance", _DEFAULT_SIGN_TOLERANCE))
        latent_innovation = _latent_innovation_payload(
            state=state,
            params=params,
            n_features=n_features,
        )
        edge_contributions = _edge_contributions_from_payload(
            state=state,
            params=params,
            full_variance=full_variance,
            sign_tolerance=sign_tolerance,
        )
        warnings = []
        if estimator_semantics == "linear_gaussian_surrogate":
            warnings.append("linear_gaussian_surrogate_used_for_unsupplied_conditional_coalitions")
        warnings.extend(support_warnings)
        edge_identified = bool(edge_contributions)
        result = {
            "bundleId": params.get("bundle_id"),
            "outputName": str(params.get("output_name", "output")),
            "contractVersion": "2.0",
            "kind": "dependent_copula_sensitivity",
            "estimatorFamily": str(params.get("estimator_family", "dependent_shapley_copula")),
            "variance": {
                "full": float(full_variance),
                "reference": {reference_copula_id: float(reference_variance)},
                "structuralDelta": {reference_copula_id: structural_variance_delta},
            },
            "indices": _build_indices(
                input_names=input_names,
                full_values=full_values,
                reference_values=reference_values,
                full_shapley=full_shapley,
                reference_shapley=reference_shapley,
                full_variance=full_variance,
                reference_variance=reference_variance,
                reference_copula_id=reference_copula_id,
                sign_tolerance=sign_tolerance,
                latent_innovation=latent_innovation,
            ),
            "edgeContributions": edge_contributions,
            "diagnostics": {
                "estimatorSemantics": estimator_semantics,
                "shapleyMode": shapley_mode,
                "observedCopula": {
                    "id": _copula_id(observed_copula, default="observed"),
                    "family": _copula_family(observed_copula),
                },
                "referenceCopula": {
                    "id": reference_copula_id,
                    "family": _copula_family(reference_copula, default="product"),
                },
                "dependenceMatrix": _covariance_to_correlation(observed_covariance),
                "referenceDependenceMatrix": _covariance_to_correlation(reference_covariance),
                "supportViolations": support_violations,
                "conditionalSamplerChecks": [
                    {
                        "type": str(
                            _get(
                                conditional_sampler,
                                "type",
                                default="analytic_gaussian",
                            )
                        ),
                        "exact": bool(_get(conditional_sampler, "exact", default=True)),
                        "supportsCoalitions": bool(
                            _get(
                                conditional_sampler,
                                "supports_coalitions",
                                "supportsCoalitions",
                                default=True,
                            )
                        ),
                    }
                ],
                "convergence": {
                    "nInputs": n_features,
                    "nCoalitions": len(required_masks),
                    "permutations": None if use_exact else len(orderings),
                },
                "warnings": warnings,
            },
            "identifiability": {
                "marginalIdentified": True,
                "fullDependentIdentified": True,
                "structuralDeltaIdentified": True,
                "edgeStructuralIdentified": edge_identified,
                "structuralClaimLevel": structural_level,
                "warnings": []
                if structural_level == "distributional"
                else ["non_distributional_structural_claim_requires_external_graph_review"],
            },
            "reproducibility": {
                "seed": seed,
                "estimatorVersion": "dc-safe-linear-gaussian-1.0",
                "modelHash": params.get("model_hash"),
                "inputDistributionHash": params.get("input_distribution_hash"),
                "runTimestamp": params.get("run_timestamp"),
            },
        }
        return {"result": result}


__all__ = ["DependentCopulaSensitivityEstimator"]
