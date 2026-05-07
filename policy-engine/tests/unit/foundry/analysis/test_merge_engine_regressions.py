from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.components.merge_engine import MergeConflictKind, MergeEngine, MergeRecord
from polisyos.ir.kernel import (
    DEFAULT_MERGE_RULE_REGISTRY,
    MergeRuleRef,
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotSpec,
    SlotValueType,
)


def _single_slot_registry(
    *,
    slot_id: str,
    rule_id: str,
    value_type: SlotValueType = SlotValueType.DECIMAL,
) -> SlotRegistry:
    return SlotRegistry(
        slots={
            slot_id: SlotSpec(
                slot_id=slot_id,
                scope=SlotScope.GLOBAL,
                value_type=value_type,
                kind=SlotKind.FLOW,
                merge_rule=MergeRuleRef(rule_id=rule_id),
                state_path=slot_id,
            )
        }
    )


def test_merge_conflict_reporting_does_not_crash_on_array_truthiness() -> None:
    engine = MergeEngine(SlotRegistry(slots={}), DEFAULT_MERGE_RULE_REGISTRY, strict_mode=True)

    report = engine.merge_records(
        [
            MergeRecord(
                node_id="writer",
                slot_id="unknown.slot",
                delta=np.array([1.0, 2.0], dtype=np.float32),
            )
        ]
    )

    assert len(report.conflicts) == 1
    assert report.conflicts[0].slot_id == "unknown.slot"
    assert isinstance(report.conflicts[0].values[0], np.ndarray)


def test_sum_merge_handles_more_than_three_concurrent_writers() -> None:
    slot_id = "test.sum_slot"
    engine = MergeEngine(
        _single_slot_registry(slot_id=slot_id, rule_id="sum"),
        DEFAULT_MERGE_RULE_REGISTRY,
        strict_mode=True,
    )
    records = [
        MergeRecord(node_id=f"writer-{index}", slot_id=slot_id, delta=index)
        for index in range(1, 6)
    ]

    report = engine.merge_records(records, {slot_id: 10})

    assert report.ok
    assert report.merged_values[slot_id] == 25


def test_sum_rule_type_mismatch_is_classified_as_conflict() -> None:
    slot_id = "test.string_sum_slot"
    engine = MergeEngine(
        _single_slot_registry(
            slot_id=slot_id,
            rule_id="sum",
            value_type=SlotValueType.STRING,
        ),
        DEFAULT_MERGE_RULE_REGISTRY,
        strict_mode=True,
    )

    report = engine.merge_records([MergeRecord(node_id="writer", slot_id=slot_id, delta=1)])

    assert len(report.conflicts) == 1
    assert report.conflicts[0].kind == MergeConflictKind.TYPE_MISMATCH
    assert "value_type" in report.conflicts[0].message


def test_priority_default_does_not_mutate_input_records() -> None:
    slot_id = "test.priority_slot"
    engine = MergeEngine(
        _single_slot_registry(slot_id=slot_id, rule_id="priority"),
        DEFAULT_MERGE_RULE_REGISTRY,
        strict_mode=True,
    )
    defaulted_record = MergeRecord(node_id="defaulted", slot_id=slot_id, value=2.0)
    lower_priority_record = MergeRecord(
        node_id="lower",
        slot_id=slot_id,
        value=1.0,
        priority=50,
    )

    report = engine.merge_records([lower_priority_record, defaulted_record])

    assert report.ok
    assert report.merged_values[slot_id] == pytest.approx(2.0)
    assert defaulted_record.priority is None
