"""Simulation-probe implementation critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
    candidate_obligation,
    context_facets,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scientist.policy_design.formulator import (
        FormulatorCandidate,
        LLMFormulatorInput,
    )


class ImplementationCritic:
    """Check whether implementation feasibility has a probe path."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="implementation",
            substantive_basis="simulation_probe",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.implementation_simulation_probe",
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
        """Evaluate implementation and delivery probe coverage."""

        facets = context_facets(context)
        if not facets.get("delivery_channel") or not facets.get("time_predicate"):
            return (
                candidate_obligation(
                    self.envelope,
                    context,
                    candidates,
                    (
                        "Candidate obligation: run an implementation feasibility probe "
                        "for delivery channel and timeline assumptions."
                    ),
                    failure_modes=("implementation_probe_missing",),
                    facet_refs=("delivery_channel", "time_predicate"),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Delivery channel and time-window candidates are available for simulation.",
                failure_modes=("implementation_probe_basis_present",),
            ),
        )
