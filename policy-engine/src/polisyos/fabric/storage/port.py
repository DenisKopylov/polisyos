"""Public storage port module API."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class StoragePort(Protocol):
    """
    Structural storage interface for Fabric/Scholar consumers.

    Implementations may wrap DuckDB, PostgreSQL, in-memory stores, etc.
    """

    def save_macro(self, data: list[dict[str, Any]]) -> None:
        ...

    def save_agents(self, run_id: str, step: int, agents_state: Any) -> None:
        ...

    def save_run_record(self, record: Any) -> None:
        ...

    def query_table(
        self,
        table: str,
        *,
        columns: Sequence[str] | None = None,
        where: Mapping[str, Any] | None = None,
        order_by: Sequence[str] | None = None,
        limit: int = 1_000,
    ) -> pd.DataFrame:
        ...

    def transaction(self) -> AbstractContextManager["StoragePort"]:
        """Return transactional context manager."""
        ...

    def close(self) -> None:
        ...

