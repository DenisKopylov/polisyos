from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scientist.evals.challenge_packs import (
    ChallengePack,
    ChallengePackKind,
    challenge_pack_is_expired,
    next_rotation_due_at,
)

from .test_authority import _ref


def test_rotating_challenge_pack_expires_on_schedule() -> None:
    created_at = datetime.now(UTC) - timedelta(days=31)
    pack = ChallengePack(
        pack_id="rotating",
        kind=ChallengePackKind.ROTATING,
        artifact_ref=_ref("rotating-pack"),
        created_at=created_at,
        rotation_days=30,
    )

    assert next_rotation_due_at(pack) == created_at + timedelta(days=30)
    assert challenge_pack_is_expired(pack) is True
