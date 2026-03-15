from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Iterator

import pandas as pd

from .port import StoragePort


class InMemoryStorageAdapter(StoragePort):
    """In-memory StoragePort implementation for fast tests."""

    def __init__(self) -> None:
        self._tables: dict[str, pd.DataFrame] = {}
        self._run_records: list[Any] = []

    def save_macro(self, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        frame = pd.DataFrame(data)
        existing = self._tables.get("macro_history")
        if existing is None:
            self._tables["macro_history"] = frame.reset_index(drop=True)
        else:
            self._tables["macro_history"] = pd.concat([existing, frame], ignore_index=True)

    def save_agents(self, run_id: str, step: int, agents_state: Any) -> None:
        row = {"run_id": run_id, "step": step, "agents_state": agents_state}
        frame = pd.DataFrame([row])
        existing = self._tables.get("agents_snapshot")
        if existing is None:
            self._tables["agents_snapshot"] = frame
        else:
            self._tables["agents_snapshot"] = pd.concat([existing, frame], ignore_index=True)

    def save_run_record(self, record: Any) -> None:
        self._run_records.append(record)

    def query_table(
        self,
        table: str,
        *,
        columns: Sequence[str] | None = None,
        where: Mapping[str, Any] | None = None,
        order_by: Sequence[str] | None = None,
        limit: int = 1_000,
    ) -> pd.DataFrame:
        frame = self._tables.get(table, pd.DataFrame()).copy()
        if where:
            for key, value in where.items():
                if key not in frame.columns:
                    frame = frame.iloc[0:0]
                    break
                frame = frame[frame[key] == value]
        if columns:
            keep = [column for column in columns if column in frame.columns]
            frame = frame[keep] if keep else frame.iloc[0:0]
        if order_by:
            sort_cols: list[str] = []
            ascending: list[bool] = []
            for item in order_by:
                tokens = str(item).strip().split()
                if not tokens:
                    continue
                column = tokens[0]
                direction = tokens[1].upper() if len(tokens) > 1 else "ASC"
                if column not in frame.columns:
                    continue
                sort_cols.append(column)
                ascending.append(direction != "DESC")
            if sort_cols:
                frame = frame.sort_values(sort_cols, ascending=ascending, kind="stable")
        return frame.head(max(limit, 0)).reset_index(drop=True)

    @contextmanager
    def transaction(self) -> Iterator[StoragePort]:
        snapshot_tables = {key: value.copy() for key, value in self._tables.items()}
        snapshot_runs = list(self._run_records)
        try:
            yield self
        except Exception:
            self._tables = snapshot_tables
            self._run_records = snapshot_runs
            raise

    def close(self) -> None:
        self._tables.clear()
        self._run_records.clear()


__all__ = ["InMemoryStorageAdapter"]

