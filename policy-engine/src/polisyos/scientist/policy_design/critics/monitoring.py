"""Monitoring/lifecycle-drift critic for W6.E candidate formulation."""

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


class MonitoringCritic:
    """Check for lifecycle drift and monitoring candidates."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="monitoring",
            substantive_basis="monitoring_lifecycle_drift_simulator",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.monitoring_lifecycle_drift_simulator",
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
        """Evaluate monitoring and revalidation coverage."""

        facets = context_facets(context)
        if not (
            facets.get("monitoring_signal")
            or facets.get("revalidation_trigger")
            or facets.get("time_predicate")
        ):
            return (
                candidate_obligation(
                    self.envelope,
                    context,
                    candidates,
                    (
                        "Candidate obligation: define monitoring signals and "
                        "revalidation triggers before lifecycle closure."
                    ),
                    failure_modes=("monitoring_lifecycle_missing",),
                    facet_refs=("monitoring_signal", "revalidation_trigger", "time_predicate"),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Monitoring or lifecycle revalidation facets are represented.",
                failure_modes=("monitoring_lifecycle_checked",),
            ),
        )
