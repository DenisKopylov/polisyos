"""Multi-fidelity evaluation funnel for the Scientist search platform.

Provides a progressive filtering pipeline (Levels 0-3+) that rejects
structurally invalid and causally implausible candidates cheaply,
reserving expensive evaluation for promising ones only.
"""

from __future__ import annotations

from typing import Any

from polisyos.scientist.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)

__all__ = [
    # Core types (A.1)
    "CheapSignalVector",
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


def __getattr__(name: str) -> Any:  # noqa: N807
    if name == "Level0StaticValidator":
        from polisyos.scientist.search.funnel.level0_static import Level0StaticValidator

        return Level0StaticValidator
    if name == "Level1CheapHeuristic":
        from polisyos.scientist.search.funnel.level1_heuristic import Level1CheapHeuristic

        return Level1CheapHeuristic
    if name == "Level2CausalPlausibility":
        from polisyos.scientist.search.funnel.level2_causal import Level2CausalPlausibility

        return Level2CausalPlausibility
    if name == "Level3MediumFidelity":
        from polisyos.scientist.search.funnel.level3_medium import Level3MediumFidelity

        return Level3MediumFidelity
    if name == "Level4FullFidelity":
        from polisyos.scientist.search.funnel.level4_full import Level4FullFidelity

        return Level4FullFidelity
    if name == "Level5RefutationGovernanceStage":
        from polisyos.scientist.search.funnel.level5_refutation_governance import (
            Level5RefutationGovernanceStage,
        )

        return Level5RefutationGovernanceStage
    if name == "Level6PromotionStage":
        from polisyos.scientist.search.funnel.level6_promotion import (
            Level6PromotionStage,
        )

        return Level6PromotionStage
    if name == "FunnelOrchestrator":
        from polisyos.scientist.search.funnel.orchestrator import FunnelOrchestrator

        return FunnelOrchestrator
    if name == "FunnelTicket":
        from polisyos.scientist.search.funnel.orchestrator import FunnelTicket

        return FunnelTicket
    if name == "FunnelTraceStep":
        from polisyos.scientist.search.funnel.orchestrator import FunnelTraceStep

        return FunnelTraceStep
    if name == "FunnelOutcome":
        from polisyos.scientist.search.funnel.orchestrator import FunnelOutcome

        return FunnelOutcome
    if name == "FunnelCorrelationTracker":
        from polisyos.scientist.search.funnel.correlation import FunnelCorrelationTracker

        return FunnelCorrelationTracker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
