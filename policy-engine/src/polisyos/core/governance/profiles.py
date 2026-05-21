"""Public governance profiles module API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from polisyos.core.contracts.control import (
    EXECUTION_PROFILE_TO_VALIDATION_PROFILE,
    POLICY_AUTHORITY_PROFILES,
    PolicyAuthorityProfile,
    PolicyValidationProfile,
)


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
    pass_ids: frozenset[str]
    thresholds: dict[str, float] = field(default_factory=dict)
    short_circuit_on_blocker: bool = True

    @classmethod
    def fast(cls) -> ValidationProfile:
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
    def mvp(cls) -> ValidationProfile:
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
                    "causal_frontier_leakage",
                    "equity",
                    "incentive_compatibility",
                    "refutation",
                    "cross_graph_evidence",
                    "literature_gate",
                    "normative_arbitration",
                    "strategic_response",
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
                "causal_frontier_blr_warning": 0.05,
                "causal_frontier_blr_blocker": 0.15,
                "equity_gini_increase_max": 0.03,
                "equity_vulnerable_loss_max_pct": -7.5,
                "equity_max_losers_share": 0.70,
            },
            short_circuit_on_blocker=True,
        )

    @classmethod
    def strict(cls) -> ValidationProfile:
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
                    "causal_frontier_leakage",
                    "confidence",
                    "equity",
                    "incentive_compatibility",
                    "refutation",
                    "cross_graph_evidence",
                    "literature_gate",
                    "normative_arbitration",
                    "strategic_response",
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
                "causal_frontier_blr_warning": 0.05,
                "causal_frontier_blr_blocker": 0.15,
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
    def from_dict(cls, data: dict[str, Any]) -> ValidationProfile:
        """Deserialize from dictionary (for configuration files)."""

        return cls(
            level=ProfileLevel(data["level"]),
            pass_ids=frozenset(data.get("pass_ids", [])),
            thresholds=data.get("thresholds", {}),
            short_circuit_on_blocker=data.get("short_circuit_on_blocker", True),
        )


_VALIDATION_PROFILE_BUILDERS = {
    "fast": ValidationProfile.fast,
    "mvp": ValidationProfile.mvp,
    "strict": ValidationProfile.strict,
}


def validation_profile_name_for_execution_profile(
    execution_profile: str,
) -> PolicyValidationProfile:
    """Map an existing execution profile to its governance validation profile."""

    normalized = execution_profile.strip().casefold().replace("-", "_")
    try:
        return EXECUTION_PROFILE_TO_VALIDATION_PROFILE[normalized]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(
            f"unsupported execution profile for validation mapping: {execution_profile!r}"
        ) from exc


def validation_profile_for_execution_profile(execution_profile: str) -> ValidationProfile:
    """Return the concrete governance profile for an execution profile."""

    profile_name = validation_profile_name_for_execution_profile(execution_profile)
    return _VALIDATION_PROFILE_BUILDERS[profile_name]()


def policy_authority_validation_profiles() -> dict[
    PolicyAuthorityProfile,
    PolicyValidationProfile,
]:
    """Return authority-level validation mapping without introducing new names."""

    return {
        cast("PolicyAuthorityProfile", profile): validation_profile_name_for_execution_profile(
            profile
        )
        for profile in POLICY_AUTHORITY_PROFILES
    }


__all__ = [
    "ProfileLevel",
    "ValidationProfile",
    "policy_authority_validation_profiles",
    "validation_profile_for_execution_profile",
    "validation_profile_name_for_execution_profile",
]
