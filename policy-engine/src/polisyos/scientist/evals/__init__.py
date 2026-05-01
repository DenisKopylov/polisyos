"""Benchmark authority facade and eval-pack contracts for Scientist."""

from __future__ import annotations

from polisyos.scientist.evals.authority import (
    BenchmarkAuthority,
    BenchmarkAuthorityVerdict,
    PromotionEvidenceRequest,
)
from polisyos.scientist.evals.challenge_factory import (
    ChallengeFactoryReport,
    ChallengeSeed,
    ChallengeSeedKind,
    ChallengeStatus,
    GeneratedChallenge,
)

__all__ = [
    "BenchmarkAuthority",
    "BenchmarkAuthorityVerdict",
    "ChallengeFactoryReport",
    "ChallengeSeed",
    "ChallengeSeedKind",
    "ChallengeStatus",
    "GeneratedChallenge",
    "PromotionEvidenceRequest",
]
