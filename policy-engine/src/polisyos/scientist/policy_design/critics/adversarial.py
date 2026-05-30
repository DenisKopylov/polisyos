"""Adversarial-scenario-generator critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
    context_facets,
    scope_drift,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.scientist.policy_design.formulator import (
        FormulatorCandidate,
        LLMFormulatorInput,
    )


class AdversarialCritic:
    """Generate scope-challenge verdicts without pretending to execute scenarios."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="adversarial",
            substantive_basis="adversarial_scenario_generator",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.adversarial_scenario_generator",
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
        """Evaluate whether candidate scope is narrow enough to withstand challenge."""

        facets = context_facets(context)
        has_population = bool(facets.get("population_predicate"))
        has_geography = bool(facets.get("geography_predicate"))
        if has_population != has_geography:
            return (
                scope_drift(
                    self.envelope,
                    candidates,
                    "Population and geography scope are not jointly bounded.",
                    failure_modes=("population_geography_scope_mismatch",),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Adversarial scope challenge did not find a population/geography mismatch.",
                failure_modes=("adversarial_scope_probe_run",),
            ),
        )
