from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scientist.evals.challenge_factory import (
    ChallengeStatus,
    generate_challenge_from_failure_card,
    promote_generated_challenge,
)
from polisyos.scientist.evals.challenge_packs import ChallengePack, ChallengePackKind
from polisyos.scientist.evals.rotation import (
    RotatingChallengePackStatus,
    build_challenge_pack_lineage,
    dedupe_challenge_lineage,
    validate_fresh_rotating_challenge_evidence,
)
from polisyos.scientist.methods.search.failure_cards import FailureSeverity, TypedFailureCard

from .test_challenge_factory import _ref


def _reviewed_challenge():
    failure = TypedFailureCard(
        judge_name="freshness",
        failure_type="stale_source",
        severity=FailureSeverity.BLOCKER,
        description="Source is stale.",
        remediation_hint="Use a stale-source challenge.",
        evidence_ref=_ref("failure", kind="scientist.failure_card"),
    )
    challenge = generate_challenge_from_failure_card(
        failure,
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )
    return promote_generated_challenge(
        challenge,
        status=ChallengeStatus.APPROVED_FOR_PRIVATE,
        reviewer_refs=[_ref("review", kind="scientist.human_review_decision")],
    )


def test_fresh_rotating_lineage_satisfies_near_frontier_requirement() -> None:
    pack = ChallengePack(
        pack_id="rotating-v1",
        kind=ChallengePackKind.ROTATING,
        artifact_ref=_ref("rotating-pack", kind="scientist.benchmark_pack"),
        created_at=datetime.now(UTC),
        rotation_days=30,
    )
    lineage = build_challenge_pack_lineage(pack, [_reviewed_challenge()])

    assert validate_fresh_rotating_challenge_evidence([lineage], near_frontier=True) == []


def test_expired_rotating_pack_blocks_near_frontier_promotion() -> None:
    pack = ChallengePack(
        pack_id="rotating-v1",
        kind=ChallengePackKind.ROTATING,
        artifact_ref=_ref("rotating-pack", kind="scientist.benchmark_pack"),
        created_at=datetime.now(UTC) - timedelta(days=45),
        rotation_days=30,
    )
    lineage = build_challenge_pack_lineage(
        pack,
        [_reviewed_challenge()],
        status=RotatingChallengePackStatus.ACTIVE,
    )

    blockers = validate_fresh_rotating_challenge_evidence([lineage], near_frontier=True)

    assert blockers == ["rotating_challenge_expired:rotating-v1"]


def test_duplicate_challenge_lineage_is_deduped() -> None:
    pack = ChallengePack(
        pack_id="rotating-v1",
        kind=ChallengePackKind.ROTATING,
        artifact_ref=_ref("rotating-pack", kind="scientist.benchmark_pack"),
    )
    challenge = _reviewed_challenge()
    older = build_challenge_pack_lineage(
        pack.model_copy(update={"created_at": datetime.now(UTC) - timedelta(days=1)}),
        [challenge],
    )
    newer = older.model_copy(update={"created_at": datetime.now(UTC)})

    assert dedupe_challenge_lineage([older, newer]) == [newer]
