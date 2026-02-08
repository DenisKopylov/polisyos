from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import pandas as pd
import pytest

from polisyos.fabric.world_query import WorldQueryError, WorldQueryRequest, execute_world_query


class _MaskingBackend:
    backend_kind = "postgres"
    placeholder = "%s"

    def __init__(self) -> None:
        self.last_sql = ""

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        del sql, params
        return None

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        del sql, params
        return []

    def fetchdf(self, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        del params
        self.last_sql = sql
        # Simulate backend returning extra columns regardless of projection.
        return pd.DataFrame(
            [{"claim_id": "c1", "confidence": 0.9, "ssn": "123-45-6789"}]
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    @contextmanager
    def tenant_scope(self, tenant_id: str) -> Iterator[None]:
        del tenant_id
        yield

    def close(self) -> None:
        return None


def test_world_query_expands_star_to_allowed_columns() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("*",),
        allowed_columns=("claim_id", "confidence"),
        limit=10,
    )

    frame = execute_world_query(backend, request)

    assert "SELECT claim_id, confidence" in backend.last_sql
    assert list(frame.columns) == ["claim_id", "confidence"]


def test_world_query_rejects_disallowed_column() -> None:
    backend = _MaskingBackend()
    request = WorldQueryRequest(
        table="claims",
        columns=("claim_id", "ssn"),
        allowed_columns=("claim_id",),
        limit=10,
    )

    with pytest.raises(WorldQueryError, match="Unauthorized columns"):
        execute_world_query(backend, request)
