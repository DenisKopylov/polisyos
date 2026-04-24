"""Robust MCDA rank-stability and consensus utilities.

This module intentionally keeps the implementation dependency-light for the
Foundry catalog methods. Monte Carlo sampling is the default execution path,
with an optional LP screen for linear utility models when scipy is available.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from itertools import pairwise, permutations
from math import factorial
from typing import Any, cast

import numpy as np

Array = np.ndarray
ScoreEvaluator = Callable[[Array], Array]


STRICT_TOP1_THRESHOLD = 0.70
STRICT_ADJACENT_THRESHOLD = 0.60
STRICT_DISPLACEMENT_THRESHOLD = 0.20
TIER_TOP1_THRESHOLD = 0.55
TIER_ADJACENT_THRESHOLD = 0.50
TIER_DISPLACEMENT_THRESHOLD = 0.35


def _load_linprog() -> Any:
    scipy_optimize = cast("Any", importlib.import_module("scipy.optimize"))
    return scipy_optimize.linprog


@dataclass(frozen=True)
class _Stakeholder:
    id: str
    meta_weight: float
    weight_model: Mapping[str, Any]


def _as_2d_float(name: str, value: Any) -> Array:
    matrix = np.asarray(value, dtype=float)
    if matrix.ndim != 2:
        raise ValueError(f"{name} must be 2D")
    if matrix.shape[0] < 1 or matrix.shape[1] < 1:
        raise ValueError(f"{name} must be non-empty")
    return matrix


def _as_bool_vector(name: str, value: Any, length: int) -> Array:
    vector = np.asarray(value, dtype=bool)
    if vector.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},)")
    return vector


def _coerce_ids(ids: Sequence[Any] | None, n_items: int, prefix: str) -> list[str]:
    if ids is None:
        return [f"{prefix}{idx + 1}" for idx in range(n_items)]
    if len(ids) != n_items:
        raise ValueError(f"{prefix} ids must match item count")
    return [str(item) for item in ids]


def _normalize_weights(weights: Any, n_criteria: int, *, name: str = "weights") -> Array:
    vector = np.asarray(weights, dtype=float)
    if vector.shape != (n_criteria,):
        raise ValueError(f"{name} must have shape ({n_criteria},)")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be finite")
    if np.any(vector < 0):
        raise ValueError(f"{name} must be non-negative")
    total = float(np.sum(vector))
    if total <= 0:
        raise ValueError(f"{name} must have positive sum")
    return vector / total


def _ahp_priority_weights(pairwise_matrix: Any) -> Array:
    matrix = np.asarray(pairwise_matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("pairwise_matrix must be square")
    if matrix.shape[0] < 2:
        raise ValueError("pairwise_matrix must include at least two criteria")
    if not np.all(np.isfinite(matrix)) or np.any(matrix <= 0):
        raise ValueError("pairwise_matrix must contain positive finite values")
    n = matrix.shape[0]
    geo_means = np.prod(matrix, axis=1) ** (1.0 / n)
    return _normalize_weights(geo_means, n, name="pairwise priority weights")


def _softmax_rows(values: Array) -> Array:
    shifted = values - np.max(values, axis=1, keepdims=True)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values, axis=1, keepdims=True)


def _coerce_weight_model(stakeholder: Mapping[str, Any], n_criteria: int) -> Mapping[str, Any]:
    if "weight_model" in stakeholder:
        weight_model = dict(stakeholder["weight_model"])
    elif "pairwise_matrix" in stakeholder:
        weight_model = {
            "type": "point",
            "weights": _ahp_priority_weights(stakeholder["pairwise_matrix"]).tolist(),
        }
    elif "weights" in stakeholder:
        weight_model = {"type": "point", "weights": stakeholder["weights"]}
    else:
        raise ValueError("each stakeholder needs weight_model, pairwise_matrix, or weights")

    model_type = str(weight_model.get("type", "point")).lower()
    if model_type in {"point", "fixed"}:
        weight_model["weights"] = _normalize_weights(
            weight_model.get("weights", weight_model.get("value")),
            n_criteria,
            name="point weights",
        ).tolist()
    elif model_type == "dirichlet":
        alpha = np.asarray(weight_model.get("alpha"), dtype=float)
        if alpha.shape != (n_criteria,) or np.any(alpha <= 0) or not np.all(np.isfinite(alpha)):
            raise ValueError("dirichlet alpha must be positive and match criteria count")
        weight_model["alpha"] = alpha.tolist()
    elif model_type == "logistic_normal":
        mean = np.asarray(weight_model.get("mean", np.zeros(n_criteria)), dtype=float)
        covariance = np.asarray(weight_model.get("covariance", np.eye(n_criteria)), dtype=float)
        if mean.shape != (n_criteria,):
            raise ValueError("logistic_normal mean must match criteria count")
        if covariance.shape != (n_criteria, n_criteria):
            raise ValueError("logistic_normal covariance must be square criteria x criteria")
        weight_model["mean"] = mean.tolist()
        weight_model["covariance"] = covariance.tolist()
    elif model_type in {"polytope", "interval"}:
        _polytope_constraints_from_model(weight_model, n_criteria)
    elif model_type == "ellipsoid":
        mu = _normalize_weights(
            weight_model.get("mu", weight_model.get("mean")), n_criteria, name="ellipsoid mu"
        )
        covariance = np.asarray(
            weight_model.get("covariance", weight_model.get("Sigma")), dtype=float
        )
        if covariance.shape != (n_criteria, n_criteria):
            raise ValueError("ellipsoid covariance must be square criteria x criteria")
        rho = float(weight_model.get("rho", 1.0))
        if rho <= 0:
            raise ValueError("ellipsoid rho must be positive")
        weight_model["mu"] = mu.tolist()
        weight_model["covariance"] = covariance.tolist()
        weight_model["rho"] = rho
    else:
        raise ValueError(f"unsupported weight model type: {model_type}")
    weight_model["type"] = model_type
    return weight_model


def _prepare_stakeholders(
    stakeholders: Sequence[Mapping[str, Any]], n_criteria: int
) -> list[_Stakeholder]:
    if not stakeholders:
        raise ValueError("stakeholders must be non-empty")
    prepared: list[_Stakeholder] = []
    for idx, stakeholder in enumerate(stakeholders):
        stakeholder_id = str(stakeholder.get("id", f"s{idx + 1}"))
        meta_weight = float(stakeholder.get("meta_weight", 1.0))
        if not np.isfinite(meta_weight) or meta_weight < 0:
            raise ValueError("stakeholder meta_weight must be finite and non-negative")
        prepared.append(
            _Stakeholder(
                id=stakeholder_id,
                meta_weight=meta_weight,
                weight_model=_coerce_weight_model(stakeholder, n_criteria),
            )
        )

    total = sum(stakeholder.meta_weight for stakeholder in prepared)
    if total <= 0:
        equal_weight = 1.0 / len(prepared)
        return [
            _Stakeholder(stakeholder.id, equal_weight, stakeholder.weight_model)
            for stakeholder in prepared
        ]
    return [
        _Stakeholder(stakeholder.id, stakeholder.meta_weight / total, stakeholder.weight_model)
        for stakeholder in prepared
    ]


def _polytope_constraints_from_model(
    weight_model: Mapping[str, Any],
    n_criteria: int,
) -> tuple[Array, Array, Array, Array, list[tuple[float, float]]]:
    lower = np.asarray(weight_model.get("lower_bounds", np.zeros(n_criteria)), dtype=float)
    upper = np.asarray(weight_model.get("upper_bounds", np.ones(n_criteria)), dtype=float)
    if lower.shape != (n_criteria,) or upper.shape != (n_criteria,):
        raise ValueError("polytope bounds must match criteria count")
    if np.any(lower < 0) or np.any(upper < lower):
        raise ValueError("polytope bounds must satisfy 0 <= lower <= upper")

    a_ub = np.asarray(weight_model.get("A", []), dtype=float)
    b_ub = np.asarray(weight_model.get("b", []), dtype=float)
    if a_ub.size == 0:
        a_ub = np.zeros((0, n_criteria), dtype=float)
        b_ub = np.zeros((0,), dtype=float)
    elif a_ub.ndim != 2 or a_ub.shape[1] != n_criteria or b_ub.shape != (a_ub.shape[0],):
        raise ValueError("polytope A and b must have compatible shapes")

    e_eq = np.asarray(weight_model.get("E", []), dtype=float)
    f_eq = np.asarray(weight_model.get("f", []), dtype=float)
    if e_eq.size == 0:
        e_eq = np.zeros((0, n_criteria), dtype=float)
        f_eq = np.zeros((0,), dtype=float)
    elif e_eq.ndim != 2 or e_eq.shape[1] != n_criteria or f_eq.shape != (e_eq.shape[0],):
        raise ValueError("polytope E and f must have compatible shapes")

    simplex_eq = np.ones((1, n_criteria), dtype=float)
    simplex_rhs = np.ones((1,), dtype=float)
    a_eq = np.vstack([simplex_eq, e_eq])
    b_eq = np.concatenate([simplex_rhs, f_eq])
    bounds = [(float(lo), float(hi)) for lo, hi in zip(lower, upper, strict=True)]
    return a_ub, b_ub, a_eq, b_eq, bounds


def _model_center_weights(weight_model: Mapping[str, Any], n_criteria: int) -> Array:
    model_type = str(weight_model.get("type", "point")).lower()
    if model_type in {"point", "fixed"}:
        return _normalize_weights(weight_model["weights"], n_criteria, name="point weights")
    if model_type == "dirichlet":
        alpha = np.asarray(weight_model["alpha"], dtype=float)
        return alpha / np.sum(alpha)
    if model_type == "logistic_normal":
        return _softmax_rows(np.asarray([weight_model["mean"]], dtype=float))[0]
    if model_type == "ellipsoid":
        return _normalize_weights(weight_model["mu"], n_criteria, name="ellipsoid mu")
    if model_type in {"polytope", "interval"}:
        lower = np.asarray(weight_model.get("lower_bounds", np.zeros(n_criteria)), dtype=float)
        upper = np.asarray(weight_model.get("upper_bounds", np.ones(n_criteria)), dtype=float)
        candidate = (lower + upper) / 2.0
        if np.sum(candidate) > 0:
            candidate = candidate / np.sum(candidate)
            if np.all(candidate >= lower - 1e-9) and np.all(candidate <= upper + 1e-9):
                return candidate
        with suppress(Exception):
            linprog = _load_linprog()

            a_ub, b_ub, a_eq, b_eq, bounds = _polytope_constraints_from_model(
                weight_model, n_criteria
            )
            result = linprog(
                c=np.zeros(n_criteria),
                A_ub=a_ub if len(a_ub) else None,
                b_ub=b_ub if len(b_ub) else None,
                A_eq=a_eq,
                b_eq=b_eq,
                bounds=bounds,
                method="highs",
            )
            if result.success:
                return _normalize_weights(result.x, n_criteria, name="polytope center")
    return np.full(n_criteria, 1.0 / n_criteria, dtype=float)


def _reference_weights(
    stakeholders: Sequence[_Stakeholder],
    n_criteria: int,
    reference_weights: Sequence[float] | None,
) -> Array:
    if reference_weights is not None:
        return _normalize_weights(reference_weights, n_criteria, name="reference_weights")
    weighted = np.zeros(n_criteria, dtype=float)
    for stakeholder in stakeholders:
        weighted += stakeholder.meta_weight * _model_center_weights(
            stakeholder.weight_model, n_criteria
        )
    return _normalize_weights(weighted, n_criteria, name="stakeholder center weights")


def _constraints_satisfied(
    weights: Array,
    a_ub: Array,
    b_ub: Array,
    a_eq: Array,
    b_eq: Array,
    bounds: list[tuple[float, float]],
    *,
    eq_tolerance: float = 1e-7,
) -> Array:
    mask = np.ones(weights.shape[0], dtype=bool)
    for idx, (lower, upper) in enumerate(bounds):
        mask &= weights[:, idx] >= lower - 1e-10
        mask &= weights[:, idx] <= upper + 1e-10
    if len(a_ub):
        mask &= np.all(weights @ a_ub.T <= b_ub + 1e-10, axis=1)
    if len(a_eq):
        mask &= np.all(np.abs(weights @ a_eq.T - b_eq) <= eq_tolerance, axis=1)
    return mask


def _nullspace(matrix: Array, *, tolerance: float = 1e-10) -> Array:
    _, singular_values, vh = np.linalg.svd(matrix, full_matrices=True)
    rank = int(np.sum(singular_values > tolerance))
    return vh[rank:].T


def _hit_and_run_polytope(
    weight_model: Mapping[str, Any],
    n_samples: int,
    n_criteria: int,
    rng: np.random.Generator,
) -> Array:
    try:
        linprog = _load_linprog()
    except Exception as exc:  # pragma: no cover - exercised only without scipy
        raise ValueError("polytope sampling with general constraints requires scipy") from exc

    a_ub, b_ub, a_eq, b_eq, bounds = _polytope_constraints_from_model(weight_model, n_criteria)
    feasible = linprog(
        c=np.zeros(n_criteria),
        A_ub=a_ub if len(a_ub) else None,
        b_ub=b_ub if len(b_ub) else None,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not feasible.success:
        raise ValueError("polytope weight model is infeasible")

    point = np.asarray(feasible.x, dtype=float)
    basis = _nullspace(a_eq)
    if basis.shape[1] == 0:
        return np.repeat(point[None, :], n_samples, axis=0)

    burn_in = int(weight_model.get("burn_in", max(50, 10 * n_criteria)))
    thinning = int(weight_model.get("thinning", 2))
    draws: list[Array] = []
    total_steps = burn_in + max(n_samples * thinning, 1)

    for step in range(total_steps):
        direction = basis @ rng.normal(size=basis.shape[1])
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-12:
            continue
        direction = direction / norm
        lower_t = -np.inf
        upper_t = np.inf

        for idx, (lower, upper) in enumerate(bounds):
            delta = float(direction[idx])
            if abs(delta) <= 1e-12:
                continue
            lo = (lower - point[idx]) / delta
            hi = (upper - point[idx]) / delta
            lower_t = max(lower_t, min(lo, hi))
            upper_t = min(upper_t, max(lo, hi))

        for row, rhs in zip(a_ub, b_ub, strict=True):
            delta = float(np.dot(row, direction))
            slack = float(rhs - np.dot(row, point))
            if abs(delta) <= 1e-12:
                if slack < -1e-10:
                    raise ValueError("polytope sampler left feasible region")
                continue
            limit = slack / delta
            if delta > 0:
                upper_t = min(upper_t, limit)
            else:
                lower_t = max(lower_t, limit)

        if not np.isfinite(lower_t) or not np.isfinite(upper_t) or lower_t > upper_t:
            continue
        point = point + rng.uniform(lower_t, upper_t) * direction
        point = np.where(np.abs(point) < 1e-14, 0.0, point)

        if step >= burn_in and (step - burn_in) % thinning == 0:
            draws.append(point.copy())
            if len(draws) == n_samples:
                break

    if len(draws) < n_samples:
        raise ValueError("polytope sampler could not produce enough feasible samples")
    return np.vstack(draws)


def _sample_rejection_polytope(
    weight_model: Mapping[str, Any],
    n_samples: int,
    n_criteria: int,
    rng: np.random.Generator,
) -> Array:
    a_ub, b_ub, a_eq, b_eq, bounds = _polytope_constraints_from_model(weight_model, n_criteria)
    if a_eq.shape[0] > 1:
        return _hit_and_run_polytope(weight_model, n_samples, n_criteria, rng)

    accepted: list[Array] = []
    needed = n_samples
    attempts = 0
    max_attempts = int(weight_model.get("max_rejection_rounds", 200))
    while needed > 0 and attempts < max_attempts:
        attempts += 1
        chunk_size = max(needed * 8, 512)
        candidates = rng.dirichlet(np.ones(n_criteria), size=chunk_size)
        mask = _constraints_satisfied(candidates, a_ub, b_ub, a_eq, b_eq, bounds)
        if np.any(mask):
            chunk = candidates[mask][:needed]
            accepted.append(chunk)
            needed -= chunk.shape[0]

    if needed > 0:
        return _hit_and_run_polytope(weight_model, n_samples, n_criteria, rng)
    return np.vstack(accepted)


def _sample_ellipsoid(
    weight_model: Mapping[str, Any],
    n_samples: int,
    n_criteria: int,
    rng: np.random.Generator,
) -> Array:
    mu = _normalize_weights(weight_model["mu"], n_criteria, name="ellipsoid mu")
    covariance = np.asarray(weight_model["covariance"], dtype=float)
    inv_covariance = np.linalg.pinv(covariance)
    rho = float(weight_model.get("rho", 1.0))
    accepted: list[Array] = []
    needed = n_samples
    rounds = 0
    while needed > 0 and rounds < 300:
        rounds += 1
        candidates = rng.dirichlet(
            np.maximum(mu * n_criteria * 2.0, 1e-3), size=max(needed * 8, 512)
        )
        diff = candidates - mu
        distances = np.einsum("ij,jk,ik->i", diff, inv_covariance, diff)
        mask = distances <= rho * rho + 1e-12
        if np.any(mask):
            chunk = candidates[mask][:needed]
            accepted.append(chunk)
            needed -= chunk.shape[0]
    if needed > 0:
        raise ValueError("ellipsoid sampler could not produce enough feasible samples")
    return np.vstack(accepted)


def _sample_weight_model(
    weight_model: Mapping[str, Any],
    n_samples: int,
    n_criteria: int,
    rng: np.random.Generator,
) -> Array:
    model_type = str(weight_model.get("type", "point")).lower()
    if model_type in {"point", "fixed"}:
        weights = _normalize_weights(weight_model["weights"], n_criteria, name="point weights")
        return np.repeat(weights[None, :], n_samples, axis=0)
    if model_type == "dirichlet":
        return rng.dirichlet(np.asarray(weight_model["alpha"], dtype=float), size=n_samples)
    if model_type == "logistic_normal":
        values = rng.multivariate_normal(
            mean=np.asarray(weight_model["mean"], dtype=float),
            cov=np.asarray(weight_model["covariance"], dtype=float),
            size=n_samples,
        )
        return _softmax_rows(values)
    if model_type in {"polytope", "interval"}:
        return _sample_rejection_polytope(weight_model, n_samples, n_criteria, rng)
    if model_type == "ellipsoid":
        return _sample_ellipsoid(weight_model, n_samples, n_criteria, rng)
    raise ValueError(f"unsupported weight model type: {model_type}")


def _allocate_samples(stakeholders: Sequence[_Stakeholder], n_samples: int) -> list[int]:
    if n_samples < 1:
        raise ValueError("n_samples must be positive")
    raw = (
        np.asarray([stakeholder.meta_weight for stakeholder in stakeholders], dtype=float)
        * n_samples
    )
    counts = np.floor(raw).astype(int)
    remainder = n_samples - int(np.sum(counts))
    if remainder > 0:
        order = np.argsort(-(raw - counts))
        for idx in order[:remainder]:
            counts[idx] += 1
    for idx, stakeholder in enumerate(stakeholders):
        if stakeholder.meta_weight > 0 and counts[idx] == 0:
            donor = int(np.argmax(counts))
            if counts[donor] > 1:
                counts[donor] -= 1
                counts[idx] += 1
    return [int(value) for value in counts]


def _sample_stakeholder_weights(
    stakeholders: Sequence[_Stakeholder],
    n_samples: int,
    n_criteria: int,
    rng: np.random.Generator,
) -> tuple[Array, Array, dict[str, int]]:
    allocations = _allocate_samples(stakeholders, n_samples)
    weight_batches: list[Array] = []
    stakeholder_indices: list[Array] = []
    counts: dict[str, int] = {}
    for idx, (stakeholder, count) in enumerate(zip(stakeholders, allocations, strict=True)):
        counts[stakeholder.id] = count
        if count == 0:
            continue
        weight_batches.append(
            _sample_weight_model(stakeholder.weight_model, count, n_criteria, rng)
        )
        stakeholder_indices.append(np.full(count, idx, dtype=int))
    if not weight_batches:
        raise ValueError("no stakeholder samples allocated")
    return np.vstack(weight_batches), np.concatenate(stakeholder_indices), counts


def _renormalized_linear_scores(utility_matrix: Array, weights: Array) -> Array:
    finite = np.isfinite(utility_matrix)
    filled = np.where(finite, utility_matrix, 0.0)
    numerator = filled @ weights.T
    denominator = finite.astype(float) @ weights.T
    scores = np.zeros_like(numerator, dtype=float)
    np.divide(numerator, denominator, out=scores, where=denominator > 1e-12)
    return np.clip(scores, 0.0, 1.0)


def _rank_positions_from_scores(scores: Array) -> tuple[Array, Array]:
    ranking = np.argsort(-scores, kind="mergesort")
    positions = np.empty_like(ranking)
    positions[ranking] = np.arange(len(ranking))
    return ranking, positions


def _kemeny_objective(order: Sequence[int], pairwise_probabilities: Array) -> float:
    objective = 0.0
    for left_pos, left in enumerate(order):
        for right in order[left_pos + 1 :]:
            objective += float(pairwise_probabilities[right, left])
    return objective


def _kemeny_consensus(pairwise_probabilities: Array, *, exact_limit: int = 8) -> list[int]:
    n_items = pairwise_probabilities.shape[0]
    if n_items <= exact_limit and factorial(n_items) <= 100_000:
        best_order: tuple[int, ...] | None = None
        best_value = float("inf")
        for order in permutations(range(n_items)):
            value = _kemeny_objective(order, pairwise_probabilities)
            if value < best_value - 1e-12:
                best_value = value
                best_order = order
        return list(best_order or range(n_items))

    copeland = np.sum(pairwise_probabilities, axis=1) - np.sum(pairwise_probabilities, axis=0)
    order = list(np.argsort(-copeland, kind="mergesort"))
    improved = True
    while improved:
        improved = False
        for idx in range(n_items - 1):
            current = _kemeny_objective(order, pairwise_probabilities)
            candidate = order.copy()
            candidate[idx], candidate[idx + 1] = candidate[idx + 1], candidate[idx]
            if _kemeny_objective(candidate, pairwise_probabilities) < current - 1e-12:
                order = candidate
                improved = True
    return order


def _ranking_to_ids(order: Sequence[int], alternative_ids: Sequence[str]) -> list[str]:
    return [alternative_ids[idx] for idx in order]


def _pair_key(left: int, right: int, alternative_ids: Sequence[str]) -> str:
    return f"{alternative_ids[left]}>{alternative_ids[right]}"


def _build_tiers(
    order: Sequence[int], pairwise_probabilities: Array, alternative_ids: Sequence[str]
) -> list[list[str]]:
    if not order:
        return []
    tiers: list[list[str]] = [[alternative_ids[order[0]]]]
    for previous, current in pairwise(order):
        if pairwise_probabilities[previous, current] >= STRICT_ADJACENT_THRESHOLD:
            tiers.append([alternative_ids[current]])
        else:
            tiers[-1].append(alternative_ids[current])
    return tiers


def _status_and_reasons(
    top1: float, adjacent: float, displacement: float
) -> tuple[str, list[str], list[str]]:
    reasons: list[str] = []
    explanations: list[str] = []
    if top1 < STRICT_TOP1_THRESHOLD:
        reasons.append("LOW_TOP1_DOMINANCE")
        explanations.append(
            "Best first-rank acceptability is "
            f"{top1:.3f}, below the full-rank threshold {STRICT_TOP1_THRESHOLD:.2f}."
        )
    if adjacent < STRICT_ADJACENT_THRESHOLD:
        reasons.append("LOW_ADJACENT_CREDIBILITY")
        explanations.append(
            "Weakest adjacent pair credibility is "
            f"{adjacent:.3f}, below {STRICT_ADJACENT_THRESHOLD:.2f}."
        )
    if displacement > STRICT_DISPLACEMENT_THRESHOLD:
        reasons.append("HIGH_RANK_DISPLACEMENT")
        explanations.append(
            "Mean normalized rank displacement is "
            f"{displacement:.3f}, above {STRICT_DISPLACEMENT_THRESHOLD:.2f}."
        )

    if (
        top1 >= STRICT_TOP1_THRESHOLD
        and adjacent >= STRICT_ADJACENT_THRESHOLD
        and displacement <= STRICT_DISPLACEMENT_THRESHOLD
    ):
        return "full", [], []
    if (
        top1 >= TIER_TOP1_THRESHOLD
        and adjacent >= TIER_ADJACENT_THRESHOLD
        and displacement <= TIER_DISPLACEMENT_THRESHOLD
    ):
        return "tiered", reasons, explanations

    if top1 < TIER_TOP1_THRESHOLD and "REFUSAL_LOW_TOP1_DOMINANCE" not in reasons:
        reasons.append("REFUSAL_LOW_TOP1_DOMINANCE")
    if adjacent < TIER_ADJACENT_THRESHOLD and "REFUSAL_LOW_ADJACENT_CREDIBILITY" not in reasons:
        reasons.append("REFUSAL_LOW_ADJACENT_CREDIBILITY")
    if (
        displacement > TIER_DISPLACEMENT_THRESHOLD
        and "REFUSAL_HIGH_RANK_DISPLACEMENT" not in reasons
    ):
        reasons.append("REFUSAL_HIGH_RANK_DISPLACEMENT")
    explanations.append("The refusal gate blocks publication of a single linear ranking.")
    return "refusal", reasons, explanations


def _top_flip_pairs(
    pairwise_flip_probability: Mapping[str, float],
    pairwise_credibility: Mapping[str, float],
    *,
    limit: int = 5,
) -> list[dict[str, float | str]]:
    sorted_pairs = sorted(pairwise_flip_probability.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "pair": pair,
            "flip_probability": float(probability),
            "credibility": float(pairwise_credibility.get(pair, 0.0)),
        }
        for pair, probability in sorted_pairs[:limit]
    ]


def _flip_surfaces(
    utility_matrix: Array | None,
    reference_weights: Array,
    alternative_ids: Sequence[str],
    criteria_ids: Sequence[str],
    reference_order: Sequence[int],
) -> list[dict[str, Any]]:
    if utility_matrix is None or np.any(~np.isfinite(utility_matrix)):
        return []
    surfaces: list[dict[str, Any]] = []
    for left_pos, left in enumerate(reference_order):
        for right in reference_order[left_pos + 1 :]:
            coefficients = utility_matrix[left] - utility_matrix[right]
            dominant = np.argsort(-np.abs(coefficients))[: min(3, len(coefficients))]
            surfaces.append(
                {
                    "pair": _pair_key(left, right, alternative_ids),
                    "coefficients": {
                        criteria_ids[idx]: float(coefficients[idx])
                        for idx in range(len(criteria_ids))
                    },
                    "dominant_criteria": [
                        criteria_ids[idx] for idx in dominant if abs(coefficients[idx]) > 1e-12
                    ],
                    "reference_margin": float(np.dot(coefficients, reference_weights)),
                    "equation": " + ".join(
                        f"{coefficients[idx]:.6g}*{criteria_ids[idx]}"
                        for idx in range(len(criteria_ids))
                    )
                    + " = 0",
                }
            )
    return surfaces


def _lp_screen_for_model(
    coefficient: Array,
    weight_model: Mapping[str, Any],
    n_criteria: int,
) -> tuple[float, float]:
    from scipy.optimize import linprog  # type: ignore

    model_type = str(weight_model.get("type", "point")).lower()
    if model_type in {"ellipsoid", "logistic_normal"}:
        raise ValueError(f"{model_type} support is not linear")
    if model_type == "dirichlet":
        a_ub = np.zeros((0, n_criteria), dtype=float)
        b_ub = np.zeros((0,), dtype=float)
        a_eq = np.ones((1, n_criteria), dtype=float)
        b_eq = np.ones((1,), dtype=float)
        bounds = [(0.0, 1.0) for _ in range(n_criteria)]
    elif model_type in {"point", "fixed"}:
        weights = _normalize_weights(weight_model["weights"], n_criteria, name="point weights")
        a_ub = np.zeros((0, n_criteria), dtype=float)
        b_ub = np.zeros((0,), dtype=float)
        a_eq = np.ones((1, n_criteria), dtype=float)
        b_eq = np.ones((1,), dtype=float)
        bounds = [(float(value), float(value)) for value in weights]
    elif model_type in {"polytope", "interval"}:
        a_ub, b_ub, a_eq, b_eq, bounds = _polytope_constraints_from_model(weight_model, n_criteria)
    else:
        raise ValueError(f"unsupported LP screen model type: {model_type}")

    lower_result = linprog(
        c=coefficient,
        A_ub=a_ub if len(a_ub) else None,
        b_ub=b_ub if len(b_ub) else None,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    upper_result = linprog(
        c=-coefficient,
        A_ub=a_ub if len(a_ub) else None,
        b_ub=b_ub if len(b_ub) else None,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not lower_result.success or not upper_result.success:
        raise ValueError("LP screen could not solve one or more pairwise programs")
    return float(lower_result.fun), float(-upper_result.fun)


def _ror_screen(
    utility_matrix: Array | None,
    stakeholders: Sequence[_Stakeholder],
    alternative_ids: Sequence[str],
) -> dict[str, Any]:
    if utility_matrix is None:
        return {
            "ror_screen_status": "skipped_non_linear_method",
            "ror_screen_reason": "necessary/possible LP screen requires a linear utility matrix",
        }
    if np.any(~np.isfinite(utility_matrix)):
        return {
            "ror_screen_status": "skipped_missing_components",
            "ror_screen_reason": (
                "missing utility components trigger per-alternative weight renormalization"
            ),
        }
    try:
        import scipy.optimize  # noqa: F401  # type: ignore
    except Exception:
        return {
            "ror_screen_status": "skipped_missing_scipy",
            "ror_screen_reason": "scipy.optimize.linprog is unavailable",
        }

    n_alternatives, n_criteria = utility_matrix.shape
    active = [stakeholder for stakeholder in stakeholders if stakeholder.meta_weight > 0]
    if not active:
        return {
            "ror_screen_status": "skipped_no_active_stakeholders",
            "ror_screen_reason": "no positive-meta stakeholders were provided",
        }
    for stakeholder in active:
        model_type = str(stakeholder.weight_model.get("type", "point")).lower()
        if model_type in {"ellipsoid", "logistic_normal"}:
            return {
                "ror_screen_status": "skipped_unsupported_weight_model",
                "ror_screen_reason": f"{model_type} support is not a linear feasible region",
            }

    necessary: dict[str, bool] = {}
    possible: dict[str, bool] = {}
    bounds: dict[str, dict[str, float]] = {}
    tolerance = 1e-9
    for left in range(n_alternatives):
        for right in range(n_alternatives):
            if left == right:
                continue
            coefficient = utility_matrix[left] - utility_matrix[right]
            lower_values: list[float] = []
            upper_values: list[float] = []
            for stakeholder in active:
                lower, upper = _lp_screen_for_model(
                    coefficient, stakeholder.weight_model, n_criteria
                )
                lower_values.append(lower)
                upper_values.append(upper)
            global_lower = float(min(lower_values))
            global_upper = float(max(upper_values))
            key = _pair_key(left, right, alternative_ids)
            bounds[key] = {"min": global_lower, "max": global_upper}
            necessary[key] = bool(global_lower >= -tolerance)
            possible[key] = bool(global_upper >= -tolerance)

    return {
        "ror_screen_status": "ran",
        "ror_screen_reason": None,
        "pairwise_necessary": necessary,
        "pairwise_possible": possible,
        "pairwise_margin_bounds": bounds,
    }


def _evaluate_batches(
    score_evaluator: ScoreEvaluator,
    sample_weights: Array,
    sample_stakeholders: Array,
    stakeholders: Sequence[_Stakeholder],
    reference_positions: Array,
    reference_order: Sequence[int],
    n_alternatives: int,
    batch_size: int,
) -> dict[str, Any]:
    n_samples = sample_weights.shape[0]
    total_pairs = max(n_alternatives * (n_alternatives - 1) // 2, 1)

    rank_counts = np.zeros((n_alternatives, n_alternatives), dtype=float)
    pairwise_wins = np.zeros((n_alternatives, n_alternatives), dtype=float)
    pairwise_flips = np.zeros((n_alternatives, n_alternatives), dtype=float)
    reference_displacement = np.zeros(n_alternatives, dtype=float)
    kendall_counts = np.zeros(total_pairs + 1, dtype=float)
    top_weight_sums = np.zeros((n_alternatives, sample_weights.shape[1]), dtype=float)
    top_weight_counts = np.zeros(n_alternatives, dtype=float)

    stakeholder_rank_counts = {
        stakeholder.id: np.zeros((n_alternatives, n_alternatives), dtype=float)
        for stakeholder in stakeholders
    }

    for start in range(0, n_samples, batch_size):
        stop = min(start + batch_size, n_samples)
        weights = sample_weights[start:stop]
        stakeholder_slice = sample_stakeholders[start:stop]
        scores = np.asarray(score_evaluator(weights), dtype=float)
        if scores.shape != (n_alternatives, stop - start):
            raise ValueError(
                "score evaluator must return "
                f"({n_alternatives}, {stop - start}), got {scores.shape}"
            )
        for local_idx, score_vector in enumerate(scores.T):
            ranking, positions = _rank_positions_from_scores(score_vector)
            global_idx = start + local_idx
            top = int(ranking[0])
            rank_counts[np.arange(n_alternatives), positions] += 1
            top_weight_sums[top] += sample_weights[global_idx]
            top_weight_counts[top] += 1

            stakeholder = stakeholders[int(stakeholder_slice[local_idx])]
            stakeholder_rank_counts[stakeholder.id][np.arange(n_alternatives), positions] += 1

            reference_displacement += np.abs(positions - reference_positions)
            kendall = 0
            for left_pos, left in enumerate(reference_order):
                for right in reference_order[left_pos + 1 :]:
                    if positions[left] > positions[right]:
                        kendall += 1
            kendall_counts[kendall] += 1

            for left in range(n_alternatives):
                for right in range(n_alternatives):
                    if left == right:
                        continue
                    if positions[left] < positions[right]:
                        pairwise_wins[left, right] += 1
                    reference_sign = reference_positions[left] < reference_positions[right]
                    sample_sign = positions[left] < positions[right]
                    if reference_sign != sample_sign:
                        pairwise_flips[left, right] += 1

    return {
        "rank_counts": rank_counts,
        "pairwise_wins": pairwise_wins,
        "pairwise_flips": pairwise_flips,
        "reference_displacement": reference_displacement,
        "kendall_counts": kendall_counts,
        "top_weight_sums": top_weight_sums,
        "top_weight_counts": top_weight_counts,
        "stakeholder_rank_counts": stakeholder_rank_counts,
    }


def _normalize_aggregation(aggregation: Mapping[str, Any] | None) -> dict[str, Any]:
    if aggregation is None:
        return {"rule": "uncertainty_kemeny", "allow_refusal": True}
    return {
        "rule": str(aggregation.get("rule", "uncertainty_kemeny")),
        "allow_refusal": bool(aggregation.get("allow_refusal", True)),
    }


def _rank_stability_core(
    *,
    method: str,
    score_evaluator: ScoreEvaluator,
    n_alternatives: int,
    n_criteria: int,
    stakeholders: Sequence[Mapping[str, Any]],
    n_samples: int,
    seed: int,
    reference_weights: Sequence[float] | None,
    alternative_ids: Sequence[Any] | None,
    criteria_ids: Sequence[Any] | None,
    aggregation: Mapping[str, Any] | None,
    batch_size: int,
    linear_utility_matrix: Array | None,
    extra_output: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    alternative_labels = _coerce_ids(alternative_ids, n_alternatives, "A")
    criteria_labels = _coerce_ids(criteria_ids, n_criteria, "c")
    prepared_stakeholders = _prepare_stakeholders(stakeholders, n_criteria)
    normalized_aggregation = _normalize_aggregation(aggregation)
    rng = np.random.default_rng(seed)

    ref_weights = _reference_weights(prepared_stakeholders, n_criteria, reference_weights)
    reference_scores = np.asarray(score_evaluator(ref_weights[None, :]), dtype=float)[:, 0]
    reference_order, reference_positions = _rank_positions_from_scores(reference_scores)

    compromise_weights = _reference_weights(prepared_stakeholders, n_criteria, None)
    compromise_scores = np.asarray(score_evaluator(compromise_weights[None, :]), dtype=float)[:, 0]
    compromise_order, _ = _rank_positions_from_scores(compromise_scores)

    sample_weights, sample_stakeholders, sample_counts = _sample_stakeholder_weights(
        prepared_stakeholders,
        n_samples,
        n_criteria,
        rng,
    )
    stats = _evaluate_batches(
        score_evaluator,
        sample_weights,
        sample_stakeholders,
        prepared_stakeholders,
        reference_positions,
        reference_order.tolist(),
        n_alternatives,
        max(1, int(batch_size)),
    )

    rank_acceptability_matrix = stats["rank_counts"] / n_samples
    pairwise_probabilities = stats["pairwise_wins"] / n_samples
    pairwise_flip_matrix = stats["pairwise_flips"] / n_samples
    reference_displacement = stats["reference_displacement"] / n_samples
    kendall_counts = stats["kendall_counts"] / n_samples

    consensus_order = _kemeny_consensus(pairwise_probabilities)
    selected_order = (
        compromise_order.tolist()
        if normalized_aggregation["rule"] == "compromise_barycenter"
        else consensus_order
    )
    selected_positions = np.empty(n_alternatives, dtype=int)
    selected_positions[selected_order] = np.arange(n_alternatives)

    aggregate_displacement = np.zeros(n_alternatives, dtype=float)
    for alt_idx in range(n_alternatives):
        aggregate_displacement[alt_idx] = float(
            np.sum(
                rank_acceptability_matrix[alt_idx]
                * np.abs(np.arange(n_alternatives) - selected_positions[alt_idx])
            )
        )

    top1 = float(np.max(rank_acceptability_matrix[:, 0]))
    if n_alternatives <= 1:
        adjacent = 1.0
        mean_rank_displacement = 0.0
    else:
        adjacent = float(
            min(pairwise_probabilities[left, right] for left, right in pairwise(selected_order))
        )
        mean_rank_displacement = float(
            np.sum(aggregate_displacement) / (n_alternatives * (n_alternatives - 1))
        )

    status, reason_codes, explanations = _status_and_reasons(top1, adjacent, mean_rank_displacement)

    top_rank_acceptability = {
        alternative_labels[idx]: float(rank_acceptability_matrix[idx, 0])
        for idx in range(n_alternatives)
    }
    rank_acceptability = {
        alternative_labels[idx]: [float(value) for value in rank_acceptability_matrix[idx]]
        for idx in range(n_alternatives)
    }
    rank_intervals: dict[str, list[int | None]] = {}
    for idx in range(n_alternatives):
        nonzero = np.where(rank_acceptability_matrix[idx] > 0)[0]
        rank_intervals[alternative_labels[idx]] = (
            [int(nonzero[0] + 1), int(nonzero[-1] + 1)] if len(nonzero) else [None, None]
        )

    pairwise_credibility = {
        _pair_key(left, right, alternative_labels): float(pairwise_probabilities[left, right])
        for left in range(n_alternatives)
        for right in range(n_alternatives)
        if left != right
    }
    pairwise_flip_probability = {
        _pair_key(left, right, alternative_labels): float(pairwise_flip_matrix[left, right])
        for left_pos, left in enumerate(reference_order)
        for right in reference_order[left_pos + 1 :]
    }

    central_weight_vectors: dict[str, list[float] | None] = {}
    for idx in range(n_alternatives):
        count = stats["top_weight_counts"][idx]
        central_weight_vectors[alternative_labels[idx]] = (
            [float(value) for value in stats["top_weight_sums"][idx] / count] if count > 0 else None
        )

    stakeholder_summaries: dict[str, Any] = {}
    for stakeholder in prepared_stakeholders:
        count = sample_counts.get(stakeholder.id, 0)
        if count > 0:
            matrix = stats["stakeholder_rank_counts"][stakeholder.id] / count
        else:
            matrix = np.zeros((n_alternatives, n_alternatives), dtype=float)
        stakeholder_summaries[stakeholder.id] = {
            "meta_weight": float(stakeholder.meta_weight),
            "sample_count": int(count),
            "top_rank_acceptability": {
                alternative_labels[idx]: float(matrix[idx, 0]) for idx in range(n_alternatives)
            },
        }

    kendall_expected = float(sum(idx * value for idx, value in enumerate(kendall_counts)))
    kendall_normalized = (
        kendall_expected / (n_alternatives * (n_alternatives - 1) / 2)
        if n_alternatives > 1
        else 0.0
    )

    result: dict[str, Any] = {
        "method": method,
        "aggregation_rule": normalized_aggregation["rule"],
        "allow_refusal": normalized_aggregation["allow_refusal"],
        "status": status,
        "aggregate_ranking": _ranking_to_ids(selected_order, alternative_labels),
        "consensus_ranking": _ranking_to_ids(consensus_order, alternative_labels),
        "compromise_ranking": _ranking_to_ids(compromise_order.tolist(), alternative_labels),
        "reference_ranking": _ranking_to_ids(reference_order.tolist(), alternative_labels),
        "tiers": _build_tiers(selected_order, pairwise_probabilities, alternative_labels),
        "top_rank_acceptability": top_rank_acceptability,
        "rank_acceptability": rank_acceptability,
        "rank_intervals": rank_intervals,
        "expected_rank_displacement": {
            alternative_labels[idx]: float(reference_displacement[idx])
            for idx in range(n_alternatives)
        },
        "aggregate_rank_displacement": {
            alternative_labels[idx]: float(aggregate_displacement[idx])
            for idx in range(n_alternatives)
        },
        "pairwise_credibility": pairwise_credibility,
        "pairwise_flip_probability": pairwise_flip_probability,
        "kendall_distribution": {
            str(idx): float(value) for idx, value in enumerate(kendall_counts) if value > 0
        },
        "kendall_expected_normalized": float(kendall_normalized),
        "central_weight_vectors": central_weight_vectors,
        "reference_weights": [float(value) for value in ref_weights],
        "compromise_weights": [float(value) for value in compromise_weights],
        "reference_scores": {
            alternative_labels[idx]: float(reference_scores[idx]) for idx in range(n_alternatives)
        },
        "gate_metrics": {
            "top1_dominance": top1,
            "adjacent_pair_min_credibility": adjacent,
            "mean_rank_displacement": mean_rank_displacement,
        },
        "refusal_reason_codes": reason_codes,
        "explanations": explanations,
        "top_flip_pairs": _top_flip_pairs(pairwise_flip_probability, pairwise_credibility),
        "stakeholder_summaries": stakeholder_summaries,
        "n_samples": int(n_samples),
        "seed": int(seed),
    }
    result.update(
        _ror_screen(
            linear_utility_matrix,
            prepared_stakeholders,
            alternative_labels,
        )
    )
    result["flip_surfaces"] = _flip_surfaces(
        linear_utility_matrix,
        ref_weights,
        alternative_labels,
        criteria_labels,
        reference_order.tolist(),
    )
    if extra_output:
        result.update(extra_output)
    return result


def run_additive_rank_stability(
    utility_matrix: Any,
    stakeholders: Sequence[Mapping[str, Any]],
    *,
    n_samples: int = 50_000,
    seed: int = 0,
    reference_weights: Sequence[float] | None = None,
    alternative_ids: Sequence[Any] | None = None,
    criteria_ids: Sequence[Any] | None = None,
    aggregation: Mapping[str, Any] | None = None,
    batch_size: int = 4096,
) -> dict[str, Any]:
    """Run SMAA-style rank stability for an additive utility matrix."""
    utility = _as_2d_float("utility_matrix", utility_matrix)

    def evaluator(weights: Array) -> Array:
        return _renormalized_linear_scores(utility, weights)

    return _rank_stability_core(
        method="additive",
        score_evaluator=evaluator,
        n_alternatives=utility.shape[0],
        n_criteria=utility.shape[1],
        stakeholders=stakeholders,
        n_samples=n_samples,
        seed=seed,
        reference_weights=reference_weights,
        alternative_ids=alternative_ids,
        criteria_ids=criteria_ids,
        aggregation=aggregation,
        batch_size=batch_size,
        linear_utility_matrix=utility,
    )


def _topsis_scores(decision_matrix: Array, is_benefit: Array, weights: Array) -> Array:
    norms = np.sqrt(np.sum(decision_matrix**2, axis=0))
    norms = np.where(norms > 0, norms, 1.0)
    normalized = decision_matrix / norms
    ideal = np.where(is_benefit, np.max(normalized, axis=0), np.min(normalized, axis=0))
    anti_ideal = np.where(is_benefit, np.min(normalized, axis=0), np.max(normalized, axis=0))

    plus_base = (normalized - ideal) ** 2
    minus_base = (normalized - anti_ideal) ** 2
    squared_weights = weights.T**2
    d_plus = np.sqrt(plus_base @ squared_weights)
    d_minus = np.sqrt(minus_base @ squared_weights)
    denom = d_plus + d_minus
    closeness = np.zeros_like(denom)
    np.divide(d_minus, denom, out=closeness, where=denom > 1e-12)
    return closeness


def _topsis_reference_output(
    decision_matrix: Array, is_benefit: Array, weights: Array
) -> dict[str, Any]:
    scores = _topsis_scores(decision_matrix, is_benefit, weights[None, :])[:, 0]
    ranking, _ = _rank_positions_from_scores(scores)
    norms = np.sqrt(np.sum(decision_matrix**2, axis=0))
    norms = np.where(norms > 0, norms, 1.0)
    normalized = decision_matrix / norms
    weighted = normalized * weights
    ideal = np.where(is_benefit, np.max(weighted, axis=0), np.min(weighted, axis=0))
    anti_ideal = np.where(is_benefit, np.min(weighted, axis=0), np.max(weighted, axis=0))
    d_plus = np.sqrt(np.sum((weighted - ideal) ** 2, axis=1))
    d_minus = np.sqrt(np.sum((weighted - anti_ideal) ** 2, axis=1))
    return {
        "reference_method_output": {
            "closeness_coefficients": [float(value) for value in scores],
            "ranking": [int(value) for value in ranking],
            "best_alternative": int(ranking[0]),
            "d_plus": [float(value) for value in d_plus],
            "d_minus": [float(value) for value in d_minus],
        }
    }


def run_topsis_rank_stability(
    decision_matrix: Any,
    is_benefit: Sequence[bool],
    stakeholders: Sequence[Mapping[str, Any]],
    *,
    n_samples: int = 50_000,
    seed: int = 0,
    reference_weights: Sequence[float] | None = None,
    alternative_ids: Sequence[Any] | None = None,
    criteria_ids: Sequence[Any] | None = None,
    aggregation: Mapping[str, Any] | None = None,
    batch_size: int = 4096,
) -> dict[str, Any]:
    """Run robust TOPSIS under stakeholder weight uncertainty."""
    dm = _as_2d_float("decision_matrix", decision_matrix)
    benefit_flags = _as_bool_vector("is_benefit", is_benefit, dm.shape[1])

    def evaluator(weights: Array) -> Array:
        return _topsis_scores(dm, benefit_flags, weights)

    prepared = _prepare_stakeholders(stakeholders, dm.shape[1])
    ref_weights = _reference_weights(prepared, dm.shape[1], reference_weights)
    return _rank_stability_core(
        method="topsis",
        score_evaluator=evaluator,
        n_alternatives=dm.shape[0],
        n_criteria=dm.shape[1],
        stakeholders=stakeholders,
        n_samples=n_samples,
        seed=seed,
        reference_weights=reference_weights,
        alternative_ids=alternative_ids,
        criteria_ids=criteria_ids,
        aggregation=aggregation,
        batch_size=batch_size,
        linear_utility_matrix=None,
        extra_output=_topsis_reference_output(dm, benefit_flags, ref_weights),
    )


def run_ahp_rank_stability(
    local_priority_matrix: Any,
    stakeholders: Sequence[Mapping[str, Any]],
    *,
    n_samples: int = 50_000,
    seed: int = 0,
    reference_weights: Sequence[float] | None = None,
    alternative_ids: Sequence[Any] | None = None,
    criteria_ids: Sequence[Any] | None = None,
    aggregation: Mapping[str, Any] | None = None,
    batch_size: int = 4096,
) -> dict[str, Any]:
    """Run robust AHP after criterion-local alternative priorities are known."""
    priorities = _as_2d_float("local_priority_matrix", local_priority_matrix)

    def evaluator(weights: Array) -> Array:
        return _renormalized_linear_scores(priorities, weights)

    result = _rank_stability_core(
        method="ahp",
        score_evaluator=evaluator,
        n_alternatives=priorities.shape[0],
        n_criteria=priorities.shape[1],
        stakeholders=stakeholders,
        n_samples=n_samples,
        seed=seed,
        reference_weights=reference_weights,
        alternative_ids=alternative_ids,
        criteria_ids=criteria_ids,
        aggregation=aggregation,
        batch_size=batch_size,
        linear_utility_matrix=priorities,
    )
    result["reference_method_output"] = {
        "local_priority_matrix": priorities.tolist(),
        "priority_weights": result["reference_weights"],
    }
    return result


def _electre_reference_output(
    decision_matrix: Array,
    is_benefit: Array,
    weights: Array,
    concordance_threshold: float,
    discordance_threshold: float,
) -> dict[str, Any]:
    n_alt = decision_matrix.shape[0]
    ranges = np.ptp(decision_matrix, axis=0)
    ranges = np.where(ranges > 0, ranges, 1.0)
    concordance = np.zeros((n_alt, n_alt), dtype=float)
    discordance = np.zeros((n_alt, n_alt), dtype=float)
    for left in range(n_alt):
        for right in range(n_alt):
            if left == right:
                continue
            better_or_equal = np.where(
                is_benefit,
                decision_matrix[left] >= decision_matrix[right],
                decision_matrix[left] <= decision_matrix[right],
            )
            concordance[left, right] = float(np.sum(weights[better_or_equal]))
            disadvantage = np.where(
                is_benefit,
                decision_matrix[right] - decision_matrix[left],
                decision_matrix[left] - decision_matrix[right],
            )
            discordance[left, right] = float(np.max(np.maximum(disadvantage, 0.0) / ranges))
    outranks = (concordance >= concordance_threshold) & (discordance <= discordance_threshold)
    np.fill_diagonal(outranks, False)
    net_concordance = np.sum(concordance, axis=1) - np.sum(concordance, axis=0)
    net_discordance = np.sum(discordance, axis=1) - np.sum(discordance, axis=0)
    dominated = np.any(outranks, axis=0)
    return {
        "reference_method_output": {
            "concordance_matrix": concordance.tolist(),
            "discordance_matrix": discordance.tolist(),
            "outranking_matrix": outranks.tolist(),
            "kernel": [int(idx) for idx in range(n_alt) if not dominated[idx]],
            "net_concordance": [float(value) for value in net_concordance],
            "net_discordance": [float(value) for value in net_discordance],
        }
    }


def _electre_scores(
    decision_matrix: Array,
    is_benefit: Array,
    weights: Array,
    concordance_threshold: float,
    discordance_threshold: float,
) -> Array:
    n_alt, _ = decision_matrix.shape
    ranges = np.ptp(decision_matrix, axis=0)
    ranges = np.where(ranges > 0, ranges, 1.0)
    better = np.zeros((n_alt, n_alt, decision_matrix.shape[1]), dtype=float)
    disadvantage = np.zeros_like(better)
    for left in range(n_alt):
        for right in range(n_alt):
            if left == right:
                continue
            better[left, right] = np.where(
                is_benefit,
                decision_matrix[left] >= decision_matrix[right],
                decision_matrix[left] <= decision_matrix[right],
            )
            raw_disadvantage = np.where(
                is_benefit,
                decision_matrix[right] - decision_matrix[left],
                decision_matrix[left] - decision_matrix[right],
            )
            disadvantage[left, right] = np.maximum(raw_disadvantage, 0.0) / ranges
    discordance = np.max(disadvantage, axis=2)
    concordance_batches = np.tensordot(better, weights.T, axes=([2], [0]))
    scores = np.zeros((n_alt, weights.shape[0]), dtype=float)
    for batch_idx in range(weights.shape[0]):
        concordance = concordance_batches[:, :, batch_idx]
        outranks = (concordance >= concordance_threshold) & (discordance <= discordance_threshold)
        np.fill_diagonal(outranks, False)
        net_flow = np.sum(outranks, axis=1) - np.sum(outranks, axis=0)
        net_concordance = np.sum(concordance, axis=1) - np.sum(concordance, axis=0)
        net_discordance = np.sum(discordance, axis=1) - np.sum(discordance, axis=0)
        scores[:, batch_idx] = net_flow + 1e-3 * net_concordance - 1e-6 * net_discordance
    return scores


def run_electre_rank_stability(
    decision_matrix: Any,
    is_benefit: Sequence[bool],
    stakeholders: Sequence[Mapping[str, Any]],
    *,
    concordance_threshold: float = 0.65,
    discordance_threshold: float = 0.35,
    n_samples: int = 50_000,
    seed: int = 0,
    reference_weights: Sequence[float] | None = None,
    alternative_ids: Sequence[Any] | None = None,
    criteria_ids: Sequence[Any] | None = None,
    aggregation: Mapping[str, Any] | None = None,
    batch_size: int = 4096,
) -> dict[str, Any]:
    """Run robust ELECTRE-style outranking under uncertain weights."""
    dm = _as_2d_float("decision_matrix", decision_matrix)
    benefit_flags = _as_bool_vector("is_benefit", is_benefit, dm.shape[1])
    c_threshold = float(concordance_threshold)
    d_threshold = float(discordance_threshold)
    if not (0.0 <= c_threshold <= 1.0 and 0.0 <= d_threshold <= 1.0):
        raise ValueError("ELECTRE thresholds must be in [0, 1]")

    def evaluator(weights: Array) -> Array:
        return _electre_scores(dm, benefit_flags, weights, c_threshold, d_threshold)

    prepared = _prepare_stakeholders(stakeholders, dm.shape[1])
    ref_weights = _reference_weights(prepared, dm.shape[1], reference_weights)
    return _rank_stability_core(
        method="electre",
        score_evaluator=evaluator,
        n_alternatives=dm.shape[0],
        n_criteria=dm.shape[1],
        stakeholders=stakeholders,
        n_samples=n_samples,
        seed=seed,
        reference_weights=reference_weights,
        alternative_ids=alternative_ids,
        criteria_ids=criteria_ids,
        aggregation=aggregation,
        batch_size=batch_size,
        linear_utility_matrix=None,
        extra_output=_electre_reference_output(
            dm, benefit_flags, ref_weights, c_threshold, d_threshold
        ),
    )


__all__ = [
    "run_additive_rank_stability",
    "run_ahp_rank_stability",
    "run_electre_rank_stability",
    "run_topsis_rank_stability",
]
