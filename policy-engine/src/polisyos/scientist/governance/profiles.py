from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet


class ProfileLevel(Enum):
    """Validation profile intensity levels."""

    FAST = "fast"
    MVP = "mvp"
    STRICT = "strict"


@dataclass(frozen=True)
class ValidationProfile:
    """
    Configuration for validation pipeline behavior.

    Controls which passes run, their thresholds, and short-circuit behavior.
    Immutable to ensure consistent behavior during pipeline execution.
    """

    level: ProfileLevel
    pass_ids: FrozenSet[str]
    thresholds: Dict[str, float] = field(default_factory=dict)
    short_circuit_on_blocker: bool = True

    @classmethod
    def fast(cls) -> "ValidationProfile":
        """
        Fast profile for development and iteration.

        Runs: schema, privacy, budget
        Skips: safety (registry lookup), legal, quality
        """

        return cls(
            level=ProfileLevel.FAST,
            pass_ids=frozenset({"schema", "privacy", "budget"}),
            thresholds={
                "budget_ratio": 0.9,
                "max_interventions": 15,
                "max_graph_cost": 15000,
            },
            short_circuit_on_blocker=True,
        )

    @classmethod
    def mvp(cls) -> "ValidationProfile":
        """
        MVP profile for standard validation.

        Runs: schema, privacy, budget, safety
        Skips: legal, quality
        """

        return cls(
            level=ProfileLevel.MVP,
            pass_ids=frozenset({"schema", "privacy", "budget", "safety"}),
            thresholds={
                "budget_ratio": 0.8,
                "max_interventions": 10,
                "max_graph_cost": 10000,
            },
            short_circuit_on_blocker=True,
        )

    @classmethod
    def strict(cls) -> "ValidationProfile":
        """
        Strict profile for production and compliance.

        Runs: ALL passes including legal and quality gates
        Never short-circuits: complete trace required for audit
        """

        return cls(
            level=ProfileLevel.STRICT,
            pass_ids=frozenset({"schema", "privacy", "budget", "safety", "legal", "quality"}),
            thresholds={
                "budget_ratio": 0.7,
                "max_interventions": 5,
                "max_graph_cost": 5000,
            },
            short_circuit_on_blocker=False,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationProfile":
        """Deserialize from dictionary (for configuration files)."""

        return cls(
            level=ProfileLevel(data["level"]),
            pass_ids=frozenset(data.get("pass_ids", [])),
            thresholds=data.get("thresholds", {}),
            short_circuit_on_blocker=data.get("short_circuit_on_blocker", True),
        )
