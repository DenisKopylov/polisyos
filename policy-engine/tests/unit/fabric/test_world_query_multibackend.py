from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pandas as pd
from polisyos.fabric.security import RowAccessPolicy
from polisyos.fabric.world_query import WorldQueryRequest, execute_world_query


class FakeBackend:
    backend_kind = "postgres"
    placeholder = "%s"
    tenant_scope_enforced = True

    def __init__(self) -> None:
        self.last_sql: str = ""
        self.last_params: list[Any] = []

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        return None

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        return []

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        self.last_sql = sql
        self.last_params = list(params or [])
        return pd.DataFrame([{"ok": True}])

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        del tenant_id
        yield

    def close(self) -> None:
        return None


def test_execute_world_query_uses_backend_placeholder() -> None:
    backend = FakeBackend()
    request = WorldQueryRequest(
        table="world_facts",
        columns=("fact_id",),
        where={"subject_id": "subj-1"},
        limit=10,
    )

    df = execute_world_query(backend, request)

    assert not df.empty
    assert "%s" in backend.last_sql
    assert "LIMIT %s" in backend.last_sql
    assert backend.last_params == ["subj-1", 10]


def test_execute_world_query_injects_row_policy_filters() -> None:
    backend = FakeBackend()
    request = WorldQueryRequest(
        table="world_facts",
        columns=("fact_id",),
        where={"subject_id": "subj-1"},
        row_policy=RowAccessPolicy(tenant_id="tenant-a", enforced_filters={"source_id": "wdi"}),
        tenant_column="tenant_id",
        limit=10,
    )

    execute_world_query(backend, request)

    assert "tenant_id = %s" in backend.last_sql
    assert "source_id = %s" in backend.last_sql
    assert backend.last_params == ["subj-1", "wdi", "tenant-a", 10]
