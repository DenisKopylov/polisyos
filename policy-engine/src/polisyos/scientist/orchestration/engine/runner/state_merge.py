"""State merge for distributed runner tier results."""

from __future__ import annotations

import logging
from typing import Final

from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.state_merge import (
    MergeConflictPolicy,
    merge_parallel_outcomes,
)

_logger = logging.getLogger(__name__)
_DEFAULT_WRITE_FIELDS: Final[tuple[str, ...]] = (
    "artifacts_index",
    "reports_index",
    "params",
    "inputs",
    "budgets",
    "causal_method_params",
)


class StateMergeConflictError(Exception):
    """Two parallel node results modified the same state surface."""

    def __init__(
        self,
        key: str,
        field: str,
        sources: list[int],
        *,
        policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
    ) -> None:
        self.key = key
        self.field = field
        self.sources = sources
        self.policy = policy
        super().__init__(
            f"Merge conflict in {field}[{key!r}] under policy={policy.value}: "
            f"modified by results {sources}"
        )


def merge_tier_states(
    base_state_bytes: bytes,
    node_results: list[bytes] | dict[str, bytes],
    *,
    write_specs: dict[str, list[str]] | None = None,
    conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
) -> bytes:
    """Merge multiple distributed tier states with explicit conflict policy."""

    if len(node_results) == 0:
        return base_state_bytes
    if isinstance(node_results, dict):
        if len(node_results) == 1:
            return next(iter(node_results.values()))
    elif len(node_results) == 1:
        return node_results[0]

    base_state = deserialize_state(base_state_bytes)
    outcomes: dict[str, NodeOutcome] = {}
    resolved_write_specs: dict[str, list[str]] = {}
    alias_to_index: dict[str, int] = {}

    if isinstance(node_results, dict):
        ordered_results = list(node_results.items())
    else:
        ordered_results = [
            (f"tier_result_{index}", result_bytes)
            for index, result_bytes in enumerate(node_results)
        ]

    for index, (alias, result_bytes) in enumerate(ordered_results):
        alias_to_index[alias] = index
        outcomes[alias] = NodeOutcome(status="ok", state=deserialize_state(result_bytes))
        resolved_write_specs[alias] = list((write_specs or {}).get(alias, _DEFAULT_WRITE_FIELDS))

    merged = merge_parallel_outcomes(
        base_state,
        outcomes,
        resolved_write_specs,
        conflict_policy=conflict_policy,
    )
    if merged.conflict_details:
        first = merged.conflict_details[0]
        field, _, key = first.path.partition(".")
        raise StateMergeConflictError(
            key=key or field,
            field=field,
            sources=[alias_to_index[alias] for alias in first.aliases if alias in alias_to_index],
            policy=conflict_policy,
        )

    if merged.resolved_conflicts:
        _logger.warning(
            "Distributed merge resolved %s conflicts with policy=%s",
            len(merged.resolved_conflicts),
            conflict_policy.value,
        )

    return serialize_state(merged.state)


__all__ = [
    "StateMergeConflictError",
    "merge_tier_states",
]
