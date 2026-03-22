"""Merge results from parallel node executions.

Merges ``NodeOutcome`` results back into a base ``ExperimentState`` by
applying each outcome's writes using the ``state_writes`` declarations
from their ``NodeSpec``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.state import ExperimentState


# Dict-typed fields on ExperimentState that support key-level merging
_DICT_FIELDS = frozenset({"inputs", "artifacts_index", "reports_index", "params"})


@dataclass(frozen=True)
class MergeResult:
    """Result of merging parallel outcomes into a base state."""

    state: ExperimentState
    conflicts: list[str] = field(default_factory=list)


def merge_parallel_outcomes(
    base_state: ExperimentState,
    outcomes: dict[str, NodeOutcome],
    write_specs: dict[str, list[str]],
) -> MergeResult:
    """Merge outcomes from parallel nodes by their ``state_writes`` declarations.

    For dict-typed fields (``params``, ``artifacts_index``, ``reports_index``,
    ``inputs``), merge happens at the key level. A conflict is reported when
    two outcomes write to the same key within the same dict field.

    For scalar fields, later writes (in alias-sorted order) win, and a
    conflict is reported if two outcomes write different values.

    Parameters
    ----------
    base_state:
        The state before the parallel tier began.
    outcomes:
        ``{alias: NodeOutcome}`` — only outcomes with ``status == "ok"``
        should be passed.
    write_specs:
        ``{alias: list_of_state_write_keys}`` — from each node's ``NodeSpec``.
    """
    if not outcomes:
        return MergeResult(state=base_state)

    conflicts: list[str] = []
    update: dict[str, Any] = {}

    # Track which alias wrote to which dict key for conflict detection
    dict_key_owners: dict[str, dict[str, str]] = {}  # field -> {key: alias}

    for alias in sorted(outcomes.keys()):
        outcome = outcomes[alias]
        writes = write_specs.get(alias, [])

        for write_field in writes:
            outcome_val = getattr(outcome.state, write_field, None)
            base_val = getattr(base_state, write_field, None)

            if write_field in _DICT_FIELDS and isinstance(outcome_val, dict):
                # Merge at key level
                if write_field not in update:
                    update[write_field] = dict(base_val) if isinstance(base_val, dict) else {}
                if write_field not in dict_key_owners:
                    dict_key_owners[write_field] = {}

                for key, val in outcome_val.items():
                    # Only merge keys that differ from base
                    base_key_val = base_val.get(key) if isinstance(base_val, dict) else None
                    if val != base_key_val:
                        if key in dict_key_owners[write_field]:
                            prev_alias = dict_key_owners[write_field][key]
                            conflicts.append(
                                f"{write_field}.{key} written by both {prev_alias} and {alias}"
                            )
                        dict_key_owners[write_field][key] = alias
                        update[write_field][key] = val
            else:
                # Scalar field — simple overwrite
                if write_field in update and update[write_field] != outcome_val:
                    conflicts.append(f"{write_field} written by multiple nodes")
                update[write_field] = outcome_val

    if update:
        merged = base_state.model_copy(update=update)
    else:
        merged = base_state

    return MergeResult(state=merged, conflicts=conflicts)
