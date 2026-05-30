"""Deterministic fiscal-rule critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
    candidate_obligation,
    context_facets,
    missing_evidence,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scientist.policy_design.formulator import (
        FormulatorCandidate,
        LLMFormulatorInput,
    )


class FiscalCritic:
    """Apply deterministic fiscal completeness rules to candidate output."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="fiscal",
            substantive_basis="deterministic_rule_set",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.fiscal_rule_set",
        )

    @property
    def envelope(self) -> CriticEnvelope:
        """Critic envelope."""

        return self._envelope

    def evaluate(
        self,
        context: LLMFormulatorInput,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[CriticVerdict, ...]:
        """Evaluate funding and budget completeness."""

        facets = context_facets(context)
        if not facets.get("funding_channel"):
            return (
                missing_evidence(
                    self.envelope,
                    candidates,
                    "Funding channel is absent from the facets.",
                    failure_modes=("funding_channel_missing",),
                ),
            )
        if not (facets.get("budget_envelope") or facets.get("fiscal_limit")):
            return (
                candidate_obligation(
                    self.envelope,
                    context,
                    candidates,
                    (
                        "Candidate obligation: bind the fiscal envelope before fiscal "
                        "adequacy is read."
                    ),
                    failure_modes=("budget_envelope_unbound",),
                    facet_refs=("funding_channel",),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Fiscal facets contain a funding channel and budget limit candidate.",
                failure_modes=("fiscal_basis_present",),
            ),
        )
