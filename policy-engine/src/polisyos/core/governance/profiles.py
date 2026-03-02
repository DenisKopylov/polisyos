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
                "quality_missingness_acceptable": 0.20,
                "quality_staleness_acceptable": 120,
                "quality_coverage_acceptable": 0.70,
            },
            short_circuit_on_blocker=True,
        )

    @classmethod
    def mvp(cls) -> "ValidationProfile":
        """
        MVP profile for standard validation.

        Runs: schema, privacy, budget, safety, literature_gate, sutva_check
        Skips: legal, quality
        """

        return cls(
            level=ProfileLevel.MVP,
            pass_ids=frozenset(
                {
                    "schema",
                    "privacy",
                    "pii_check",
                    "budget",
                    "safety",
                    "equity",
                    "refutation",
                    "literature_gate",
                    "sutva_check",
                    "transportability_required",
                }
            ),
            thresholds={
                "budget_ratio": 0.8,
                "max_interventions": 10,
                "max_graph_cost": 10000,
                "quality_missingness_acceptable": 0.10,
                "quality_staleness_acceptable": 60,
                "quality_coverage_acceptable": 0.85,
                "equity_gini_increase_max": 0.03,
                "equity_vulnerable_loss_max_pct": -7.5,
                "equity_max_losers_share": 0.70,
            },
            short_circuit_on_blocker=True,
        )

    @classmethod
    def strict(cls) -> "ValidationProfile":
        """
        Strict profile for production and compliance.

        Runs: ALL passes including legal/quality + strict human review requirement
        Never short-circuits: complete trace required for audit
        """

        return cls(
            level=ProfileLevel.STRICT,
            pass_ids=frozenset(
                {
                    "schema",
                    "privacy",
                    "pii_check",
                    "budget",
                    "safety",
                    "legal",
                    "quality",
                    "confidence",
                    "equity",
                    "refutation",
                    "literature_gate",
                    "sutva_check",
                    "transportability_required",
                    "human_review_required",
                }
            ),
            thresholds={
                "budget_ratio": 0.7,
                "max_interventions": 5,
                "max_graph_cost": 5000,
                "quality_missingness_acceptable": 0.05,
                "quality_staleness_acceptable": 14,
                "quality_coverage_acceptable": 0.95,
                "quality_min_row_count": 100,
                "uncertainty_max_ci_width_ratio": 0.5,
                "uncertainty_max_ci_width_abs": 1e6,
                "uncertainty_min_gate_eligible_ratio": 0.5,
                "equity_gini_increase_max": 0.02,
                "equity_vulnerable_loss_max_pct": -5.0,
                "equity_max_losers_share": 0.60,
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
