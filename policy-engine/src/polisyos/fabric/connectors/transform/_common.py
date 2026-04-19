"""Public transform common module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from polisyos.core.observability import get_metrics
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


def _default_metrics():
    return get_metrics()


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
    context: TransformContext | None = None,
    metrics: Any | None = None,
) -> TransformLineage:
    """Construct standard TransformLineage object for a stage."""
    lineage = TransformLineage(
        stage_name=stage_name,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        input_row_count=len(input_data),
        output_row_count=len(output_data),
        parameters=parameters,
    )
    if context is not None:
        tracker = context.metadata.get("lineage_tracker")
        if tracker is not None and hasattr(tracker, "record_transform_stage"):
            tracker.record_transform_stage(
                stage_name=stage_name,
                started_at=lineage.started_at,
                completed_at=lineage.completed_at,
                input_columns=[str(col) for col in input_data.columns],
                output_columns=[str(col) for col in output_data.columns],
                parameters=parameters,
                evidence_refs=context.evidence_refs,
            )
            graph = getattr(tracker, "graph", None)
            resolved_metrics = metrics
            if resolved_metrics is None and context is not None:
                resolved_metrics = context.metadata.get("metrics")
            if resolved_metrics is None:
                resolved_metrics = _default_metrics()
            if graph is not None and getattr(resolved_metrics, "record_fabric_lineage_graph", None):
                resolved_metrics.record_fabric_lineage_graph(
                    graph_id=graph.graph_id,
                    node_count=len(graph.entities) + len(graph.activities) + len(graph.agents),
                    edge_count=len(graph.edges),
                )
    return lineage
