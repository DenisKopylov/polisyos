"""Fairness tier definitions and benchmark configuration constants."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class FairnessTier(enum.Enum):
    """Three tiers of fairness for head-to-head comparison."""

    A = "minimal"       # Isolates algorithm: identical simple nuisance
    B = "best_effort"   # Fair tuning budget: identical strong nuisance
    C = "default"       # Ecological validity: library recommended defaults


TIER_A_NUISANCE: dict[str, Any] = {
    "propensity_model": "logistic_regression",
    "outcome_model": "linear_regression",
    "cv_folds": 5,
    "calibration": None,
    "model_selection": None,
    "overlap_trimming": None,
    "bootstrap_draws": 200,
}

TIER_B_NUISANCE: dict[str, Any] = {
    "propensity_model": "hist_gradient_boosting_classifier",
    "outcome_model": "hist_gradient_boosting_regressor",
    "propensity_max_iter": 200,
    "propensity_max_depth": 6,
    "outcome_max_iter": 200,
    "outcome_max_depth": 6,
    "cv_folds": 5,
    "calibration": None,
    "model_selection": None,
    "overlap_trimming_lower": 0.01,
    "overlap_trimming_upper": 0.99,
    "bootstrap_draws": 200,
}


@dataclass(frozen=True)
class BenchmarkConfig:
    """Top-level benchmark configuration."""

    tiers: tuple[FairnessTier, ...] = (FairnessTier.A, FairnessTier.B, FairnessTier.C)
    sample_sizes: tuple[int, ...] = (1000, 2500, 5000)
    k_replications: int = 100
    k_replications_ihdp: int = 1000
    base_seed: int = 42
    timeout_per_method_s: float = 300.0
    bootstrap_metric_resamples: int = 1000
    smoke: bool = False

    def effective_k(self, dataset_name: str) -> int:
        if self.smoke:
            return 3
        if dataset_name == "ihdp":
            return self.k_replications_ihdp
        return self.k_replications

    def effective_sample_sizes(self) -> tuple[int, ...]:
        if self.smoke:
            return (500,)
        return self.sample_sizes

    def effective_tiers(self) -> tuple[FairnessTier, ...]:
        if self.smoke:
            return (FairnessTier.B,)
        return self.tiers


def nuisance_config_for_tier(tier: FairnessTier) -> dict[str, Any] | None:
    """Return shared nuisance config for a tier, or None for Tier C."""
    if tier is FairnessTier.A:
        return dict(TIER_A_NUISANCE)
    if tier is FairnessTier.B:
        return dict(TIER_B_NUISANCE)
    return None
