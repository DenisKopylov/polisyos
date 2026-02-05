"""Multi-fidelity extension points for future BOHB/Successive Halving integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FidelityLevel:
    """One fidelity tier and expected cost/accuracy profile."""

    level: int
    resource_budget: float
    accuracy_estimate: float


class FidelityScheduler(Protocol):
    """Protocol for fidelity progression policies."""

    def get_fidelity(
        self,
        candidate_id: str,
        current_level: int,
        observed_score: float,
    ) -> tuple[int, bool]:
        """Return next fidelity level and whether to continue candidate."""

    def register_evaluation(self, candidate_id: str, fidelity: int, score: float) -> None:
        """Record fidelity result for bracket decisions."""


@dataclass(slots=True)
class SuccessiveHalvingScheduler:
    """Simplified successive halving scheduler for candidate pruning."""

    min_fidelity: int = 1
    max_fidelity: int = 81
    eta: int = 3
    _candidate_fidelity: dict[str, int] = field(default_factory=dict)
    _scores_by_fidelity: dict[int, list[tuple[str, float]]] = field(default_factory=dict)

    def get_fidelity(
        self,
        candidate_id: str,
        current_level: int,
        observed_score: float,
    ) -> tuple[int, bool]:
        del observed_score
        if candidate_id not in self._candidate_fidelity:
            self._candidate_fidelity[candidate_id] = self.min_fidelity
            return self.min_fidelity, True
        next_fidelity = min(current_level * self.eta, self.max_fidelity)
        return next_fidelity, next_fidelity <= self.max_fidelity

    def register_evaluation(self, candidate_id: str, fidelity: int, score: float) -> None:
        self._scores_by_fidelity.setdefault(fidelity, []).append((candidate_id, score))
        self._candidate_fidelity[candidate_id] = fidelity

