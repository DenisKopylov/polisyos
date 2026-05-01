from __future__ import annotations

import hashlib

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.challenge_factory import ChallengeStatus
from polisyos.scientist.evals.sentinels import SentinelChallengeCase, SentinelChallengeKind


def _ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        ),
        kind="scientist.challenge_case",
        media_type="application/json",
    )


def test_hidden_sentinel_admission_requires_reviewer_ref() -> None:
    with pytest.raises(ValueError, match="reviewer_refs"):
        SentinelChallengeCase(
            sentinel_id="sentinel_1",
            kind=SentinelChallengeKind.CANARY,
            challenge_ref=_ref("case"),
            expected_detection="Detect forged citation canary.",
            admission_status=ChallengeStatus.APPROVED_FOR_HIDDEN,
        )


def test_reviewed_sentinel_hidden_admission_validates() -> None:
    case = SentinelChallengeCase(
        sentinel_id="sentinel_1",
        kind=SentinelChallengeKind.REGRESSION,
        challenge_ref=_ref("case"),
        expected_detection="Detect forged citation regression.",
        admission_status=ChallengeStatus.APPROVED_FOR_HIDDEN,
        reviewer_refs=[_ref("review")],
    )

    assert case.admission_status is ChallengeStatus.APPROVED_FOR_HIDDEN
