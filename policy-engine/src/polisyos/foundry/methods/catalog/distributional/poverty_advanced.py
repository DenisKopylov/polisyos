"""Public distributional poverty advanced module API."""
from __future__ import annotations

from itertools import product
from typing import Any, ClassVar, Mapping, Sequence

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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
            )
        }
    )


def _normalize_weights(weights: np.ndarray, *, expected_dims: int) -> np.ndarray:
    if weights.ndim != 1:
        raise ValueError("weights must be a 1D vector")
    if weights.shape[0] != expected_dims:
        raise ValueError("weights length must match number of dimensions")
    if np.any(~np.isfinite(weights)):
        raise ValueError("weights must contain only finite values")
    if np.any(weights < 0.0):
        raise ValueError("weights must be non-negative")
    weight_sum = float(np.sum(weights))
    if weight_sum <= 0.0:
        raise ValueError("weights must sum to a positive value")
    return weights / weight_sum


def _normalize_category_label(value: Any, *, field_name: str) -> tuple[str, Any]:
    if isinstance(value, np.generic):
        value = value.item()
    elif hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass

    if value is None:
        raise ValueError(f"{field_name} must not contain null category labels")
    if isinstance(value, (str, bytes)):
        label = value.decode() if isinstance(value, bytes) else value
        if not label:
            raise ValueError(f"{field_name} must not contain empty category labels")
        return ("text", label)
    if isinstance(value, (bool, np.bool_)):
        return ("bool", bool(value))
    if isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
        if not np.isfinite(numeric):
            raise ValueError(f"{field_name} must contain only finite numeric labels")
        return ("number", numeric)
    raise TypeError(
        f"{field_name} must contain only finite numeric, string, or boolean category labels"
    )


def _coerce_category_orders(raw_orders: Any, *, n_dims: int) -> tuple[tuple[tuple[str, Any], ...], ...]:
    if raw_orders is None:
        raise ValueError("category_orders parameter is required")
    if not isinstance(raw_orders, Sequence) or isinstance(raw_orders, (str, bytes)):
        raise TypeError("category_orders must be a sequence of per-dimension category orders")
    if len(raw_orders) != n_dims:
        raise ValueError("category_orders length must match number of dimensions")

    normalized_orders: list[tuple[tuple[str, Any], ...]] = []
    for dim_index, raw_order in enumerate(raw_orders):
        if not isinstance(raw_order, Sequence) or isinstance(raw_order, (str, bytes)):
            raise TypeError(f"category_orders[{dim_index}] must be a sequence")
        values = tuple(
            _normalize_category_label(
                value,
                field_name=f"category_orders[{dim_index}]",
            )
            for value in raw_order
        )
        if len(values) < 2:
            raise ValueError(f"category_orders[{dim_index}] must contain at least two categories")
        if len(set(values)) != len(values):
            raise ValueError(f"category_orders[{dim_index}] must not contain duplicates")
        normalized_orders.append(values)
    return tuple(normalized_orders)


def _coerce_numeric_category_orders(raw_orders: Any, *, n_dims: int) -> tuple[tuple[float, ...], ...]:
    if raw_orders is None:
        raise ValueError("numeric category_orders are required")
    if not isinstance(raw_orders, Sequence) or isinstance(raw_orders, (str, bytes)):
        raise TypeError("numeric category_orders must be a sequence of per-dimension category orders")
    if len(raw_orders) != n_dims:
        raise ValueError("numeric category_orders length must match number of dimensions")

    normalized_orders: list[tuple[float, ...]] = []
    for dim_index, raw_order in enumerate(raw_orders):
        if not isinstance(raw_order, Sequence) or isinstance(raw_order, (str, bytes)):
            raise TypeError(f"numeric category_orders[{dim_index}] must be a sequence")
        values = tuple(float(value) for value in raw_order)
        if len(values) < 2:
            raise ValueError(f"numeric category_orders[{dim_index}] must contain at least two categories")
        if any(not np.isfinite(value) for value in values):
            raise ValueError(
                f"numeric category_orders[{dim_index}] must contain only finite numeric values"
            )
        if len(set(values)) != len(values):
            raise ValueError(f"numeric category_orders[{dim_index}] must not contain duplicates")
        normalized_orders.append(values)
    return tuple(normalized_orders)


