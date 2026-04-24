"""State mutation guards for builtin nodes."""

from __future__ import annotations

from typing import Any

from polisyos.scientist.engine.protocol import NodeSpec
from polisyos.scientist.engine.state import ExperimentState


class StateMutationViolation(Exception):
    """Raised when a node mutates state in a way that violates its spec."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("; ".join(violations))


class StateMutationGuard:
    """Validates that a node respects its declared state_reads/state_writes.

    Usage::

        guard = StateMutationGuard(node.spec)
        warnings = guard.pre_check(state)
        # ... execute node ...
        guard.post_check(state_before, state_after)  # raises on violation
    """

    def __init__(self, spec: NodeSpec) -> None:
        self._reads = set(spec.state_reads)
        self._writes = set(spec.state_writes)

    def pre_check(self, state: ExperimentState) -> list[str]:
        """Check that all declared state_reads are present.

        Returns a list of warning messages for missing reads.
        """
        warnings: list[str] = []
        snapshot = _state_snapshot(state)

        for key in self._reads:
            if not _path_exists(snapshot, key) and not _legacy_state_key_exists(snapshot, key):
                warnings.append(f"state_read '{key}' not found in state")
        return warnings

    def post_check(
        self,
        before: ExperimentState,
        after: ExperimentState,
    ) -> None:
        """Verify that only declared state_writes were mutated.

        Raises ``StateMutationViolation`` if a node mutates state outside its
        declared ``state_writes`` contract.  Historical specs often name
        logical keys (``"causal_graph"``) while newer specs can name explicit
        paths (``"artifacts_index.causal_graph"`` or ``"params.depth"``), so
        both forms are accepted.
        """
        violations: list[str] = []
        before_snapshot = _state_snapshot(before)
        after_snapshot = _state_snapshot(after)

        removed_indexes = _removed_index_paths(before_snapshot, after_snapshot)
        if removed_indexes:
            violations.append(f"state index keys removed: {sorted(removed_indexes)}")

        mutated_paths = sorted(_diff_paths(before_snapshot, after_snapshot))
        undeclared = [
            path
            for path in mutated_paths
            if path not in removed_indexes and not _write_covers_path(self._writes, path)
        ]
        if undeclared:
            violations.append(f"undeclared state_writes: {undeclared}")

        if violations:
            raise StateMutationViolation(violations)


def _state_snapshot(state: ExperimentState) -> dict[str, Any]:
    return state.model_dump(mode="python", by_alias=True, exclude_none=False)


def _split_path(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def _path_exists(snapshot: dict[str, Any], path: str) -> bool:
    cursor: Any = snapshot
    for part in _split_path(path):
        if not isinstance(cursor, dict) or part not in cursor:
            return False
        cursor = cursor[part]
    return True


def _legacy_state_key_exists(snapshot: dict[str, Any], key: str) -> bool:
    if "." in key:
        return False
    for container in ("inputs", "artifacts_index", "reports_index", "params", "budgets"):
        values = snapshot.get(container)
        if isinstance(values, dict) and key in values:
            return True
    return False


def _removed_index_paths(
    before: dict[str, Any],
    after: dict[str, Any],
) -> set[str]:
    removed: set[str] = set()
    for container in ("inputs", "artifacts_index", "reports_index"):
        before_values = before.get(container)
        after_values = after.get(container)
        if not isinstance(before_values, dict):
            continue
        after_keys = set(after_values.keys()) if isinstance(after_values, dict) else set()
        for key in set(before_values) - after_keys:
            removed.add(f"{container}.{key}")
    return removed


def _diff_paths(before: Any, after: Any, prefix: str = "") -> set[str]:
    if before == after:
        return set()
    if isinstance(before, dict) and isinstance(after, dict):
        paths: set[str] = set()
        for key in sorted(set(before) | set(after)):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.add(child_prefix)
                continue
            paths.update(_diff_paths(before[key], after[key], child_prefix))
        return paths
    return {prefix or "$"}


def _write_covers_path(writes: set[str], path: str) -> bool:
    path_parts = _split_path(path)
    for write in writes:
        write_parts = _split_path(write)
        if not write_parts:
            continue
        if _is_prefix(write_parts, path_parts):
            return True
        if _legacy_write_covers_path(write_parts, path_parts):
            return True
    return False


def _legacy_write_covers_path(write_parts: list[str], path_parts: list[str]) -> bool:
    if len(write_parts) != 1 or len(path_parts) < 2:
        return False
    return (
        path_parts[0] in {"inputs", "artifacts_index", "reports_index", "params", "budgets"}
        and path_parts[1] == write_parts[0]
    )


def _is_prefix(prefix: list[str], path: list[str]) -> bool:
    return len(prefix) <= len(path) and path[: len(prefix)] == prefix


__all__ = [
    "StateMutationGuard",
    "StateMutationViolation",
]
