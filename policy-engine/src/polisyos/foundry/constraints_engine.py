from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

from polisyos.core.contracts.foundry import PatchOp
from polisyos.ir.kernel import ConstraintRegistry, SlotRegistry


@dataclass
class ConstraintResult:
    violations: List[str]
    penalty: float | None = None
    repair_patch: list[PatchOp] | None = None
    events: list[dict[str, Any]] | None = None


def check_constraints(
    *,
    constraint_registry: ConstraintRegistry,
    slot_registry: SlotRegistry,
    merged_ops: Iterable[PatchOp],
    state_before,
) -> ConstraintResult:
    """
    Placeholder constraints engine; returns empty violations.
    """
    return ConstraintResult(violations=[], penalty=None, repair_patch=None, events=[])
