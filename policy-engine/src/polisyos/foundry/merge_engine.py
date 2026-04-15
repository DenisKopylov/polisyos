"""
CRDT-inspired Merge Engine for deterministic StateDelta application.

This module provides the single source of truth for all merge operations,
eliminating duplicated logic in executor.py, patch_vm.py, pure_executor.py,
and flow_nodes.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

import jax.numpy as jnp
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.kernel import (
    MergeRuleKind,
    MergeRuleRegistry,
    MergeRuleSpec,
    SlotRegistry,
    SlotSpec,
)
from polisyos.ir.kernel.merge_rules import ConflictResolution


class MergeConflictKind(str, Enum):
    """Classification of merge conflicts."""

    MULTIPLE_WRITERS = "multiple_writers"
    TYPE_MISMATCH = "type_mismatch"
    MISSING_PRIORITY = "missing_priority"
    MISSING_VALUE = "missing_value"
    UNSUPPORTED_RULE = "unsupported_rule"


@dataclass(frozen=True)
class MergeConflict:
    """Immutable record of a merge conflict."""

    slot_id: str
    kind: MergeConflictKind
    writers: tuple[str, ...]
    values: tuple[Any, ...]
    message: str

    def __str__(self) -> str:
        return f"MergeConflict[{self.slot_id}]: {self.message} (writers: {', '.join(self.writers)})"


@dataclass
class MergeRecord:
    """A single write operation to be merged."""

    node_id: str
    slot_id: str
    value: Any | None = None
    delta: Any | None = None
    priority: int | None = None
    timestamp: int | None = None
    active: jnp.ndarray | None = None
    rank: int | None = None


@dataclass
class MergeReport:
    """Report of a merge operation."""

    merged_values: dict[str, Any] = field(default_factory=dict)
    conflicts: list[MergeConflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.conflicts) == 0

    def raise_if_conflicts(self) -> None:
        if self.conflicts:
            msgs = [str(conflict) for conflict in self.conflicts]
            raise MergeConflictError(
                f"{len(self.conflicts)} merge conflict(s):\n" + "\n".join(msgs),
                conflicts=self.conflicts,
            )


class MergeConflictError(Exception):
    """Raised when merge conflicts cannot be resolved."""

    def __init__(self, message: str, conflicts: list[MergeConflict]):
        super().__init__(message)
        self.conflicts = conflicts


class MergeEngine:
    """CRDT-inspired merge engine for deterministic state updates."""

    def __init__(
        self,
        slot_registry: SlotRegistry,
        merge_registry: MergeRuleRegistry,
        *,
        strict_mode: bool = True,
        default_rule_id: str | None = None,
    ):
        self.slot_registry = slot_registry
        self.merge_registry = merge_registry
        self.strict_mode = strict_mode
        self.default_rule_id = default_rule_id or "error"

        if not strict_mode and self.default_rule_id not in merge_registry.rules:
            raise ValueError(f"Default merge rule '{self.default_rule_id}' not in registry")

    def merge_records(
        self,
        records: Sequence[MergeRecord],
        base_values: Mapping[str, Any] | None = None,
    ) -> MergeReport:
        report = MergeReport()
        base_values = base_values or {}

        records_by_slot: dict[str, list[MergeRecord]] = {}
        for record in records:
            records_by_slot.setdefault(record.slot_id, []).append(record)

        report.statistics["total_records"] = len(records)
        report.statistics["unique_slots"] = len(records_by_slot)

        for slot_id, slot_records in sorted(records_by_slot.items()):
            try:
                merged = self._merge_slot(
                    slot_id,
                    slot_records,
                    base_values.get(slot_id),
                    report,
                )
                report.merged_values[slot_id] = merged
            except (TypeError, ValueError) as exc:
                report.conflicts.append(
                    MergeConflict(
                        slot_id=slot_id,
                        kind=_classify_merge_exception(exc),
                        writers=tuple(record.node_id for record in slot_records),
                        values=tuple(_record_payload_value(record) for record in slot_records),
                        message=str(exc),
                    )
                )

        return report

    def _merge_slot(
        self,
        slot_id: str,
        records: list[MergeRecord],
        base_value: Any | None,
        report: MergeReport,
    ) -> Any:
        slot_spec = self.slot_registry.slots.get(slot_id)
        if slot_spec is None:
            if self.strict_mode:
                raise ValueError(f"Unknown slot: {slot_id}")
            rule_id = self.default_rule_id
        else:
            rule_id = slot_spec.merge_rule.rule_id

        rule = self.merge_registry.rules.get(rule_id)
        if rule is None:
            raise ValueError(f"Unknown merge rule '{rule_id}' for slot '{slot_id}'")

        if slot_spec is not None:
            rule = self._apply_override(rule, slot_spec)
            self._validate_slot_type(slot_id, slot_spec, rule)

        handler = self._get_handler(rule.kind)
        return handler(slot_id, records, base_value, rule, report)

    def _apply_override(self, rule: MergeRuleSpec, slot_spec: SlotSpec) -> MergeRuleSpec:
        override = slot_spec.merge_override
        if override is None:
            return rule
        updates: dict[str, Any] = {}
        if override.conflict_resolution is not None:
            updates["conflict_resolution"] = override.conflict_resolution
        if override.default_priority is not None:
            updates["default_priority"] = override.default_priority
        return rule.model_copy(update=updates) if updates else rule

    def _validate_slot_type(self, slot_id: str, slot_spec: SlotSpec, rule: MergeRuleSpec) -> None:
        if not rule.allowed_value_types:
            return
        slot_type = slot_spec.value_type.value
        if slot_type not in rule.allowed_value_types:
            raise ValueError(
                f"Slot '{slot_id}' value_type '{slot_type}' "
                f"not allowed for merge rule '{rule.rule_id}'"
            )

    def _get_handler(self, kind: MergeRuleKind) -> Callable:
        handlers = {
            MergeRuleKind.SUM: self._merge_sum,
            MergeRuleKind.OVERRIDE: self._merge_override,
            MergeRuleKind.PRIORITY: self._merge_priority,
            MergeRuleKind.ERROR: self._merge_error,
        }
        handler = handlers.get(kind)
        if handler is None:
            raise ValueError(f"Unsupported merge rule kind: {kind}")
        return handler

    def _merge_sum(
        self,
        slot_id: str,
        records: list[MergeRecord],
        base_value: Any | None,
        rule: MergeRuleSpec,
        report: MergeReport,
    ) -> Any:
        total_delta = None
        for record in records:
            delta = record.delta
            if delta is None:
                if record.value is not None and base_value is not None:
                    delta = record.value - base_value
                else:
                    raise ValueError(
                        f"SUM merge requires 'delta' for slot '{slot_id}' from '{record.node_id}'"
                    )
            total_delta = delta if total_delta is None else total_delta + delta

        if base_value is None:
            return total_delta if total_delta is not None else 0
        return base_value + (total_delta if total_delta is not None else 0)

    def _merge_override(
        self,
        slot_id: str,
        records: list[MergeRecord],
        base_value: Any | None,
        rule: MergeRuleSpec,
        report: MergeReport,
    ) -> Any:
        if not records:
            return base_value

        def sort_key(record: MergeRecord) -> tuple[int, str]:
            ts = record.timestamp if record.timestamp is not None else 0
            return ts, record.node_id

        winner = max(records, key=sort_key)
        value = winner.value
        if value is None:
            raise ValueError(
                f"OVERRIDE merge requires 'value' for slot '{slot_id}' from '{winner.node_id}'"
            )
        return value

    def _merge_priority(
        self,
        slot_id: str,
        records: list[MergeRecord],
        base_value: Any | None,
        rule: MergeRuleSpec,
        report: MergeReport,
    ) -> Any:
        if not records:
            return base_value

        missing_priority = [record.node_id for record in records if record.priority is None]
        if missing_priority:
            if rule.default_priority is None:
                raise ValueError(
                    f"PRIORITY merge requires 'priority' for slot '{slot_id}'. "
                    f"Missing from: {', '.join(missing_priority)}"
                )

        def priority(record: MergeRecord) -> int:
            if record.priority is not None:
                return int(record.priority)
            assert rule.default_priority is not None
            return int(rule.default_priority)

        sorted_records = sorted(records, key=lambda record: (-priority(record), record.node_id))
        winner = sorted_records[0]
        value = winner.value
        if value is None:
            raise ValueError(
                f"PRIORITY merge requires 'value' for slot '{slot_id}' from '{winner.node_id}'"
            )
        return value

    def _merge_error(
        self,
        slot_id: str,
        records: list[MergeRecord],
        base_value: Any | None,
        rule: MergeRuleSpec,
        report: MergeReport,
    ) -> Any:
        if len(records) > 1:
            conflict = MergeConflict(
                slot_id=slot_id,
                kind=MergeConflictKind.MULTIPLE_WRITERS,
                writers=tuple(record.node_id for record in records),
                values=tuple(_record_payload_value(record) for record in records),
                message=f"ERROR merge detected {len(records)} concurrent writers",
            )
            report.conflicts.append(conflict)

            if rule.conflict_resolution == ConflictResolution.FIRST:
                sorted_records = sorted(records, key=lambda record: record.node_id)
                return sorted_records[0].value
            if rule.conflict_resolution == ConflictResolution.LAST:
                sorted_records = sorted(records, key=lambda record: record.node_id)
                return sorted_records[-1].value
            return base_value

        if not records:
            return base_value
        value = records[0].value
        if value is None:
            raise ValueError(
                f"ERROR merge requires 'value' for slot '{slot_id}' from '{records[0].node_id}'"
            )
        return value


def _record_payload_value(record: MergeRecord) -> Any:
    """Select the conflict payload without relying on ambiguous array truthiness."""
    if record.value is not None:
        return record.value
    return record.delta


def _classify_merge_exception(exc: TypeError | ValueError) -> MergeConflictKind:
    message = str(exc).lower()
    if "value_type" in message or "not allowed" in message:
        return MergeConflictKind.TYPE_MISMATCH
    if "priority" in message:
        return MergeConflictKind.MISSING_PRIORITY
    if "value" in message or "delta" in message:
        return MergeConflictKind.MISSING_VALUE
    return MergeConflictKind.UNSUPPORTED_RULE


class JAXMergeEngine:
    """JAX-compatible merge engine for differentiable calibration."""

    def __init__(self, slot_registry: SlotRegistry, merge_registry: MergeRuleRegistry):
        self.slot_registry = slot_registry
        self.merge_registry = merge_registry

    def merge_sum_jax(
        self,
        base_value: jnp.ndarray,
        deltas: Sequence[jnp.ndarray],
        masks: Sequence[jnp.ndarray],
    ) -> jnp.ndarray:
        total = jnp.zeros_like(base_value)
        for delta, mask in zip(deltas, masks):
            masked_delta = jnp.where(mask, delta, jnp.zeros_like(delta))
            total = total + masked_delta
        return base_value + total

    def merge_override_jax(
        self,
        base_value: jnp.ndarray,
        values: Sequence[jnp.ndarray],
        ranks: Sequence[jnp.ndarray],
        masks: Sequence[jnp.ndarray],
    ) -> jnp.ndarray:
        best_rank = jnp.array(-1e9)
        result = base_value
        for value, rank, mask in zip(values, ranks, masks):
            better = mask & (rank > best_rank)
            result = jnp.where(better, value, result)
            best_rank = jnp.where(better, rank, best_rank)
        return result

    def merge_priority_jax(
        self,
        base_value: jnp.ndarray,
        values: Sequence[jnp.ndarray],
        priorities: Sequence[jnp.ndarray],
        ranks: Sequence[jnp.ndarray],
        masks: Sequence[jnp.ndarray],
    ) -> jnp.ndarray:
        best_priority = jnp.array(-1e9)
        best_rank = jnp.array(1e9)
        result = base_value
        for value, priority, rank, mask in zip(values, priorities, ranks, masks):
            higher = priority > best_priority
            tie = (priority == best_priority) & (rank < best_rank)
            better = mask & (higher | tie)
            result = jnp.where(better, value, result)
            best_priority = jnp.where(better, priority, best_priority)
            best_rank = jnp.where(better, rank, best_rank)
        return result

    def merge_error_jax(
        self,
        base_value: jnp.ndarray,
        values: Sequence[jnp.ndarray],
        masks: Sequence[jnp.ndarray],
        slot_id: str,
    ) -> jnp.ndarray:
        import equinox as eqx

        active_count = jnp.array(0, dtype=jnp.int32)
        result = base_value
        best_rank = jnp.array(1e9)

        for index, (value, mask) in enumerate(zip(values, masks)):
            is_active = mask
            active_count = active_count + is_active.astype(jnp.int32)
            rank = jnp.array(float(index))
            better = is_active & (rank < best_rank)
            result = jnp.where(better, value, result)
            best_rank = jnp.where(better, rank, best_rank)

        result = eqx.error_if(
            result,
            active_count > 1,
            f"Merge conflict for slot '{slot_id}': multiple concurrent writers",
        )
        return result


class MergeConflictContract(BaseModel):
    """Pydantic contract for serializable merge conflicts."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str
    kind: MergeConflictKind
    writers: list[str]
    message: str


class MergeReportContract(BaseModel):
    """Pydantic contract for serializable merge reports."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    conflicts: list[MergeConflictContract] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    statistics: dict[str, int] = Field(default_factory=dict)
