"""Benchmark authority facade and eval-pack contracts for Scientist."""

from __future__ import annotations

from polisyos.scientist.evals.authority import (
    BenchmarkAuthority,
    BenchmarkAuthorityVerdict,
    PromotionEvidenceRequest,
)
from polisyos.scientist.evals.challenge_factory import (
    AuthoritySpoofingProbe,
    ChallengeFactoryReport,
    ChallengeSeed,
    ChallengeSeedKind,
    ChallengeStatus,
    GeneratedChallenge,
    ParticipationSpeculationProbe,
    PromptInjectionProbe,
    R14AdversarialProbeFixture,
    R14AdversarialProbeResult,
    evaluate_r14_adversarial_probe_fixture,
)

__all__ = [
    "AuthoritySpoofingProbe",
    "BenchmarkAuthority",
    "BenchmarkAuthorityVerdict",
    "ChallengeFactoryReport",
    "ChallengeSeed",
    "ChallengeSeedKind",
    "ChallengeStatus",
    "GeneratedChallenge",
    "ParticipationSpeculationProbe",
    "PromotionEvidenceRequest",
    "PromptInjectionProbe",
    "R14AdversarialProbeFixture",
    "R14AdversarialProbeResult",
    "evaluate_r14_adversarial_probe_fixture",
]
