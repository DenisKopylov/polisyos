"""Participation-provenance critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
    claim_family_present,
    context_claims,
    context_facets,
    speculation,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scientist.policy_design.formulator import (
        FormulatorCandidate,
        LLMFormulatorInput,
    )


class AffectedPersonCritic:
    """Prevent affected-person preference claims from being laundered from LLM text."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="affected_person",
            substantive_basis="participation_provenance_check",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.participation_provenance_check",
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
        """Evaluate participation provenance for preference/lived-experience claims."""

        facets = context_facets(context)
        claims = context_claims(context)
        has_participation = bool(
            facets.get("participation_provenance_ref")
            or facets.get("participation_mode")
            or facets.get("affected_person_input_ref")
        )
        uses_affected_person_claim = claim_family_present(
            claims,
            ("preference", "lived_experience", "acceptability", "legitimacy"),
        )
        if uses_affected_person_claim and not has_participation:
            return (
                speculation(
                    self.envelope,
                    candidates,
                    (
                        "Affected-person preference or lived-experience content lacks "
                        "participation provenance."
                    ),
                    failure_modes=("participation_provenance_missing",),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Affected-person claims are either absent or have participation provenance.",
                failure_modes=("participation_provenance_checked",),
            ),
        )
