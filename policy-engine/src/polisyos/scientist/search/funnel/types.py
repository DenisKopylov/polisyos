"""Core types for the multi-fidelity evaluation funnel."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Literal

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.search.failure_cards import TypedFailureCard
from polisyos.scientist.search.stages import SearchStage, StageResult
from polisyos.scientist.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)


# ---------------------------------------------------------------------------
# §8.5 — CheapSignalVector
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheapSignalVector:
    """Multi-dimensional cheap signal produced by Level 1 (blueprint §8.5).

    All scores are in [0, 1] unless documented otherwise.
    """

    structural_validity: float = 0.5
    causal_identifiability: float = 0.5
    positivity_risk: float = 0.5
    transportability_risk: float = 0.5
    uncertainty_prior: float = 0.5
    policy_conflict: float = 0.0
    feasibility: float = 0.5
    expected_value_proxy: float = 0.0
    expected_harm_proxy: float = 0.5
    expected_information_gain: float = 0.5

    def routing_decision(self) -> Literal["reject", "defer", "advance", "fast_track"]:
        """Deterministic routing based on vector thresholds (blueprint §8.5)."""
        if self.structural_validity < 0.5 or self.causal_identifiability < 0.2:
            return "reject"
        if self.positivity_risk > 0.8 or self.policy_conflict > 0.8:
            return "reject"
        if (
            self.expected_value_proxy > 0.9
            and self.feasibility > 0.8
            and self.expected_harm_proxy < 0.1
            and self.positivity_risk < 0.2
            and self.uncertainty_prior < 0.3
        ):
            return "fast_track"
        return "advance"


# ---------------------------------------------------------------------------
# §8.6 — FunnelStageResult and FunnelStage
# ---------------------------------------------------------------------------


@dataclass
class FunnelStageResult(StageResult):
    """Extended stage result carrying funnel-specific metadata."""

    uncertainty_envelope: UncertaintyEnvelope = field(
        default_factory=UncertaintyEnvelope.unknown,
    )
    cheap_signal: CheapSignalVector | None = None
    failure_cards: list[TypedFailureCard] = field(default_factory=list)
    compute_actual_usd: float = 0.0
    fidelity_level: int = 0
    audit_refs: list[ArtifactRef] = field(default_factory=list)
    actionable_side_information_ref: ArtifactRef | None = None
    terminal_action: (
        Literal[
            "advance",
            "defer",
            "reject",
            "retry_cheaper",
            "complete",
            "defer_to_human",
        ]
        | None
    ) = None

    @property
    def has_blockers(self) -> bool:
        return any(fc.is_blocker for fc in self.failure_cards)


class FunnelStage(SearchStage):
    """Abstract base for a stage within the multi-fidelity funnel.

    Extends ``SearchStage`` with fidelity metadata and richer result type.
    """

    @property
    @abstractmethod
    def fidelity_level(self) -> int:
        """Numeric fidelity level (0 = cheapest, higher = more expensive)."""
        ...

    @property
    @abstractmethod
    def estimated_cost_usd(self) -> float:
        """Estimated per-candidate cost in USD."""
        ...

    @abstractmethod
    def evaluate(
        self,
        candidate: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FunnelStageResult:
        """Evaluate a candidate and return a funnel-aware result."""
        ...
