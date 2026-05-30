"""Statistical-pattern equity critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
    claim_family_present,
    context_claims,
    context_facets,
    missing_evidence,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scientist.policy_design.formulator import (
        FormulatorCandidate,
        LLMFormulatorInput,
    )


class EquityCritic:
    """Look for distributional/equity coverage using statistical risk patterns."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="equity",
            substantive_basis="statistical_pattern",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.equity_statistical_pattern",
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
        """Evaluate equity/distributional candidate coverage."""

        facets = context_facets(context)
        claims = context_claims(context)
        has_targeting = bool(facets.get("targeting_type") or facets.get("population_predicate"))
        if has_targeting and not claim_family_present(
            claims,
            ("distributional", "equity", "procedural_fairness"),
        ):
            return (
                missing_evidence(
                    self.envelope,
                    candidates,
                    "Targeted policy lacks a distributional or equity claim candidate.",
                    failure_modes=("distributional_claim_missing",),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Equity-sensitive targeting is represented in candidate claims or facets.",
                failure_modes=("equity_pattern_considered",),
            ),
        )
