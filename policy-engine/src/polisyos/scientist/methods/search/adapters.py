"""Concrete bridges from search contracts to legacy runtime owners.

The DTOs and protocols stay in :mod:`contracts`; this module is the only
place where those contracts are connected to the legacy controller and funnel
implementations.  The adapter deliberately delegates evaluation acceptance to
the controller's state-owner seam instead of editing controller compatibility
views itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
)
from polisyos.scientist.methods.search.funnel.orchestrator import (
    FunnelOrchestrator,
    FunnelOutcome,
    FunnelTicket,
)
from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver


class LegacySearchServiceAdapter(_NativeSearchServiceDriver):
    """Compatibility name for the native ask/tell service driver."""


@dataclass(slots=True)
class OrchestratorFunnelService:
    """Wrap ``FunnelOrchestrator`` behind the canonical funnel contract."""

    orchestrator: FunnelOrchestrator

    def submit(
        self,
        candidate: CandidateProposal,
        *,
        context: dict[str, Any] | None = None,
    ) -> FunnelTicket:
        """Submit one proposal to the existing multi-fidelity orchestrator."""
        return self.orchestrator.submit(candidate.payload, context or {})

    def get_result(self, ticket: FunnelTicket | str) -> FunnelOutcome:
        """Return a completed outcome, advancing the existing ticket if needed."""
        outcome = self.orchestrator.get_outcome(ticket)
        if not outcome.completed and outcome.final_result is None:
            return self.orchestrator.advance(ticket, policy="full")
        return outcome


__all__ = [
    "LegacySearchServiceAdapter",
    "OrchestratorFunnelService",
]
