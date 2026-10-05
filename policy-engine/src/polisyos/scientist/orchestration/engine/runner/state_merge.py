"""State merge for distributed runner tier results."""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.runner.serialization import (
    NativeNodeOutcomeBatch,
    deserialize_outcome_batch,
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
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


class TierOutcomeAdmissionError(ValueError):
    """A worker returned an outcome outside the requested execution tier."""

    code = "distributed_tier_result_alias_outside_requested_tier"

    def __init__(self, unexpected_aliases: Collection[str]) -> None:
        self.unexpected_aliases = tuple(sorted(set(unexpected_aliases)))
        super().__init__(self.code)


def validate_tier_result_aliases(
    *,
    requested_aliases: Collection[str],
    result_aliases: Collection[str],
) -> None:
    """Reject worker results not owned by this tier before state can be merged."""
    unexpected = set(result_aliases) - set(requested_aliases)
    if unexpected:
        raise TierOutcomeAdmissionError(unexpected)


@dataclass(frozen=True)
class TierOutcomeMergeResult:
    """Merged state and typed worker outcomes for one distributed tier."""

    state_bytes: bytes
    node_outcomes: dict[str, NodeOutcome]
    status_evidence: NativeNodeOutcomeBatch


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

    return _serialize_merged_state(merged.state)


def merge_tier_outcomes(
    base_state_bytes: bytes,
    outcome_bytes_by_alias: dict[str, bytes],
    *,
    requested_aliases: Collection[str],
    write_specs: dict[str, list[str]] | None = None,
    conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
) -> TierOutcomeMergeResult:
    """Merge only successful typed outcomes while retaining every native status."""

    validate_tier_result_aliases(
        requested_aliases=requested_aliases,
        result_aliases=outcome_bytes_by_alias,
    )
    base_state = deserialize_state(base_state_bytes)
    status_evidence = deserialize_outcome_batch(outcome_bytes_by_alias)
    outcomes = status_evidence.outcomes
    successful = status_evidence.successful_outcomes
    if not successful:
        return TierOutcomeMergeResult(
            state_bytes=base_state_bytes,
            node_outcomes=outcomes,
            status_evidence=status_evidence,
        )

    resolved_write_specs = {
        alias: list((write_specs or {}).get(alias, _DEFAULT_WRITE_FIELDS))
        for alias in successful
    }
    merged = merge_parallel_outcomes(
        base_state,
        successful,
        resolved_write_specs,
        conflict_policy=conflict_policy,
    )
    alias_to_index = {alias: index for index, alias in enumerate(successful)}
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

    return TierOutcomeMergeResult(
        state_bytes=_serialize_merged_state(merged.state),
        node_outcomes=outcomes,
        status_evidence=status_evidence,
    )


def _serialize_merged_state(state: ExperimentState) -> bytes:
    """Strip branch-local mutation-journal subtype before using the wire codec."""

    serializable_state = ExperimentState.model_validate(
        state.model_dump(mode="python", by_alias=True, exclude_none=False)
    )
    return serialize_state(serializable_state)


__all__ = [
    "StateMergeConflictError",
    "TierOutcomeAdmissionError",
    "TierOutcomeMergeResult",
    "merge_tier_outcomes",
    "merge_tier_states",
    "validate_tier_result_aliases",
]
