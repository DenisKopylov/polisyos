"""Row filtering transform."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from polisyos.fabric.connectors.transform._common import (
    build_lineage,
    resolve_copy_policy,
    stage_started_at,
)
from polisyos.fabric.connectors.transform.pipeline import (
    CopyPolicy,
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
)

__all__ = ["FilterTransform"]

# Tokens that must NOT appear in a DataFrame.eval() condition string.
# These could enable arbitrary code execution via pandas numexpr backend.
_UNSAFE_PATTERN = re.compile(
    r"(__import__|__class__|__subclasses__|__globals__|__builtins__"
    r"|eval\s*\(|exec\s*\(|compile\s*\(|open\s*\(|os\.|sys\.|subprocess\.)",
    re.IGNORECASE,
)


def _validate_eval_condition(condition: str) -> None:
    """Reject filter conditions containing unsafe tokens."""
    if _UNSAFE_PATTERN.search(condition):
        raise TransformError(
            f"Filter condition contains unsafe token: {condition!r}"
        )


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
        start_time = stage_started_at()
        copy_policy = resolve_copy_policy(context)

        if isinstance(self.condition, str):
            _validate_eval_condition(self.condition)
            try:
                mask = data.eval(self.condition)
            except Exception as exc:
                raise TransformError(f"Filter condition failed: {self.condition}: {exc}") from exc
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
            warnings.append(f"Filter dropped {drop_pct:.1%} of rows (>{self.max_drop_pct:.1%})")

        lineage = build_lineage(
            stage_name=self.name,
            started_at=start_time,
            input_data=data,
            output_data=result,
            parameters={
                "condition": self.condition if isinstance(self.condition, str) else "<callable>",
                "keep": self.keep,
                "dropped_rows": dropped,
                "drop_pct": drop_pct,
            },
        )

        return result, lineage, warnings
