from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest
from polisyos.core.registry.generic import GenericRegistry


@dataclass(slots=True)
class _Record:
    record_id: str
    namespace: str
    tags: list[str]
    active: bool = True


def test_register_get_and_override() -> None:
    registry = GenericRegistry[str, _Record](
        key_fn=lambda row: row.record_id,
        indexers={"namespace": lambda row: row.namespace, "tag": lambda row: row.tags},
    )

    first = _Record(record_id="a", namespace="alpha", tags=["x"])
    registry.register(first)
    assert registry.get("a") == first

    with pytest.raises(ValueError, match="Duplicate registry key"):
        registry.register(first)

    replacement = _Record(record_id="a", namespace="beta", tags=["y"])
    registry.register(replacement, override=True)
    assert registry.get("a") == replacement
    assert registry.find("namespace", "alpha") == []
    assert registry.find("namespace", "beta") == [replacement]


def test_query_find_and_unregister_keep_indices_consistent() -> None:
    registry = GenericRegistry[str, _Record](
        key_fn=lambda row: row.record_id,
        indexers={"namespace": lambda row: row.namespace, "tag": lambda row: row.tags},
    )
    rows = [
        _Record(record_id="a", namespace="alpha", tags=["risk", "core"], active=True),
        _Record(record_id="b", namespace="alpha", tags=["core"], active=False),
        _Record(record_id="c", namespace="beta", tags=["risk"], active=True),
    ]
    for row in rows:
        registry.register(row)

    risk_in_alpha = registry.query(
        index_filters={"namespace": "alpha", "tag": "risk"},
        predicate=lambda row: row.active,
    )
    assert risk_in_alpha == [rows[0]]

    removed = registry.unregister("a")
    assert removed == rows[0]
    assert registry.get("a") is None
    assert registry.find("tag", "risk") == [rows[2]]
    assert registry.find("namespace", "alpha") == [rows[1]]


def test_snapshot_and_require_behaviour() -> None:
    registry = GenericRegistry[str, _Record](key_fn=lambda row: row.record_id)
    row = _Record(record_id="item-1", namespace="default", tags=[])
    registry.register(row)

    snapshot = registry.snapshot()
    assert snapshot.keys == ("item-1",)
    assert snapshot.values == (row,)
    assert snapshot.as_dict() == {"item-1": row}

    assert registry.require("item-1") == row
    with pytest.raises(KeyError):
        registry.require("missing")


def test_thread_safety_concurrent_register_and_get() -> None:
    registry = GenericRegistry[str, _Record](
        key_fn=lambda row: row.record_id,
        indexers={"namespace": lambda row: row.namespace},
    )

    def worker(index: int) -> None:
        record = _Record(
            record_id=f"id-{index}",
            namespace="bulk",
            tags=[f"tag-{index % 5}"],
        )
        registry.register(record)
        loaded = registry.get(record.record_id)
        assert loaded == record

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(worker, range(300)))

    assert registry.count == 300
    assert len(registry.find("namespace", "bulk")) == 300
