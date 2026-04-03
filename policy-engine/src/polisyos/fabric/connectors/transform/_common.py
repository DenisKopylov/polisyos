"""Public transform common module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from polisyos.fabric.connectors.transform.pipeline import (
    CopyPolicy,
    TransformContext,
    TransformLineage,
)

__all__ = [
    "resolve_copy_policy",
    "copy_if_needed",
    "stage_started_at",
    "build_lineage",
]


def resolve_copy_policy(context: TransformContext) -> CopyPolicy:
    """Resolve copy policy from transform context."""
    return context.effective_copy_policy()


def copy_if_needed(
    data: pd.DataFrame,
    context: TransformContext,
) -> tuple[pd.DataFrame, CopyPolicy]:
    """Apply transform copy policy and return the resolved policy."""
    copy_policy = resolve_copy_policy(context)
    result = data.copy() if copy_policy == CopyPolicy.COPY else data
    return result, copy_policy


def stage_started_at() -> datetime:
    """Timestamp helper for transform stage execution start."""
    return datetime.now(timezone.utc)


def build_lineage(
    *,
    stage_name: str,
    started_at: datetime,
    input_data: pd.DataFrame,
    output_data: pd.DataFrame,
    parameters: dict[str, Any],
) -> TransformLineage:
    """Construct standard TransformLineage object for a stage."""
    return TransformLineage(
        stage_name=stage_name,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        input_row_count=len(input_data),
        output_row_count=len(output_data),
        parameters=parameters,
    )
