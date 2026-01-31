"""Row filtering transform."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from polisyos.fabric.connectors.transform.pipeline import (
    CopyPolicy,
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)

__all__ = ["FilterTransform"]


@dataclass
class FilterTransform(DataTransform):
    """Filter rows based on a boolean condition or predicate."""

    condition: str | Callable[[pd.DataFrame], pd.Series]
    keep: bool = True
    max_drop_pct: float = 0.9

    @property
    def name(self) -> str:
        return "filter"

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        start_time = datetime.now(timezone.utc)
        copy_policy = context.effective_copy_policy()

        if isinstance(self.condition, str):
            try:
                mask = data.eval(self.condition)
            except Exception as exc:
                raise TransformError(
                    f"Filter condition failed: {self.condition}: {exc}"
                ) from exc
        else:
            try:
                mask = self.condition(data)
            except Exception as exc:
                raise TransformError(f"Filter predicate failed: {exc}") from exc

        if not isinstance(mask, pd.Series):
            raise TransformError("Filter predicate must return a pandas Series")

        if self.keep:
            result = data[mask]
        else:
            result = data[~mask]

        if copy_policy == CopyPolicy.COPY:
            result = result.copy()

        dropped = len(data) - len(result)
        drop_pct = dropped / len(data) if len(data) else 0.0
        warnings: list[str] = []
        if drop_pct > self.max_drop_pct:
            warnings.append(
                f"Filter dropped {drop_pct:.1%} of rows (>{self.max_drop_pct:.1%})"
            )

        lineage = TransformLineage(
            stage_name=self.name,
            started_at=start_time,
            completed_at=datetime.now(timezone.utc),
            input_row_count=len(data),
            output_row_count=len(result),
            parameters={
                "condition": self.condition if isinstance(self.condition, str) else "<callable>",
                "keep": self.keep,
                "dropped_rows": dropped,
                "drop_pct": drop_pct,
            },
        )

        return result, lineage, warnings
