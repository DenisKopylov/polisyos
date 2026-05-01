"""Research trajectory comparison reports for Research DAG replay."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.research_dag.diff import ResearchDAGDiff, diff_research_dags
from polisyos.scientist.research_dag.models import (
    FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS,
    FORBIDDEN_PUBLIC_METADATA_TOKENS,
    ResearchDAGArtifact,
)

_FORBIDDEN_PUBLIC_TEXT_TOKENS = (
    *FORBIDDEN_PUBLIC_METADATA_TOKENS,
    *FORBIDDEN_PUBLIC_ARTIFACT_KIND_TOKENS,
)


class ResearchTrajectoryComparisonReport(BaseModel):
    """Decision-oriented comparison between two Research DAG runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    old_run_id: str
    new_run_id: str
    workflow_id: str
    changed_queries: list[str] = Field(default_factory=list)
    changed_sources: list[str] = Field(default_factory=list)
    changed_snippets: list[str] = Field(default_factory=list)
    changed_claim_ids: list[str] = Field(default_factory=list)
    changed_governance_outcomes: list[str] = Field(default_factory=list)
    added_node_ids: list[str] = Field(default_factory=list)
    removed_node_ids: list[str] = Field(default_factory=list)
    explanation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def compare_research_trajectories(
    old: ResearchDAGArtifact,
    new: ResearchDAGArtifact,
) -> ResearchTrajectoryComparisonReport:
    """Compare two runs by research trajectory, not just artifact filenames."""

    diff = diff_research_dags(old, new)
    return comparison_report_from_diff(diff, workflow_id=new.workflow_id)


def comparison_report_from_diff(
    diff: ResearchDAGDiff,
    *,
    workflow_id: str,
) -> ResearchTrajectoryComparisonReport:
    """Build a human-readable trajectory comparison report from a DAG diff."""

    changed_categories = [
        label
        for label, values in (
            ("queries", diff.changed_queries),
            ("sources", diff.changed_sources),
            ("snippets", diff.changed_snippets),
            ("claims", diff.changed_claim_ids),
            ("governance", diff.changed_governance_outcomes),
        )
        if values
    ]
    explanation = (
        "Research trajectory changed in: " + ", ".join(changed_categories)
        if changed_categories
        else "Research trajectory did not change in tracked categories."
    )
    return ResearchTrajectoryComparisonReport(
        old_run_id=diff.old_run_id,
        new_run_id=diff.new_run_id,
        workflow_id=workflow_id,
        changed_queries=list(diff.changed_queries),
        changed_sources=list(diff.changed_sources),
        changed_snippets=list(diff.changed_snippets),
        changed_claim_ids=list(diff.changed_claim_ids),
        changed_governance_outcomes=list(diff.changed_governance_outcomes),
        added_node_ids=list(diff.added_node_ids),
        removed_node_ids=list(diff.removed_node_ids),
        explanation=explanation,
        metadata={
            "changed_category_count": len(changed_categories),
            "changed_categories": changed_categories,
        },
    )


def public_comparison_export(
    report: ResearchTrajectoryComparisonReport,
) -> dict[str, Any]:
    """Return public comparison data without hidden/private source internals."""

    redacted = _redact_public_value(report.model_dump(mode="json"))
    if not isinstance(redacted, dict):
        return {"redacted": True}
    return redacted


def _redact_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_public_value(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if any(token in lowered for token in _FORBIDDEN_PUBLIC_TEXT_TOKENS):
            return "redacted"
    return value


__all__ = [
    "ResearchTrajectoryComparisonReport",
    "compare_research_trajectories",
    "comparison_report_from_diff",
    "public_comparison_export",
]
