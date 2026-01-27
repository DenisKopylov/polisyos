from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Protocol


class OptimizationDirection(str, Enum):
    """Direction for objective optimization."""

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


@dataclass(frozen=True)
class ObjectiveValue:
    """
    Evaluated value of a single objective.

    Attributes:
        name: Objective identifier
        raw_value: Actual metric value from simulation
        direction: Whether to minimize or maximize
        weight: Importance weight for composite objectives
        is_satisfied: Whether value meets any constraint thresholds
    """

    name: str
    raw_value: float
    direction: OptimizationDirection
    weight: float = 1.0
    is_satisfied: bool = True
    threshold: float | None = None

    @property
    def normalized_value(self) -> float:
        """
        Normalize to minimization convention.

        This enables uniform comparison: lower is always better.
        """
        if self.direction == OptimizationDirection.MAXIMIZE:
            return -self.raw_value
        return self.raw_value

    @property
    def weighted_value(self) -> float:
        """Return normalized value scaled by weight."""
        return self.normalized_value * self.weight


class SearchObjective(Protocol):
    """Protocol for search objectives."""

    @property
    def name(self) -> str:
        """Unique identifier for this objective."""

    @property
    def direction(self) -> OptimizationDirection:
        """Optimization direction."""

    def evaluate(self, results: Dict[str, Any]) -> ObjectiveValue:
        """
        Evaluate objective from simulation results.

        Args:
            results: Dict containing simulation outputs (gdp_change, etc.)

        Returns:
            ObjectiveValue with evaluation details
        """


class BaseObjective(ABC):
    """Abstract base class for objectives with common functionality."""

    def __init__(
        self,
        weight: float = 1.0,
        threshold: float | None = None,
    ):
        self._weight = weight
        self._threshold = threshold

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def direction(self) -> OptimizationDirection:
        ...

    @abstractmethod
    def _extract_value(self, results: Dict[str, Any]) -> float:
        """Extract raw metric value from results dict."""
        ...

    def evaluate(self, results: Dict[str, Any]) -> ObjectiveValue:
        raw = self._extract_value(results)

        is_satisfied = True
        if self._threshold is not None:
            if self.direction == OptimizationDirection.MINIMIZE:
                is_satisfied = raw <= self._threshold
            else:
                is_satisfied = raw >= self._threshold

        return ObjectiveValue(
            name=self.name,
            raw_value=raw,
            direction=self.direction,
            weight=self._weight,
            is_satisfied=is_satisfied,
            threshold=self._threshold,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Concrete Objective Implementations
# ─────────────────────────────────────────────────────────────────────────────


class GDPGrowthObjective(BaseObjective):
    """Maximize GDP growth rate."""

    @property
    def name(self) -> str:
        return "gdp_growth"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MAXIMIZE

    def _extract_value(self, results: Dict[str, Any]) -> float:
        return float(results.get("gdp_change", 0.0))


class BudgetDeficitObjective(BaseObjective):
    """Minimize budget deficit (absolute value)."""

    @property
    def name(self) -> str:
        return "budget_deficit"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: Dict[str, Any]) -> float:
        balance = results.get("gov_balance", 0.0)
        if balance is None:
            balance = -results.get("budget_deficit", 0.0)
        return abs(min(balance, 0))


class InequalityObjective(BaseObjective):
    """Minimize Gini coefficient (inequality)."""

    @property
    def name(self) -> str:
        return "inequality"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: Dict[str, Any]) -> float:
        return float(results.get("gini_coefficient", 0.5))


class EmploymentObjective(BaseObjective):
    """Maximize employment rate."""

    @property
    def name(self) -> str:
        return "employment"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MAXIMIZE

    def _extract_value(self, results: Dict[str, Any]) -> float:
        return float(results.get("employment_rate", 0.0))


# ─────────────────────────────────────────────────────────────────────────────
# Composite Objective
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompositeObjective:
    """
    Weighted combination of multiple objectives.

    Example:
        objective = CompositeObjective([
            GDPGrowthObjective(weight=0.7),
            InequalityObjective(weight=0.3),
        ])
    """

    objectives: List[SearchObjective] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "composite"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: Dict[str, Any]) -> ObjectiveValue:
        """Evaluate all objectives and return weighted sum."""
        if not self.objectives:
            return ObjectiveValue(
                name=self.name,
                raw_value=0.0,
                direction=self.direction,
            )

        total = 0.0
        all_satisfied = True

        for obj in self.objectives:
            val = obj.evaluate(results)
            total += val.weighted_value
            all_satisfied = all_satisfied and val.is_satisfied

        return ObjectiveValue(
            name=self.name,
            raw_value=total,
            direction=self.direction,
            is_satisfied=all_satisfied,
        )

    def evaluate_detailed(self, results: Dict[str, Any]) -> List[ObjectiveValue]:
        """Return individual objective evaluations for analysis."""
        return [obj.evaluate(results) for obj in self.objectives]


# ─────────────────────────────────────────────────────────────────────────────
# Factory for Common Objective Configurations
# ─────────────────────────────────────────────────────────────────────────────


class ObjectivePresets:
    """Pre-configured objective combinations for common use cases."""

    @staticmethod
    def balanced_growth() -> CompositeObjective:
        """Balance GDP growth with fiscal responsibility."""
        return CompositeObjective(
            [
                GDPGrowthObjective(weight=0.5),
                BudgetDeficitObjective(weight=0.3),
                InequalityObjective(weight=0.2),
            ]
        )

    @staticmethod
    def growth_focused() -> CompositeObjective:
        """Prioritize GDP growth."""
        return CompositeObjective(
            [
                GDPGrowthObjective(weight=0.8),
                BudgetDeficitObjective(weight=0.2),
            ]
        )

    @staticmethod
    def equity_focused() -> CompositeObjective:
        """Prioritize reducing inequality."""
        return CompositeObjective(
            [
                InequalityObjective(weight=0.6),
                EmploymentObjective(weight=0.3),
                GDPGrowthObjective(weight=0.1),
            ]
        )
