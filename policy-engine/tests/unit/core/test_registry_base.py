from __future__ import annotations

from dataclasses import dataclass

import pytest

from polisyos.core.registry import BaseRegistry, DuplicateDecision


@dataclass(slots=True)
class _Record:
    record_id: str
    value: int


class _RecordRegistry(BaseRegistry[str, _Record]):
    def __init__(self) -> None:
        super().__init__(key_fn=lambda row: row.record_id)
        self.register_events: list[tuple[str, int, int | None]] = []
        self.unregister_events: list[tuple[str, int]] = []
        self.decision = DuplicateDecision.REJECT

    def validate_duplicate(
        self,
        *,
        key: str,
        existing: _Record,
        incoming: _Record,
    ) -> DuplicateDecision:
        return self.decision

    def on_register(
        self,
        *,
        key: str,
        value: _Record,
        replaced: _Record | None,
    ) -> None:
        replaced_value = None if replaced is None else replaced.value
        self.register_events.append((key, value.value, replaced_value))

    def on_unregister(self, *, key: str, value: _Record) -> None:
        self.unregister_events.append((key, value.value))


def test_duplicate_reject_is_default() -> None:
    registry = _RecordRegistry()
    registry.register(_Record(record_id="a", value=1))

    with pytest.raises(ValueError, match="Duplicate registry key"):
        registry.register(_Record(record_id="a", value=2))

    assert registry.get("a") == _Record(record_id="a", value=1)


def test_duplicate_keep_existing_returns_without_overriding() -> None:
    registry = _RecordRegistry()
    registry.decision = DuplicateDecision.KEEP_EXISTING
    registry.register(_Record(record_id="a", value=1))

    key = registry.register(_Record(record_id="a", value=2))

    assert key == "a"
    assert registry.get("a") == _Record(record_id="a", value=1)
    assert registry.register_events == [("a", 1, None)]


def test_duplicate_replace_and_unregister_hooks() -> None:
    registry = _RecordRegistry()
    registry.decision = DuplicateDecision.REPLACE
    registry.register(_Record(record_id="a", value=1))
    registry.register(_Record(record_id="a", value=2))

    removed = registry.unregister("a")

    assert removed == _Record(record_id="a", value=2)
    assert registry.register_events == [("a", 1, None), ("a", 2, 1)]
    assert registry.unregister_events == [("a", 2)]


def test_clear_invokes_unregister_hook_for_all_entries() -> None:
    registry = _RecordRegistry()
    registry.register(_Record(record_id="a", value=1))
    registry.register(_Record(record_id="b", value=2))

    registry.clear()

    assert registry.count == 0
    assert sorted(registry.unregister_events) == [("a", 1), ("b", 2)]
