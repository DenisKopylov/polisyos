"""Stable backtesting facade for replay, masking, challenge suites, and trust scoring.

Core evaluator/orchestrator exports are imported eagerly because they are pure
Python and define the standard replay contract. Composition replay helpers are
lazy-loaded to avoid importing cross-graph reconciliation dependencies unless a
benchmark explicitly audits fragment composition.
"""

from __future__ import annotations

import importlib
from typing import Any

from .adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    PHASE_D4_ROTATION_GROUP,
    STRATEGIC_GAMING_SUITE_ID,
    AdversarialGenerator,
    AdversarialScenario,
    ChallengeCase,
    ChallengeCaseResult,
    ChallengeSuiteResult,
    run_phase_d4_challenge_suites,
)
from .evaluator import PredictionEvaluator
from .masking import OutcomeMasker
from .orchestrator import BacktestOrchestrator
from .plan import HistoricalValidationPlan, MaskingStrategy, PredictionSource
from .trust_scorer import TrustScorer

__all__ = [
    "ABSTRACTION_LEAKAGE_SUITE_ID",
    "MULTIPLICITY_DISCLOSURE_SUITE_ID",
    "PHASE_D4_ROTATION_GROUP",
    "STRATEGIC_GAMING_SUITE_ID",
    "AdversarialGenerator",
    "AdversarialScenario",
    "BacktestOrchestrator",
    "ChallengeCase",
    "ChallengeCaseResult",
    "ChallengeSuiteResult",
    "CompositionReplayResult",
    "HistoricalValidationPlan",
    "MaskingStrategy",
    "OutcomeMasker",
    "PredictionEvaluator",
    "PredictionSource",
    "TemporalEvaluationResult",
    "TemporalThresholds",
    "TrustScorer",
    "build_temporal_backtest_report",
    "evaluate_temporal_safe_rejection",
    "evaluate_temporal_trajectory",
    "replay_fragment_composition_case",
    "run_phase_d4_challenge_suites",
    "summarize_temporal_evaluations",
]


def __getattr__(name: str) -> Any:
    """Resolve optional backtesting helpers on first access."""
    if name in {"CompositionReplayResult", "replay_fragment_composition_case"}:
        module = importlib.import_module("polisyos.scientist.methods.backtesting.composition_bridge")
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {
        "TemporalThresholds",
        "TemporalEvaluationResult",
        "evaluate_temporal_trajectory",
        "evaluate_temporal_safe_rejection",
        "summarize_temporal_evaluations",
        "build_temporal_backtest_report",
    }:
        module = importlib.import_module("polisyos.scientist.methods.backtesting.temporal")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
