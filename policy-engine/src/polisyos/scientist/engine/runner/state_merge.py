"""State merge for parallel tier results in distributed runners.

When multiple nodes execute in parallel within a tier, each produces a
modified copy of the experiment state.  This module merges those partial
results back into a single consistent state.

Conflict resolution: if two node results modify the same key in ``data``,
``artifacts_index``, or ``reports_index``, a ``StateMergeConflictError``
is raised.
"""

from __future__ import annotations

import logging
from typing import Any

from polisyos.scientist.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)

_logger = logging.getLogger(__name__)


class StateMergeConflictError(Exception):
    """Two parallel node results modified the same state key."""

    def __init__(self, key: str, field: str, sources: list[int]) -> None:
        self.key = key
        self.field = field
        self.sources = sources
        super().__init__(
            f"Merge conflict in {field}[{key!r}]: modified by results {sources}"
        )


def _diff_dict(base: dict[str, Any], modified: dict[str, Any]) -> dict[str, Any]:
    """Return keys that were added or changed relative to *base*."""
    diff: dict[str, Any] = {}
    for k, v in modified.items():
        if k not in base or base[k] != v:
            diff[k] = v
    return diff


def merge_tier_states(
    base_state_bytes: bytes,
    node_results: list[bytes],
) -> bytes:
    """Merge multiple parallel node results into a single state.

    Parameters
    ----------
    base_state_bytes:
        Serialised ``ExperimentState`` before the tier started.
    node_results:
        List of serialised ``ExperimentState`` bytes, one per node in
        the tier.

    Returns
    -------
    bytes
        Serialised merged ``ExperimentState``.

    Raises
    ------
    StateMergeConflictError
        If two results modify the same key within the same dict field.
    """
    if len(node_results) == 0:
        return base_state_bytes
    if len(node_results) == 1:
        return node_results[0]

    base = deserialize_state(base_state_bytes)
    results = [deserialize_state(r) for r in node_results]

    # We merge these mutable dict fields.
    merge_fields = ("artifacts_index", "reports_index", "params", "inputs")

    base_dicts: dict[str, dict[str, Any]] = {}
    for field in merge_fields:
        base_dicts[field] = dict(getattr(base, field, {}) or {})

    # Collect per-field diffs from each result
    all_diffs: dict[str, list[tuple[int, dict[str, Any]]]] = {
        f: [] for f in merge_fields
    }
    for idx, result in enumerate(results):
        for field in merge_fields:
            result_dict = dict(getattr(result, field, {}) or {})
            diff = _diff_dict(base_dicts[field], result_dict)
            if diff:
                all_diffs[field].append((idx, diff))

    # Detect conflicts and build merged dicts
    merged_updates: dict[str, dict[str, Any]] = {}
    for field in merge_fields:
        merged = dict(base_dicts[field])
        seen_keys: dict[str, int] = {}  # key -> first result index

        for idx, diff in all_diffs[field]:
            for key, value in diff.items():
                if key in seen_keys and seen_keys[key] != idx:
                    # Another result already modified this key
                    raise StateMergeConflictError(
                        key=key, field=field, sources=[seen_keys[key], idx]
                    )
                seen_keys[key] = idx
                merged[key] = value

        merged_updates[field] = merged

    # Build merged state: start from last result (inherits scalar fields),
    # then overlay our merged dicts.
    merged_state = results[-1].model_copy(update=merged_updates)

    return serialize_state(merged_state)
