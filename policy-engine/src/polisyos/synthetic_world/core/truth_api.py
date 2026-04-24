"""Helpers for selecting and subsetting truth targets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.synthetic_world.models import TruthQuery, json_safe


def _subset_vector_payload(payload: Mapping[str, Any], subset: Mapping[str, Any]) -> dict[str, Any]:
    if not subset:
        return dict(payload)
    coords = payload.get("coords")
    if not isinstance(coords, Mapping):
        return {**payload, "query_subset": dict(subset)}

    coord_arrays = {str(key): list(value) for key, value in coords.items()}
    vector_keys = [
        key
        for key in (
            "values",
            "lower",
            "upper",
            "mean",
            "std",
            "posterior_predictive_mean",
            "posterior_predictive_std",
        )
        if key in payload and isinstance(payload.get(key), (list, tuple))
    ]
    if not vector_keys:
        return {**payload, "query_subset": dict(subset)}

    size = len(list(payload[vector_keys[0]]))
    if any(len(list(coord_values)) != size for coord_values in coord_arrays.values()):
        return {**payload, "query_subset": dict(subset)}
    mask = [True] * size
    for key, wanted in subset.items():
        if key not in coord_arrays:
            continue
        axis_values = coord_arrays[key]
        for idx, axis_value in enumerate(axis_values):
            if mask[idx] and axis_value != wanted:
                mask[idx] = False

    filtered_coords = {
        key: [item for idx, item in enumerate(axis_values) if mask[idx]]
        for key, axis_values in coord_arrays.items()
    }
    filtered_payload = {
        **payload,
        "coords": filtered_coords,
        "query_subset": dict(subset),
    }
    for key in vector_keys:
        filtered_payload[key] = [item for idx, item in enumerate(list(payload[key])) if mask[idx]]
    return {
        **filtered_payload,
    }


def select_truth_targets(
    available: Mapping[str, Mapping[str, Any]],
    query: TruthQuery,
) -> dict[str, dict[str, Any]]:
    """Select and optionally subset truth payloads for a query."""
    if query.targets:
        missing = [target for target in query.targets if target not in available]
        if missing:
            raise KeyError(f"Unknown truth targets requested: {', '.join(sorted(missing))}")
        selected_keys = list(query.targets)
    elif query.prefixes:
        selected_keys = [
            key
            for key in sorted(available)
            if any(key.startswith(prefix) for prefix in query.prefixes)
        ]
    else:
        selected_keys = sorted(available)

    selected: dict[str, dict[str, Any]] = {}
    for key in selected_keys:
        payload = dict(available[key])
        if query.subset:
            payload = _subset_vector_payload(payload, query.subset)
        selected[key] = json_safe(payload)
    return selected


__all__ = ["select_truth_targets"]