def _coerce_int_vector(
    raw_values: Any,
    *,
    name: str,
    expected_dims: int,
) -> np.ndarray:
    if raw_values is None:
        raise ValueError(f"{name} parameter is required")
    arr = np.asarray(raw_values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D vector")
    if arr.shape[0] != expected_dims:
        raise ValueError(f"{name} length must match number of dimensions")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    rounded = np.rint(arr)
    if np.any(np.abs(arr - rounded) > 1.0e-9):
        raise ValueError(f"{name} must contain integer-valued cutoffs")
    return rounded.astype(int)


def _coerce_dimension_names(raw_names: Any, *, n_dims: int) -> tuple[str, ...]:
    if raw_names is None:
        return tuple(f"dimension_{index}" for index in range(n_dims))
    if not isinstance(raw_names, Sequence) or isinstance(raw_names, (str, bytes)):
        raise TypeError("dimension_names must be a sequence of strings")
    if len(raw_names) != n_dims:
        raise ValueError("dimension_names length must match number of dimensions")
    names = tuple(str(value).strip() for value in raw_names)
    if any(not name for name in names):
        raise ValueError("dimension_names must contain non-empty strings")
    return names


def _map_category_matrix_to_ranks(
    category_matrix: np.ndarray,
    *,
    category_orders: tuple[tuple[tuple[str, Any], ...], ...],
) -> np.ndarray:
    n_agents, n_dims = category_matrix.shape
    ranks = np.zeros((n_agents, n_dims), dtype=int)
    for dim_index, order in enumerate(category_orders):
        code_to_rank = {code: rank for rank, code in enumerate(order, start=1)}
        column = category_matrix[:, dim_index]
        ranked = np.fromiter(
            (
                code_to_rank.get(
                    _normalize_category_label(
                        value,
                        field_name=f"category_matrix[:, {dim_index}]",
                    ),
                    0,
                )
                for value in column
            ),
            dtype=int,
            count=n_agents,
        )
        if np.any(ranked == 0):
            bad_value = column[np.flatnonzero(ranked == 0)[0]]
            raise ValueError(
                f"category_matrix column {dim_index} contains value {bad_value!r} "
                "not present in category_orders"
            )
        ranks[:, dim_index] = ranked
    return ranks


def _resolve_threshold_weights(
    raw_threshold_weights: Any,
    *,
    category_orders: tuple[tuple[tuple[str, Any], ...], ...],
    deprivation_cutoffs: np.ndarray,
) -> tuple[np.ndarray, ...]:
    schedules: list[np.ndarray] = []
    n_dims = len(category_orders)

    if raw_threshold_weights is None or raw_threshold_weights == "equal":
        for order in category_orders:
            n_steps = len(order) - 1
            schedules.append(np.full(n_steps, 1.0 / n_steps, dtype=float))
        return tuple(schedules)

    if raw_threshold_weights == "af_last":
        for dim_index, order in enumerate(category_orders):
            n_steps = len(order) - 1
            schedule = np.zeros(n_steps, dtype=float)
            schedule[int(deprivation_cutoffs[dim_index]) - 1] = 1.0
            schedules.append(schedule)
        return tuple(schedules)

    if not isinstance(raw_threshold_weights, Sequence) or isinstance(raw_threshold_weights, (str, bytes)):
        raise TypeError("threshold_weights must be None, 'equal', 'af_last', or a per-dimension sequence")
    if len(raw_threshold_weights) != n_dims:
        raise ValueError("threshold_weights length must match number of dimensions")

    for dim_index, (order, raw_schedule) in enumerate(zip(category_orders, raw_threshold_weights, strict=True)):
        if not isinstance(raw_schedule, Sequence) or isinstance(raw_schedule, (str, bytes)):
            raise TypeError(f"threshold_weights[{dim_index}] must be a sequence")
        schedule = np.asarray(raw_schedule, dtype=float)
        n_steps = len(order) - 1
        if schedule.ndim != 1 or schedule.shape[0] != n_steps:
            raise ValueError(
                f"threshold_weights[{dim_index}] must have length {n_steps} "
                f"for {len(order)} ordered categories"
            )
        if np.any(~np.isfinite(schedule)):
            raise ValueError(f"threshold_weights[{dim_index}] must contain only finite values")
        if np.any(schedule < 0.0):
            raise ValueError(f"threshold_weights[{dim_index}] must be non-negative")
        total = float(np.sum(schedule))
        if total <= 0.0:
            raise ValueError(f"threshold_weights[{dim_index}] must sum to a positive value")
        schedules.append(schedule / total)
    return tuple(schedules)


def _build_delta_lookups(
    *,
    category_orders: tuple[tuple[tuple[str, Any], ...], ...],
    deprivation_cutoffs: np.ndarray,
    threshold_weights: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, ...]:
    lookups: list[np.ndarray] = []
    for order, cutoff, schedule in zip(category_orders, deprivation_cutoffs, threshold_weights, strict=True):
        n_categories = len(order)
        lookup = np.zeros(n_categories + 1, dtype=float)
        if int(cutoff) > 0:
            active = schedule[: int(cutoff)]
            lookup[1 : int(cutoff) + 1] = np.cumsum(active[::-1], dtype=float)[::-1]
        lookups.append(lookup)
    return tuple(lookups)


def _coerce_beta(raw_beta: Any) -> float:
    beta = float(raw_beta if raw_beta is not None else 1.0)
    if not np.isfinite(beta) or beta < 1.0:
        raise ValueError("beta must be finite and >= 1.0")
    return beta


def _coerce_bool(raw_value: Any, *, default: bool) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    raise TypeError("boolean parameters must be True/False")


def _coerce_cutoff_grid(
    raw_grid: Any,
    *,
    deprivation_cutoffs: np.ndarray,
    category_orders: tuple[tuple[float, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    if raw_grid is None:
        local_grid: list[tuple[int, ...]] = []
        for cutoff, order in zip(deprivation_cutoffs, category_orders, strict=True):
            candidates = {int(cutoff)}
            if cutoff > 1:
                candidates.add(int(cutoff) - 1)
            if cutoff < len(order) - 1:
                candidates.add(int(cutoff) + 1)
            local_grid.append(tuple(sorted(candidates)))
        return tuple(local_grid)

    n_dims = deprivation_cutoffs.shape[0]
    if not isinstance(raw_grid, Sequence) or isinstance(raw_grid, (str, bytes)):
        raise TypeError("cutoff_grid must be a sequence of per-dimension candidate cutoffs")
    if len(raw_grid) != n_dims:
        raise ValueError("cutoff_grid length must match number of dimensions")

    normalized_grid: list[tuple[int, ...]] = []
    for dim_index, (raw_candidates, order, current_cutoff) in enumerate(
        zip(raw_grid, category_orders, deprivation_cutoffs, strict=True)
    ):
        if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes)):
            raise TypeError(f"cutoff_grid[{dim_index}] must be a sequence")
        candidates = _coerce_int_vector(
            raw_candidates,
            name=f"cutoff_grid[{dim_index}]",
            expected_dims=len(raw_candidates),
        )
        valid_candidates = sorted({int(value) for value in candidates.tolist()} | {int(current_cutoff)})
        if valid_candidates[0] < 1 or valid_candidates[-1] >= len(order):
            raise ValueError(
                f"cutoff_grid[{dim_index}] must stay within [1, {len(order) - 1}]"
            )
        normalized_grid.append(tuple(valid_candidates))
    return tuple(normalized_grid)


def _compute_ordinal_core(
    *,
    rank_matrix: np.ndarray,
    weights: np.ndarray,
    deprivation_cutoffs: np.ndarray,
    delta_lookups: tuple[np.ndarray, ...],
    k_threshold: float,
    beta: float,
) -> dict[str, Any]:
    cutoff_tol = 1.0e-9
    deprivation_matrix = (rank_matrix <= deprivation_cutoffs[None, :]).astype(float)
    breadth_scores = deprivation_matrix @ weights
    poor_mask = breadth_scores >= (k_threshold - cutoff_tol)

    delta_matrix = np.column_stack(
        [lookup[rank_matrix[:, dim_index]] for dim_index, lookup in enumerate(delta_lookups)]
    )
    severity_scores = delta_matrix @ weights
    transformed_scores = severity_scores ** beta
    censored_scores = transformed_scores * poor_mask.astype(float)

    headcount_h = float(np.mean(poor_mask))
    ordinal_intensity_a = float(np.mean(transformed_scores[poor_mask])) if np.any(poor_mask) else 0.0
    ordinal_adjusted_headcount_q = float(np.mean(censored_scores))
    af_m0 = float(np.mean(breadth_scores * poor_mask.astype(float)))

    return {
        "deprivation_matrix": deprivation_matrix,
        "breadth_scores": breadth_scores,
        "poor_mask": poor_mask,
        "delta_matrix": delta_matrix,
        "severity_scores": severity_scores,
        "transformed_scores": transformed_scores,
        "censored_scores": censored_scores,
        "headcount_h": headcount_h,
        "ordinal_intensity_a": ordinal_intensity_a,
        "ordinal_adjusted_headcount_q": ordinal_adjusted_headcount_q,
        "af_m0": af_m0,
    }


def _diagnostic_status(*, slope: float, flip_share: float) -> str:
    if slope <= 0.02 and flip_share <= 0.05:
        return "green"
    if slope <= 0.05 and flip_share <= 0.15:
        return "yellow"
    return "red"


def _build_dimension_contributions(
    *,
    core: Mapping[str, Any],
    weights: np.ndarray,
    dimension_names: tuple[str, ...],
    beta: float,
) -> dict[str, Any]:
    if abs(beta - 1.0) > 1.0e-9:
        return {
            "available": False,
            "note": "Exact additive dimension contributions are only available for beta=1.0.",
        }

    poor_mask = np.asarray(core["poor_mask"], dtype=bool)
    delta_matrix = np.asarray(core["delta_matrix"], dtype=float)
    censored_dimension_scores = delta_matrix * weights[None, :] * poor_mask[:, None]
    contributions = np.mean(censored_dimension_scores, axis=0)
    total_q = float(core["ordinal_adjusted_headcount_q"])

    payload: dict[str, Any] = {"available": True, "by_dimension": {}}
    for dim_index, name in enumerate(dimension_names):
        contribution = float(contributions[dim_index])
        share = float(contribution / total_q) if total_q > 0.0 else 0.0
        payload["by_dimension"][name] = {
            "dimension_index": dim_index,
            "contribution": contribution,
            "share": share,
        }
    return payload


def _build_cutoff_diagnostics(
    *,
    rank_matrix: np.ndarray,
    weights: np.ndarray,
    category_orders: tuple[tuple[tuple[str, Any], ...], ...],
    deprivation_cutoffs: np.ndarray,
    threshold_weights: tuple[np.ndarray, ...],
    k_threshold: float,
    beta: float,
    baseline_core: Mapping[str, Any],
    dimension_names: tuple[str, ...],
    cutoff_grid: tuple[tuple[int, ...], ...],
    max_cutoff_grid_size: int,
) -> dict[str, Any]:
    baseline_q = float(baseline_core["ordinal_adjusted_headcount_q"])
    baseline_breadth = np.asarray(baseline_core["breadth_scores"], dtype=float)
    baseline_poor = np.asarray(baseline_core["poor_mask"], dtype=bool)
    n_dims = deprivation_cutoffs.shape[0]

    local_slopes: dict[str, float] = {}
    flip_shares: dict[str, float] = {}
    local_upper_bounds: dict[str, float] = {}
    per_dimension: dict[str, Any] = {}

    for dim_index in range(n_dims):
        name = dimension_names[dim_index]
        n_steps = len(category_orders[dim_index]) - 1
        margin_share = float(
            np.mean(
                (baseline_breadth >= (k_threshold - weights[dim_index]))
                & (baseline_breadth < (k_threshold + weights[dim_index]))
            )
        )
        upper_bound = float(weights[dim_index] / n_steps + margin_share)
        neighbors: list[dict[str, Any]] = []

        for direction, candidate_cutoff in (("tighten", int(deprivation_cutoffs[dim_index]) - 1), ("relax", int(deprivation_cutoffs[dim_index]) + 1)):
            if candidate_cutoff < 1 or candidate_cutoff >= len(category_orders[dim_index]):
                continue
            trial_cutoffs = deprivation_cutoffs.copy()
            trial_cutoffs[dim_index] = candidate_cutoff
            trial_lookups = _build_delta_lookups(
                category_orders=category_orders,
                deprivation_cutoffs=trial_cutoffs,
                threshold_weights=threshold_weights,
            )
            trial_core = _compute_ordinal_core(
                rank_matrix=rank_matrix,
                weights=weights,
                deprivation_cutoffs=trial_cutoffs,
                delta_lookups=trial_lookups,
                k_threshold=k_threshold,
                beta=beta,
            )
            delta_q = abs(float(trial_core["ordinal_adjusted_headcount_q"]) - baseline_q)
            flip_share = float(np.mean(np.asarray(trial_core["poor_mask"], dtype=bool) != baseline_poor))
            neighbors.append(
                {
                    "direction": direction,
                    "candidate_cutoff": int(candidate_cutoff),
                    "delta_q": float(delta_q),
                    "flip_share": flip_share,
                    "ordinal_adjusted_headcount_q": float(trial_core["ordinal_adjusted_headcount_q"]),
                    "headcount_h": float(trial_core["headcount_h"]),
                    "ordinal_intensity_a": float(trial_core["ordinal_intensity_a"]),
                    "local_upper_bound": upper_bound,
                }
            )

        max_slope = max((entry["delta_q"] for entry in neighbors), default=0.0)
        max_flip = max((entry["flip_share"] for entry in neighbors), default=0.0)
        local_slopes[name] = float(max_slope)
        flip_shares[name] = float(max_flip)
        local_upper_bounds[name] = upper_bound
        per_dimension[name] = {
            "dimension_index": dim_index,
            "current_cutoff": int(deprivation_cutoffs[dim_index]),
            "category_count": len(category_orders[dim_index]),
            "near_poor_margin_share": margin_share,
            "local_upper_bound": upper_bound,
            "max_local_delta_q": float(max_slope),
            "max_flip_share": float(max_flip),
            "status": _diagnostic_status(slope=float(max_slope), flip_share=float(max_flip)),
            "neighbors": neighbors,
        }

    grid_size = int(np.prod([len(candidates) for candidates in cutoff_grid], dtype=np.int64))
    grid_summary: dict[str, Any]
    if grid_size > max_cutoff_grid_size:
        grid_summary = {
            "evaluated": False,
            "reason": "candidate cutoff grid exceeds max_cutoff_grid_size",
            "grid_size": grid_size,
            "max_cutoff_grid_size": int(max_cutoff_grid_size),
        }
    else:
        evaluations: dict[tuple[int, ...], dict[str, Any]] = {}
        for candidate_vector in product(*cutoff_grid):
            candidate_cutoffs = np.asarray(candidate_vector, dtype=int)
            candidate_lookups = _build_delta_lookups(
                category_orders=category_orders,
                deprivation_cutoffs=candidate_cutoffs,
                threshold_weights=threshold_weights,
            )
            candidate_core = _compute_ordinal_core(
                rank_matrix=rank_matrix,
                weights=weights,
                deprivation_cutoffs=candidate_cutoffs,
                delta_lookups=candidate_lookups,
                k_threshold=k_threshold,
                beta=beta,
            )
            evaluations[tuple(int(value) for value in candidate_cutoffs.tolist())] = {
                "headcount_h": float(candidate_core["headcount_h"]),
                "ordinal_intensity_a": float(candidate_core["ordinal_intensity_a"]),
                "ordinal_adjusted_headcount_q": float(candidate_core["ordinal_adjusted_headcount_q"]),
                "poor_mask": np.asarray(candidate_core["poor_mask"], dtype=bool),
            }

        rows: list[dict[str, Any]] = []
        current_vector = tuple(int(value) for value in deprivation_cutoffs.tolist())
        for vector, payload in evaluations.items():
            neighbors: list[tuple[int, ...]] = []
            for dim_index in range(n_dims):
                for direction in (-1, 1):
                    candidate = list(vector)
                    candidate[dim_index] += direction
                    candidate_tuple = tuple(candidate)
                    if candidate_tuple in evaluations:
                        neighbors.append(candidate_tuple)
            slope = max(
                (
                    abs(payload["ordinal_adjusted_headcount_q"] - evaluations[neighbor]["ordinal_adjusted_headcount_q"])
                    for neighbor in neighbors
                ),
                default=0.0,
            )
            instability = max(
                (
                    float(np.mean(payload["poor_mask"] != evaluations[neighbor]["poor_mask"]))
                    for neighbor in neighbors
                ),
                default=0.0,
            )
            rows.append(
                {
                    "cutoffs": list(vector),
                    "headcount_h": float(payload["headcount_h"]),
                    "ordinal_intensity_a": float(payload["ordinal_intensity_a"]),
                    "ordinal_adjusted_headcount_q": float(payload["ordinal_adjusted_headcount_q"]),
                    "slope": float(slope),
                    "flip_share": float(instability),
                    "status": _diagnostic_status(slope=float(slope), flip_share=float(instability)),
                    "is_current": vector == current_vector,
                }
            )

        rows.sort(key=lambda row: (row["slope"], row["flip_share"], row["cutoffs"]))
        preferred = [row["cutoffs"] for row in rows if row["status"] == "green"]
        if not preferred:
            preferred = [row["cutoffs"] for row in rows if row["status"] == "yellow"]
        if not preferred:
            preferred = [list(current_vector)]

        current_row = next(row for row in rows if row["is_current"])
        grid_summary = {
            "evaluated": True,
            "grid_size": grid_size,
            "candidate_grid": [list(candidates) for candidates in cutoff_grid],
            "current_cutoffs": list(current_vector),
            "current_slope": float(current_row["slope"]),
            "current_flip_share": float(current_row["flip_share"]),
            "preferred_cutoff_plateau": preferred,
            "evaluations": rows,
        }

    return {
        "recoding_invariance_bound": 0.0,
        "current_cutoffs": deprivation_cutoffs.tolist(),
        "local_slopes": local_slopes,
        "flip_shares": flip_shares,
        "local_upper_bounds": local_upper_bounds,
        "per_dimension": per_dimension,
        "grid_summary": grid_summary,
        "preferred_cutoff_plateau": (
            grid_summary.get("preferred_cutoff_plateau", [deprivation_cutoffs.tolist()])
            if isinstance(grid_summary, dict)
            else [deprivation_cutoffs.tolist()]
        ),
    }


def _coerce_recoding_scenarios(
    raw_scenarios: Any,
    *,
    category_orders: tuple[tuple[tuple[str, Any], ...], ...],
) -> tuple[dict[str, Any], ...]:
    if raw_scenarios is None:
        return ()
    if not isinstance(raw_scenarios, Sequence) or isinstance(raw_scenarios, (str, bytes)):
        raise TypeError("comparator_recodings must be a sequence of recoding scenarios")

    scenarios: list[dict[str, Any]] = []
    for scenario_index, raw_scenario in enumerate(raw_scenarios):
        if isinstance(raw_scenario, Mapping):
            name = str(raw_scenario.get("name", f"recoding_{scenario_index}"))
            raw_orders = raw_scenario.get("category_orders")
        else:
            name = f"recoding_{scenario_index}"
            raw_orders = raw_scenario
        scenario_orders = _coerce_numeric_category_orders(raw_orders, n_dims=len(category_orders))
        for dim_index, (baseline_order, scenario_order) in enumerate(zip(category_orders, scenario_orders, strict=True)):
            if len(baseline_order) != len(scenario_order):
                raise ValueError(
                    f"comparator_recodings[{scenario_index}] dimension {dim_index} "
                    "must preserve the number of categories"
                )
        scenarios.append({"name": name, "category_orders": scenario_orders})
    return tuple(scenarios)


def _compute_legacy_gap_q(
    *,
    rank_matrix: np.ndarray,
    weights: np.ndarray,
    deprivation_cutoffs: np.ndarray,
    poor_mask: np.ndarray,
    numeric_orders: tuple[tuple[float, ...], ...],
) -> float:
    gap_columns: list[np.ndarray] = []
    for dim_index, numeric_order in enumerate(numeric_orders):
        numeric_codes = np.asarray(numeric_order, dtype=float)
        cutoff_code = float(numeric_codes[int(deprivation_cutoffs[dim_index])])
        if cutoff_code <= 0.0:
            raise ValueError(
                "legacy numeric-gap comparator requires strictly positive cutoff codes"
            )
        realized_codes = numeric_codes[rank_matrix[:, dim_index] - 1]
        gap_columns.append(np.clip((cutoff_code - realized_codes) / cutoff_code, 0.0, None))
    gap_matrix = np.column_stack(gap_columns)
    gap_scores = gap_matrix @ weights
    return float(np.mean(gap_scores * poor_mask.astype(float)))


def _build_legacy_gap_envelope(
    *,
    rank_matrix: np.ndarray,
    weights: np.ndarray,
    deprivation_cutoffs: np.ndarray,
    poor_mask: np.ndarray,
    category_orders: tuple[tuple[float, ...], ...],
    comparator_recodings: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    scenarios = (
        {
            "name": "baseline",
            "category_orders": tuple(
                tuple(float(index) for index in range(1, len(order) + 1))
                for order in category_orders
            ),
        },
        *comparator_recodings,
    )
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        q_gap = _compute_legacy_gap_q(
            rank_matrix=rank_matrix,
            weights=weights,
            deprivation_cutoffs=deprivation_cutoffs,
            poor_mask=poor_mask,
            numeric_orders=scenario["category_orders"],
        )
        rows.append({"name": scenario["name"], "ordinal_adjusted_gap_q": float(q_gap)})

    values = np.asarray([row["ordinal_adjusted_gap_q"] for row in rows], dtype=float)
    baseline_value = next(row["ordinal_adjusted_gap_q"] for row in rows if row["name"] == "baseline")
    return {
        "baseline_q_gap": float(baseline_value),
        "q_gap_min": float(np.min(values)),
        "q_gap_max": float(np.max(values)),
        "envelope_width": float(np.max(values) - np.min(values)),
        "scenarios": rows,
    }


@foundry_method(
    namespace="distributional.poverty",
    version="1.0.0",
    tags={"distributional", "poverty", "multidimensional", "alkire-foster", "cross-section"},
)
class MultidimensionalPovertyEstimator:
    """Estimate multidimensional poverty when policy runs combine several deprivation indicators."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multidimensional",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "deprivation_matrix",
                    SlotType.MATRIX,
                    Unit("deprivation", "binary"),
                    shape=("n_agents", "n_dimensions"),
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "proportion"),
                    shape=("n_dimensions",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="k_threshold", default=0.33, bounds=(0.0, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Alkire-Foster multidimensional poverty index (MPI): H * A = M0.",
        tags=frozenset({"distributional", "poverty", "multidimensional", "alkire-foster", "cross-section"}),
        when_to_use="Multidimensional poverty measurement across health, education, living standards; UNDP MPI-style analysis",
        output_interpretation="M0 = H * A: headcount ratio times average intensity. Higher = more multidimensional poverty. Policy improves if post-policy M0 decreases.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide deprivation_matrix and weights")
        deprivation_matrix = np.asarray(state["deprivation_matrix"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        if deprivation_matrix.ndim != 2:
            raise ValueError("deprivation_matrix must be 2D (n_agents x n_dimensions)")
        n_agents, n_dims = deprivation_matrix.shape
        if n_agents == 0:
            raise ValueError("deprivation_matrix must not be empty")

        k_threshold = float(params.get("k_threshold", 0.33))

        # Normalize weights to sum to 1
        w = _normalize_weights(weights, expected_dims=n_dims)

        # Weighted deprivation score per agent
        deprivation_scores = deprivation_matrix @ w  # shape: (n_agents,)

        # Identify poor: those whose weighted deprivation score >= k
        is_poor = deprivation_scores >= (k_threshold - 1.0e-9)

        # Headcount ratio H
        headcount = float(np.mean(is_poor))

        # Intensity A: average deprivation score among the poor
        if np.any(is_poor):
            intensity = float(np.mean(deprivation_scores[is_poor]))
        else:
            intensity = 0.0

        # Adjusted headcount M0 = H * A
        m0 = headcount * intensity

        return {
            "result": {
                "m0": m0,
                "headcount_ratio": headcount,
                "intensity": intensity,
                "k_threshold": k_threshold,
                "n_agents": n_agents,
                "n_dimensions": n_dims,
                "n_poor": int(np.sum(is_poor)),
            }
        }


@foundry_method(
    namespace="distributional.poverty",
    version="1.0.0",
    tags={
        "distributional",
        "poverty",
        "multidimensional",
        "alkire-foster",
        "ordinal",
        "cross-section",
    },
)
class OrdinalMultidimensionalPovertyEstimator:
    """Estimate an ordinal-recoding-invariant AF-style poverty index family (ORAF)."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ordinal_multidimensional",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "category_matrix",
                    SlotType.MATRIX,
                    Unit("category", "ordinal"),
                    shape=("n_agents", "n_dimensions"),
                ),
                SlotSpec(
                    "weights",
                    SlotType.VECTOR,
                    Unit("weight", "proportion"),
                    shape=("n_dimensions",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="category_orders", default=None, is_static=True),
            ParameterSpec(name="deprivation_cutoffs", default=None, is_static=True),
            ParameterSpec(name="k_threshold", default=0.33, bounds=(0.0, 1.0)),
            ParameterSpec(name="beta", default=1.0, bounds=(1.0, None)),
            ParameterSpec(name="threshold_weights", default="equal", is_static=True),
            ParameterSpec(name="dimension_names", default=None, is_static=True),
            ParameterSpec(name="return_censored_scores", default=True),
            ParameterSpec(name="return_dimension_contributions", default=True),
            ParameterSpec(name="return_cutoff_diagnostics", default=True),
            ParameterSpec(name="cutoff_grid", default=None, is_static=True),
            ParameterSpec(name="max_cutoff_grid_size", default=256, bounds=(1, None)),
            ParameterSpec(name="comparator_recodings", default=None, is_static=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Ordinal-recoding-invariant Alkire-Foster family (ORAF) for multidimensional poverty, "
            "with optional cutoff sensitivity diagnostics and legacy numeric-gap envelope."
        ),
        tags=frozenset(
            {
                "distributional",
                "poverty",
                "multidimensional",
                "alkire-foster",
                "ordinal",
                "cross-section",
            }
        ),
        when_to_use=(
            "Ordinal health/education/housing dimensions where deprivation depth should remain "
            "invariant to monotone relabeling of categories."
        ),
        output_interpretation=(
            "Returns H, A_ord, and Q_ord along with optional AF M0 baseline, dimension "
            "contributions (beta=1), cutoff sensitivity diagnostics, and legacy gap envelope."
        ),
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("state must provide category_matrix and weights")

        category_matrix = np.asarray(state["category_matrix"], dtype=object)
        weights = np.asarray(state["weights"], dtype=float)

        if category_matrix.ndim != 2:
            raise ValueError("category_matrix must be 2D (n_agents x n_dimensions)")
        n_agents, n_dims = category_matrix.shape
        if n_agents == 0:
            raise ValueError("category_matrix must not be empty")

        category_orders = _coerce_category_orders(params.get("category_orders"), n_dims=n_dims)
        deprivation_cutoffs = _coerce_int_vector(
            params.get("deprivation_cutoffs"),
            name="deprivation_cutoffs",
            expected_dims=n_dims,
        )
        for dim_index, (cutoff, order) in enumerate(zip(deprivation_cutoffs, category_orders, strict=True)):
            if cutoff < 1 or cutoff >= len(order):
                raise ValueError(
                    f"deprivation_cutoffs[{dim_index}] must fall in [1, {len(order) - 1}]"
                )

        k_threshold = float(params.get("k_threshold", 0.33))
        if not np.isfinite(k_threshold) or not (0.0 <= k_threshold <= 1.0):
            raise ValueError("k_threshold must be finite and lie in [0, 1]")
        beta = _coerce_beta(params.get("beta", 1.0))
        threshold_weights = _resolve_threshold_weights(
            params.get("threshold_weights", "equal"),
            category_orders=category_orders,
            deprivation_cutoffs=deprivation_cutoffs,
        )
        dimension_names = _coerce_dimension_names(params.get("dimension_names"), n_dims=n_dims)
        return_censored_scores = _coerce_bool(params.get("return_censored_scores"), default=True)
        return_dimension_contributions = _coerce_bool(
            params.get("return_dimension_contributions"), default=True
        )
        return_cutoff_diagnostics = _coerce_bool(
            params.get("return_cutoff_diagnostics"), default=True
        )
        max_cutoff_grid_size = int(params.get("max_cutoff_grid_size", 256))
        if max_cutoff_grid_size < 1:
            raise ValueError("max_cutoff_grid_size must be >= 1")

        weights = _normalize_weights(weights, expected_dims=n_dims)
        rank_matrix = _map_category_matrix_to_ranks(
            category_matrix,
            category_orders=category_orders,
        )
        delta_lookups = _build_delta_lookups(
            category_orders=category_orders,
            deprivation_cutoffs=deprivation_cutoffs,
            threshold_weights=threshold_weights,
        )
        core = _compute_ordinal_core(
            rank_matrix=rank_matrix,
            weights=weights,
            deprivation_cutoffs=deprivation_cutoffs,
            delta_lookups=delta_lookups,
            k_threshold=k_threshold,
            beta=beta,
        )

        result: dict[str, Any] = {
            "headcount_h": float(core["headcount_h"]),
            "ordinal_intensity_a": float(core["ordinal_intensity_a"]),
            "ordinal_adjusted_headcount_q": float(core["ordinal_adjusted_headcount_q"]),
            "af_m0_baseline": float(core["af_m0"]),
            "beta": beta,
            "k_threshold": k_threshold,
            "n_agents": n_agents,
            "n_dimensions": n_dims,
            "n_poor": int(np.sum(np.asarray(core["poor_mask"], dtype=bool))),
            "dimension_weights": weights.tolist(),
            "deprivation_cutoffs": deprivation_cutoffs.tolist(),
            "dimension_names": list(dimension_names),
            "threshold_weights_basis": (
                "equal"
                if params.get("threshold_weights", "equal") in (None, "equal")
                else "af_last"
                if params.get("threshold_weights") == "af_last"
                else "custom"
            ),
        }

        if return_dimension_contributions:
            result["dimension_contributions"] = _build_dimension_contributions(
                core=core,
                weights=weights,
                dimension_names=dimension_names,
                beta=beta,
            )

        if return_censored_scores:
            result["poor_mask"] = np.asarray(core["poor_mask"], dtype=int).tolist()
            result["breadth_scores"] = np.asarray(core["breadth_scores"], dtype=float).tolist()
            result["severity_scores"] = np.asarray(core["severity_scores"], dtype=float).tolist()
            result["censored_scores"] = np.asarray(core["censored_scores"], dtype=float).tolist()

        if return_cutoff_diagnostics:
            cutoff_grid = _coerce_cutoff_grid(
                params.get("cutoff_grid"),
                deprivation_cutoffs=deprivation_cutoffs,
                category_orders=category_orders,
            )
            result["cutoff_diagnostics"] = _build_cutoff_diagnostics(
                rank_matrix=rank_matrix,
                weights=weights,
                category_orders=category_orders,
                deprivation_cutoffs=deprivation_cutoffs,
                threshold_weights=threshold_weights,
                k_threshold=k_threshold,
                beta=beta,
                baseline_core=core,
                dimension_names=dimension_names,
                cutoff_grid=cutoff_grid,
                max_cutoff_grid_size=max_cutoff_grid_size,
            )

        comparator_recodings = _coerce_recoding_scenarios(
            params.get("comparator_recodings"),
            category_orders=category_orders,
        )
        if comparator_recodings:
            result["legacy_gap_envelope"] = _build_legacy_gap_envelope(
                rank_matrix=rank_matrix,
                weights=weights,
                deprivation_cutoffs=deprivation_cutoffs,
                poor_mask=np.asarray(core["poor_mask"], dtype=bool),
                category_orders=category_orders,
                comparator_recodings=comparator_recodings,
            )

        return {"result": result}


__all__ = [
    "MultidimensionalPovertyEstimator",
    "OrdinalMultidimensionalPovertyEstimator",
]
