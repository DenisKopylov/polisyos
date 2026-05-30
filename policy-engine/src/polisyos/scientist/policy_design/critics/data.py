"""Historical-failure-corpus data critic for W6.E candidate formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.policy_design.critic_contracts import CriticEnvelope, CriticVerdict
from polisyos.scientist.policy_design.critics._shared import (
    agree,
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


class DataCritic:
    """Flag historical data-lineage failure modes before authority admission."""

    def __init__(self) -> None:
        self._envelope = CriticEnvelope(
            critic_role="data",
            substantive_basis="historical_failure_corpus",
            critic_version="1.0.0",
            basis_ref="policy_design_case.W6.E.data_failure_corpus",
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
        """Evaluate data/source-lineage candidate coverage."""

        facets = context_facets(context)
        claims = context_claims(context)
        needs_data = any(
            str(claim.get("claim_family") or claim.get("claim_type") or "").lower()
            in {"causal", "distributional", "forecast", "welfare", "implementation"}
            for claim in claims
        )
        if needs_data and not (
            facets.get("data_source_family")
            or facets.get("data_requirement")
            or facets.get("production_data_manifest_ref")
        ):
            return (
                missing_evidence(
                    self.envelope,
                    candidates,
                    "Evidence-seeking claims lack a data source family or lineage candidate.",
                    failure_modes=("data_lineage_candidate_missing",),
                ),
            )
        return (
            agree(
                self.envelope,
                candidates,
                "Data-lineage needs are either absent or represented as candidates.",
                failure_modes=("data_failure_corpus_checked",),
            ),
        )
