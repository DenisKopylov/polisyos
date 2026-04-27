"""Supervisor-worker promotion evidence adapter."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef

__all__ = [
    "SupervisorEvalMetrics",
    "SupervisorPromotionEvaluation",
    "evaluate_supervisor_promotion",
    "supervisor_default_blockers",
]


class SupervisorEvalMetrics(BaseModel):
    """Offline handoff/delegation/quorum metrics for supervisor promotion."""

    model_config = ConfigDict(extra="forbid")

    handoff_eval_ref: ArtifactRef | None = None
    case_count: int = Field(default=0, ge=0)
    delegation_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    quorum_consistency_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_violation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupervisorPromotionEvaluation(BaseModel):
    """Computed promotion decision for supervisor-worker capability evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    metrics: SupervisorEvalMetrics
    passed: bool = False
    blockers: list[str] = Field(default_factory=list)

    @property
    def default_enable_ready(self) -> bool:
        """Return True when the supervisor evidence is sufficient for default enablement."""

        return self.passed and not self.blockers


def evaluate_supervisor_promotion(
    metrics: SupervisorEvalMetrics,
    *,
    min_case_count: int = 3,
    min_delegation_success_rate: float = 0.95,
    min_quorum_consistency_rate: float = 0.85,
    min_citation_coverage: float = 0.85,
    max_budget_violation_rate: float = 0.0,
) -> SupervisorPromotionEvaluation:
    """Evaluate supervisor-worker handoff evidence without executing workers."""

    blockers = supervisor_default_blockers(
        metrics,
        min_case_count=min_case_count,
        min_delegation_success_rate=min_delegation_success_rate,
        min_quorum_consistency_rate=min_quorum_consistency_rate,
        min_citation_coverage=min_citation_coverage,
        max_budget_violation_rate=max_budget_violation_rate,
    )
    return SupervisorPromotionEvaluation(
        metrics=metrics,
        passed=not blockers,
        blockers=blockers,
    )


def supervisor_default_blockers(
    metrics: SupervisorEvalMetrics | None,
    *,
    min_case_count: int = 3,
    min_delegation_success_rate: float = 0.95,
    min_quorum_consistency_rate: float = 0.85,
    min_citation_coverage: float = 0.85,
    max_budget_violation_rate: float = 0.0,
) -> list[str]:
    """Return default-enable blockers for supervisor-worker promotion."""

    if metrics is None:
        return ["supervisor_eval_missing"]
    blockers: list[str] = []
    if metrics.handoff_eval_ref is None:
        blockers.append("missing_supervisor_handoff_eval_ref")
    if metrics.case_count < min_case_count:
        blockers.append("supervisor_handoff_case_count_below_threshold")
    if metrics.delegation_success_rate < min_delegation_success_rate:
        blockers.append("supervisor_delegation_success_rate_below_threshold")
    if metrics.quorum_consistency_rate < min_quorum_consistency_rate:
        blockers.append("supervisor_quorum_consistency_rate_below_threshold")
    if metrics.citation_coverage < min_citation_coverage:
        blockers.append("supervisor_citation_coverage_below_threshold")
    if metrics.budget_violation_rate > max_budget_violation_rate:
        blockers.append("supervisor_budget_violation_rate_above_threshold")
    return sorted(set(blockers))
