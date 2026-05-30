"""W6.E multi-critic ensemble for candidate-only policy formulation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.scientist.policy_design.critic_contracts import (
    CRITIC_ENSEMBLE_SCHEMA_VERSION,
    CriticConsensusCandidate,
    CriticConsensusReport,
    CriticDiversitySummary,
    CriticDiversityWarning,
    CriticEnsembleReport,
    CriticEnvelope,
    CriticRole,
    CriticSubstantiveBasis,
    CriticVerdict,
    CriticVerdictType,
    PolicyDesignCritic,
    build_critic_candidate,
    critic_verdict,
)
from polisyos.scientist.policy_design.formulator import (
    FormulatorCandidate,
    LLMFormulatorInput,
    fingerprint_payload,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class MultiCriticEnsemble:
    """Run eight W6.E critics and report diversity over their substantive output."""

    def __init__(self, critics: Sequence[PolicyDesignCritic]) -> None:
        self._critics = tuple(critics)
        if not self._critics:
            raise ValueError("multi-critic ensemble requires at least one critic")

    @classmethod
    def default(cls) -> MultiCriticEnsemble:
        """Return the canonical eight-critic W6.E ensemble."""

        from polisyos.scientist.policy_design.critics.adversarial import AdversarialCritic
        from polisyos.scientist.policy_design.critics.affected_person import (
            AffectedPersonCritic,
        )
        from polisyos.scientist.policy_design.critics.data import DataCritic
        from polisyos.scientist.policy_design.critics.equity import EquityCritic
        from polisyos.scientist.policy_design.critics.fiscal import FiscalCritic
        from polisyos.scientist.policy_design.critics.implementation import (
            ImplementationCritic,
        )
        from polisyos.scientist.policy_design.critics.legal import LegalCritic
        from polisyos.scientist.policy_design.critics.monitoring import MonitoringCritic

        return cls(
            critics=(
                LegalCritic(),
                FiscalCritic(),
                EquityCritic(),
                DataCritic(),
                ImplementationCritic(),
                AffectedPersonCritic(),
                AdversarialCritic(),
                MonitoringCritic(),
            )
        )

    @property
    def critics(self) -> tuple[PolicyDesignCritic, ...]:
        """Critics in run order."""

        return self._critics

    def evaluate(
        self,
        context: LLMFormulatorInput,
        *,
        candidates: Sequence[FormulatorCandidate],
    ) -> CriticEnsembleReport:
        """Run all critics and return typed verdicts plus diversity summary."""

        verdicts: list[CriticVerdict] = []
        for critic in self._critics:
            critic_verdicts = critic.evaluate(context, candidates)
            verdicts.extend(_with_verdict_ids(critic.envelope, critic_verdicts))
        diversity = _summarise_diversity(self._critics, verdicts)
        return CriticEnsembleReport(
            run_id=context.run_id,
            verdicts=tuple(verdicts),
            diversity=diversity,
            metadata={
                "critic_roles": [critic.envelope.critic_role for critic in self._critics],
                "substantive_bases": [
                    critic.envelope.substantive_basis for critic in self._critics
                ],
                "capability_phase": "W6.E",
            },
        )


def project_critic_consensus(
    report: CriticEnsembleReport,
    *,
    candidate_ids: Sequence[str],
    consensus_threshold: int = 6,
) -> CriticConsensusReport:
    """Project agree/add-obligation support counts per candidate."""

    supported_verdicts = {"agree", "add_candidate_obligation"}
    rows: list[CriticConsensusCandidate] = []
    for candidate_id in candidate_ids:
        verdicts = [
            verdict
            for verdict in report.verdicts
            if verdict.verdict in supported_verdicts
            and candidate_id in verdict.target_candidate_ids
        ]
        if len(verdicts) < consensus_threshold:
            continue
        rows.append(
            CriticConsensusCandidate(
                candidate_id=candidate_id,
                support_count=len(verdicts),
                consensus_threshold=consensus_threshold,
                verdict_refs=tuple(
                    verdict.verdict_id or f"verdict:{index}"
                    for index, verdict in enumerate(verdicts)
                ),
                verdict_types=tuple(verdict.verdict for verdict in verdicts),
            )
        )
    return CriticConsensusReport(
        run_id=report.run_id,
        consensus_threshold=consensus_threshold,
        candidates=tuple(rows),
    )


def _with_verdict_ids(
    envelope: CriticEnvelope,
    verdicts: Sequence[CriticVerdict],
) -> tuple[CriticVerdict, ...]:
    assigned: list[CriticVerdict] = []
    for index, verdict in enumerate(verdicts):
        if verdict.envelope != envelope:
            raise ValueError(
                "critic verdict envelope does not match the evaluating critic"
            )
        if verdict.verdict_id is not None:
            assigned.append(verdict)
            continue
        verdict_digest = fingerprint_payload(verdict.signature).removeprefix("sha256:")[:16]
        assigned.append(
            verdict.model_copy(
                update={
                    "verdict_id": f"verdict_{envelope.critic_role}_{index}_{verdict_digest}"
                }
            )
        )
    return tuple(assigned)


def _summarise_diversity(
    critics: Sequence[PolicyDesignCritic],
    verdicts: Sequence[CriticVerdict],
) -> CriticDiversitySummary:
    roles = [critic.envelope.critic_role for critic in critics]
    bases = [critic.envelope.substantive_basis for critic in critics]
    signatures = {verdict.signature for verdict in verdicts}
    warnings: list[CriticDiversityWarning] = []
    if len(set(roles)) != len(roles):
        warnings.append(
            CriticDiversityWarning(
                code="critic_role_duplicate",
                message="Critic ensemble has duplicate critic roles.",
            )
        )
    if len(set(bases)) != len(bases):
        warnings.append(
            CriticDiversityWarning(
                code="critic_basis_duplicate",
                message="Critic ensemble has duplicate substantive bases.",
            )
        )
    if len(critics) < 8:
        warnings.append(
            CriticDiversityWarning(
                code="critic_count_below_w6e_floor",
                message="W6.E expects eight critic roles.",
            )
        )
    if _is_identical_all_critic_agree(critics, verdicts):
        warnings.append(
            CriticDiversityWarning(
                code="critic_monoculture_identical_output",
                message=(
                    "All critics emitted the same agree verdict with identical "
                    "substantive output."
                ),
            )
        )
    return CriticDiversitySummary(
        critic_count=len(critics),
        basis_count=len(set(bases)),
        verdict_signature_count=len(signatures),
        warnings=tuple(warnings),
    )


def _is_identical_all_critic_agree(
    critics: Sequence[PolicyDesignCritic],
    verdicts: Sequence[CriticVerdict],
) -> bool:
    if len(critics) < 8:
        return False
    by_role: dict[str, list[CriticVerdict]] = {}
    for verdict in verdicts:
        by_role.setdefault(verdict.envelope.critic_role, []).append(verdict)
    critic_roles = {critic.envelope.critic_role for critic in critics}
    if set(by_role) != critic_roles:
        return False
    role_signatures: list[tuple[Any, ...]] = []
    for role in critic_roles:
        role_verdicts = by_role[role]
        if len(role_verdicts) != 1:
            return False
        verdict = role_verdicts[0]
        if verdict.verdict != "agree":
            return False
        role_signatures.append(verdict.signature)
    return len(set(role_signatures)) == 1


__all__ = [
    "CRITIC_ENSEMBLE_SCHEMA_VERSION",
    "CriticConsensusCandidate",
    "CriticConsensusReport",
    "CriticDiversitySummary",
    "CriticDiversityWarning",
    "CriticEnsembleReport",
    "CriticEnvelope",
    "CriticRole",
    "CriticSubstantiveBasis",
    "CriticVerdict",
    "CriticVerdictType",
    "MultiCriticEnsemble",
    "PolicyDesignCritic",
    "build_critic_candidate",
    "critic_verdict",
    "project_critic_consensus",
]
