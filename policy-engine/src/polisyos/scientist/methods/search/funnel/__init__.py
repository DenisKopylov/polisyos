"""Multi-fidelity evaluation funnel for the Scientist search platform.

Provides a progressive filtering pipeline (Levels 0-3+) that rejects
structurally invalid and causally implausible candidates cheaply,
reserving expensive evaluation for promising ones only.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from polisyos.ir import TypedFailureCard, UncertaintyType
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelAttemptHistory,
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
    UncertaintyEstimate,
)

__all__ = [
    # Core types (A.1)
    "CheapSignalVector",
    "FunnelAttemptHistory",
    "FunnelStage",
    "FunnelStageResult",
    "FunnelOutcome",
    "FunnelTicket",
    "FunnelTraceStep",
    "TypedFailureCard",
    "UncertaintyEnvelope",
    "UncertaintyEstimate",
    "UncertaintyType",
    "Level5RefutationGovernanceStage",
    "Level6PromotionStage",
]

# Lazy imports for stage implementations to avoid heavy dependencies at import time.

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "Level0StaticValidator": (
        "polisyos.scientist.methods.search.funnel.level0_static",
        "Level0StaticValidator",
    ),
    "Level1CheapHeuristic": (
        "polisyos.scientist.methods.search.funnel.level1_heuristic",
        "Level1CheapHeuristic",
    ),
    "Level2CausalPlausibility": (
        "polisyos.scientist.methods.search.funnel.level2_causal",
        "Level2CausalPlausibility",
    ),
    "Level3MediumFidelity": (
        "polisyos.scientist.methods.search.funnel.level3_medium",
        "Level3MediumFidelity",
    ),
    "Level4FullFidelity": (
        "polisyos.scientist.methods.search.funnel.level4_full",
        "Level4FullFidelity",
    ),
    "Level5RefutationGovernanceStage": (
        "polisyos.scientist.methods.search.funnel.level5_refutation_governance",
        "Level5RefutationGovernanceStage",
    ),
    "Level6PromotionStage": (
        "polisyos.scientist.methods.search.funnel.level6_promotion",
        "Level6PromotionStage",
    ),
    "FunnelOrchestrator": (
        "polisyos.scientist.methods.search.funnel.orchestrator",
        "FunnelOrchestrator",
    ),
    "FunnelTicket": (
        "polisyos.scientist.methods.search.funnel.orchestrator",
        "FunnelTicket",
    ),
    "FunnelTraceStep": (
        "polisyos.scientist.methods.search.funnel.orchestrator",
        "FunnelTraceStep",
    ),
    "FunnelOutcome": (
        "polisyos.scientist.methods.search.funnel.orchestrator",
        "FunnelOutcome",
    ),
    "FunnelCorrelationTracker": (
        "polisyos.scientist.methods.search.funnel.correlation",
        "FunnelCorrelationTracker",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
