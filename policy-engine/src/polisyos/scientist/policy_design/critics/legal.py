"""Legal-corpus-probe critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
    candidates_contain_any,
    context_facets,
    context_obligations,
    missing_evidence,
    obligation_family_present,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scientist.policy_design.formulator import (
        FormulatorCandidate,
        LLMFormulatorInput,
    )


class LegalCritic:
    """Probe whether legal authority is represented as a candidate-only need."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="legal",
            substantive_basis="legal_corpus_probe",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.legal_corpus_probe",
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
        """Evaluate legal authority candidate coverage."""

        facets = context_facets(context)
        obligations = context_obligations(context)
        if not (
            facets.get("authority_type")
            or facets.get("legal_authority")
            or obligation_family_present(obligations, ("legal", "authority"))
        ):
            return (
                missing_evidence(
                    self.envelope,
                    candidates,
                    "Legal authority is not grounded by an authority facet or legal obligation.",
                    failure_modes=("legal_authority_missing",),
                ),
            )
        if candidates_contain_any(candidates, ("legal", "authority", "statutory")):
            return (
                agree(
                    self.envelope,
                    candidates,
                    "Legal authority appears as a candidate-only follow-up.",
                    failure_modes=("legal_candidate_not_authority",),
                ),
            )
        return (
            missing_evidence(
                self.envelope,
                candidates,
                "Authority facet exists, but no legal follow-up candidate was emitted.",
                failure_modes=("legal_follow_up_missing",),
            ),
        )
