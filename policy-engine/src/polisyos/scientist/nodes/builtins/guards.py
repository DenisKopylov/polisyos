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
        artifacts = set(state.artifacts_index.keys()) if state.artifacts_index else set()
        params = set(state.params.keys()) if state.params else set()
        available = artifacts | params

        for key in self._reads:
            if key not in available:
                warnings.append(f"state_read '{key}' not found in state")
        return warnings

    def post_check(
        self,
        before: ExperimentState,
        after: ExperimentState,
    ) -> None:
        """Verify that only declared state_writes were mutated.

        Raises ``StateMutationViolation`` if:
        - An artifact key was added that is not in state_writes
        - An existing artifact key was removed
        """
        violations: list[str] = []

        before_keys = set(before.artifacts_index.keys()) if before.artifacts_index else set()
        after_keys = set(after.artifacts_index.keys()) if after.artifacts_index else set()

        # Check for removed keys
        removed = before_keys - after_keys
        if removed:
            violations.append(f"artifacts removed: {sorted(removed)}")

        # Check for undeclared additions
        added = after_keys - before_keys
        undeclared = added - self._writes
        if undeclared:
            violations.append(f"undeclared state_writes: {sorted(undeclared)}")

        if violations:
            raise StateMutationViolation(violations)


__all__ = [
    "StateMutationGuard",
    "StateMutationViolation",
]
