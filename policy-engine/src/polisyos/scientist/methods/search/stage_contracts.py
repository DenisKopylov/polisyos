"""Dependency-neutral typed contracts for search evaluation stages.

Concrete stage implementations and the public compatibility facade remain in
:mod:`polisyos.scientist.methods.search.stages`. This leaf lets funnel DTOs
refer to stage contracts without importing runtime stage implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAdmission,
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    _validate_objective_score_state,
)


@dataclass
class StageResult:
    """Result from a search stage evaluation."""

    policy_candidate: dict[str, Any]
    objective_value: float | None
    is_promising: bool
    stage_name: str
    score_status: ObjectiveScoreStatus = ObjectiveScoreStatus.NOT_ESTABLISHED
    score_assessment: ObjectiveScoreAssessment | None = None
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    simulation_results: dict[str, Any] = field(default_factory=dict)
    feedback: dict[str, Any] = field(default_factory=dict)

    predicted_score: float | None = None
    actual_score: float | None = None
    score_admission: ObjectiveScoreAdmission | None = None

    def __post_init__(self) -> None:
        """Keep numeric diagnostics while requiring a source assessment for admission."""
        if self.score_admission is not None:
            self.score_status = self.score_admission.status
            if self.score_status is not ObjectiveScoreStatus.AVAILABLE:
                self.objective_value = None
            elif self.score_admission.reported_assessment != self.score_assessment:
                self.score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                self.objective_value = None
            elif self.score_assessment is not None:
                self.objective_value = self.score_assessment.value
        elif self.score_assessment is None:
            if self.score_status is ObjectiveScoreStatus.AVAILABLE:
                self.score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        else:
            self.score_status = self.score_assessment.status
            if self.score_status is ObjectiveScoreStatus.AVAILABLE:
                self.objective_value = self.score_assessment.value
        _validate_objective_score_state(self.objective_value, self.score_status)


class SearchStage(ABC):
    """Abstract search stage for policy evaluation."""

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Unique identifier for this stage."""
        ...

    @abstractmethod
    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> StageResult:
        """
        Evaluate a policy candidate.

        Args:
            candidate: Policy IR or policy-like dict
            context: Additional context (user_request, etc.)

        Returns:
            StageResult with evaluation details
        """
        ...


# Preserve historical pickle/import paths while exposing these classes through
# the dependency-neutral module internally.
StageResult.__module__ = "polisyos.scientist.methods.search.stages"
SearchStage.__module__ = "polisyos.scientist.methods.search.stages"
