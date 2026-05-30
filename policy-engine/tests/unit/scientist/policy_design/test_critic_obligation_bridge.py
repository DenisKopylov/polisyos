from __future__ import annotations

# ruff: noqa: S101
from typing import TYPE_CHECKING

from polisyos.obligation_graph import PriorityClass, SourceClass
from polisyos.scientist.policy_design.critic_ensemble import (
    CriticEnvelope,
    CriticVerdict,
    MultiCriticEnsemble,
    PolicyDesignCritic,
)
from polisyos.scientist.policy_design.critic_obligation_bridge import (
    critic_consensus_to_obligation_candidates,
)
from polisyos.scientist.policy_design.formulator import (
    FormulatorCandidate,
    LLMFormulator,
)

from .test_formulator import _msme_input

if TYPE_CHECKING:
    from collections.abc import Sequence


def test_critic_consensus_bridge_emits_review_required_obligation_candidate() -> None:
    payload = _msme_input()
    formulated = LLMFormulator().formulate(payload)
    target = next(
        candidate for candidate in formulated.candidates if candidate.kind == "obligation"
    )
    critics = tuple(
        _StaticTargetCritic(role=f"role_{index}", target_candidate_id=target.candidate_id)
        for index in range(6)
    )
    report = MultiCriticEnsemble(critics=critics).evaluate(
        payload,
        candidates=formulated.candidates,
    )

    candidates = critic_consensus_to_obligation_candidates(
        formulator_output=formulated,
        critic_report=report,
        facets=payload.facets,
        intent_text=payload.intent,
        authority_profile_ref="authority_profile.msme_governed",
        consensus_threshold=6,
    )

    assert len(candidates) == 1
    emitted = candidates[0]
    assert emitted.source_class is SourceClass.LLM_CRITIC_CONSENSUS
    assert emitted.priority_hint is PriorityClass.REVIEW_REQUIRED
    assert emitted.metadata["consensus_threshold"] == 6
    assert emitted.metadata["support_count"] == 6
    assert target.candidate_id in emitted.metadata["formulator_candidate_ref"]
    assert emitted.metadata["admission_state"] == "candidate_unverified"
    assert emitted.metadata["candidate_kind"] == "candidate_capability"
    assert "producer_domain_truth" in emitted.metadata["may_not_use_for"]
    assert "producer_backed_admission_required" in emitted.metadata["next_required_steps"]


def test_critic_consensus_bridge_does_not_emit_below_threshold() -> None:
    payload = _msme_input()
    formulated = LLMFormulator().formulate(payload)
    target = next(
        candidate for candidate in formulated.candidates if candidate.kind == "obligation"
    )
    critics = tuple(
        _StaticTargetCritic(role=f"role_{index}", target_candidate_id=target.candidate_id)
        for index in range(5)
    )
    report = MultiCriticEnsemble(critics=critics).evaluate(
        payload,
        candidates=formulated.candidates,
    )

    candidates = critic_consensus_to_obligation_candidates(
        formulator_output=formulated,
        critic_report=report,
        facets=payload.facets,
        intent_text=payload.intent,
        authority_profile_ref="authority_profile.msme_governed",
        consensus_threshold=6,
    )

    assert candidates == ()


def test_critic_consensus_bridge_does_not_emit_speculation_flagged_candidate() -> None:
    payload = _msme_input()
    formulated = LLMFormulator().formulate(payload)
    target = next(
        candidate for candidate in formulated.candidates if candidate.kind == "obligation"
    )
    critics = (
        *(
            _StaticTargetCritic(role=f"role_{index}", target_candidate_id=target.candidate_id)
            for index in range(6)
        ),
        _StaticSpeculationCritic(target_candidate_id=target.candidate_id),
    )
    report = MultiCriticEnsemble(critics=critics).evaluate(
        payload,
        candidates=formulated.candidates,
    )

    candidates = critic_consensus_to_obligation_candidates(
        formulator_output=formulated,
        critic_report=report,
        facets=payload.facets,
        intent_text=payload.intent,
        authority_profile_ref="authority_profile.msme_governed",
        consensus_threshold=6,
    )

    assert candidates == ()


class _StaticTargetCritic(PolicyDesignCritic):
    def __init__(self, *, role: str, target_candidate_id: str) -> None:
        self._envelope = CriticEnvelope(
            critic_role="monitoring",
            substantive_basis="monitoring_lifecycle_drift_simulator",
            critic_version=role,
        )
        self._target_candidate_id = target_candidate_id

    @property
    def envelope(self) -> CriticEnvelope:
        return self._envelope

    def evaluate(
        self,
        context: object,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[CriticVerdict, ...]:
        return (
            CriticVerdict(
                verdict="agree",
                envelope=self.envelope,
                target_candidate_ids=(self._target_candidate_id,),
                message="Candidate is useful as a review-required obligation.",
                failure_modes=(),
            ),
        )


class _StaticSpeculationCritic(PolicyDesignCritic):
    def __init__(self, *, target_candidate_id: str) -> None:
        self._envelope = CriticEnvelope(
            critic_role="adversarial",
            substantive_basis="adversarial_scenario_generator",
            critic_version="speculation",
        )
        self._target_candidate_id = target_candidate_id

    @property
    def envelope(self) -> CriticEnvelope:
        return self._envelope

    def evaluate(
        self,
        context: object,
        candidates: Sequence[FormulatorCandidate],
    ) -> tuple[CriticVerdict, ...]:
        return (
            CriticVerdict(
                verdict="flag_speculation",
                envelope=self.envelope,
                target_candidate_ids=(self._target_candidate_id,),
                message="Consensus is present, but this candidate is speculative.",
                failure_modes=("unsupported_claim",),
            ),
        )
