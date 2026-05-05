from __future__ import annotations

import hashlib
import json

import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.challenge_factory import (
    ChallengeClass,
    ChallengeSeed,
    ChallengeSeedKind,
    ChallengeStatus,
    export_public_challenge_factory_report,
    generate_challenge_from_failure_card,
    generate_challenge_from_seed,
    generate_challenge_report_from_failure_cards,
    generate_challenge_report_from_seeds,
    mutate_generated_challenge,
    promote_generated_challenge,
    register_challenge_pack_with_benchmark_registry,
)
from polisyos.scientist.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard


def _ref(seed: str, *, kind: str = "scientist.challenge_case") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        ),
        kind=kind,
        media_type="application/json",
    )


def _failure_card(**metadata) -> TypedFailureCard:
    return TypedFailureCard(
        judge_name="citation_faithfulness",
        failure_type="forged_citation",
        severity=FailureSeverity.BLOCKER,
        description="The report cited a source that does not support the claim.",
        remediation_hint="Build a forged-citation challenge before promotion.",
        evidence_ref=_ref("failure", kind="scientist.failure_card"),
        metadata=metadata,
    )


def test_failure_card_generates_review_required_candidate_challenge() -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )

    assert challenge.status is ChallengeStatus.REVIEW_REQUIRED
    assert challenge.challenge_class == ChallengeClass.FORGED_CITATION.value
    assert challenge.source_failure_refs
    assert challenge.lineage_key
    assert "forged_citation" in challenge.expected_failure_mode


def test_challenge_report_generation_records_private_public_rejections() -> None:
    report = generate_challenge_report_from_failure_cards(
        run_id="run_25",
        failure_cards=[_failure_card(private_data=True)],
        prompt_or_case_refs=[_ref("case")],
        target_visibility="public",
    )

    assert report.generated == []
    assert report.rejected_reasons
    assert "private data" in report.rejected_reasons[0]


def test_near_miss_and_policy_risk_seeds_generate_candidate_challenges() -> None:
    near_miss = ChallengeSeed(
        seed_id="near_miss_citation_1",
        seed_kind=ChallengeSeedKind.NEAR_MISS,
        challenge_class=ChallengeClass.FORGED_CITATION,
        prompt_or_case_ref=_ref("near-miss-case"),
        expected_failure_mode="Citation looked valid but failed snippet support.",
        summary="Near miss in citation validation.",
    )
    policy_risk = ChallengeSeed(
        seed_id="policy_risk_budget_1",
        seed_kind=ChallengeSeedKind.POLICY_DOMAIN_RISK,
        challenge_class=ChallengeClass.BUDGET_INFEASIBILITY,
        prompt_or_case_ref=_ref("policy-risk-case"),
        expected_failure_mode="Budget cap is impossible under stated constraints.",
        summary="Domain risk for infeasible budget claims.",
    )

    report = generate_challenge_report_from_seeds(
        run_id="run_25",
        seeds=[near_miss, policy_risk],
    )

    assert [item.source_seed_kind for item in report.generated] == [
        ChallengeSeedKind.NEAR_MISS,
        ChallengeSeedKind.POLICY_DOMAIN_RISK,
    ]
    assert {item.challenge_class for item in report.generated} == {
        ChallengeClass.FORGED_CITATION.value,
        ChallengeClass.BUDGET_INFEASIBILITY.value,
    }


def test_private_seed_cannot_generate_public_challenge() -> None:
    seed = ChallengeSeed(
        seed_id="tenant_case",
        seed_kind=ChallengeSeedKind.POLICY_DOMAIN_RISK,
        challenge_class=ChallengeClass.LEGAL_EXCEPTION,
        prompt_or_case_ref=_ref("private-case"),
        expected_failure_mode="Tenant-specific legal exception.",
        summary="Private tenant source.",
        private_data=True,
    )

    report = generate_challenge_report_from_seeds(
        run_id="run_25",
        seeds=[seed],
        target_visibility="public",
    )

    assert report.generated == []
    assert "private data" in report.rejected_reasons[0]


def test_mutated_challenge_resets_review_and_preserves_lineage() -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )
    reviewed = promote_generated_challenge(
        challenge,
        status=ChallengeStatus.APPROVED_FOR_PRIVATE,
        reviewer_refs=[_ref("review", kind="scientist.human_review_decision")],
    )

    mutated = mutate_generated_challenge(
        reviewed,
        mutation_strategy="swap_supporting_source_with_contradiction",
    )

    assert mutated.status is ChallengeStatus.REVIEW_REQUIRED
    assert mutated.reviewer_refs == []
    assert mutated.metadata["parent_challenge_id"] == reviewed.challenge_id
    assert mutated.lineage_key != reviewed.lineage_key


def test_generated_hidden_challenge_cannot_promote_without_review_ref() -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )

    with pytest.raises(ValueError, match="reviewer_refs"):
        promote_generated_challenge(challenge, status=ChallengeStatus.APPROVED_FOR_HIDDEN)


def test_unreviewed_generated_challenge_cannot_register_as_hidden(tmp_path) -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )
    registry = BenchmarkRegistry(tmp_path / "benchmarks")

    with pytest.raises(ValueError, match="hidden without review"):
        register_challenge_pack_with_benchmark_registry(
            registry,
            split_type="hidden_holdout",
            pack_ref=_ref("hidden-pack", kind="scientist.benchmark_pack"),
            challenges=[challenge],
            family="policy_design",
        )


def test_reviewed_challenge_registration_tracks_lineage(tmp_path) -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )
    reviewed = promote_generated_challenge(
        challenge,
        status=ChallengeStatus.APPROVED_FOR_HIDDEN,
        reviewer_refs=[_ref("review", kind="scientist.human_review_decision")],
    )
    registry = BenchmarkRegistry(tmp_path / "benchmarks")
    register_challenge_pack_with_benchmark_registry(
        registry,
        split_type="hidden_holdout",
        pack_ref=_ref("hidden-pack", kind="scientist.benchmark_pack"),
        challenges=[reviewed],
        family="policy_design",
        loop_id="loop-a",
        suite_id="hidden-challenges-v1",
    )

    entry = registry.snapshot().entries[0]
    lineage = entry.metadata["challenge_pack_lineage"]
    assert lineage["source_challenge_ids"] == [reviewed.challenge_id]
    assert lineage["source_failure_ref_ids"] == [str(_ref("failure").artifact_id)]
    assert entry.metadata["review_before_hidden"] is True


def test_reviewed_private_challenge_can_register_as_private_pack(tmp_path) -> None:
    challenge = generate_challenge_from_seed(
        ChallengeSeed(
            seed_id="policy_risk_private",
            seed_kind=ChallengeSeedKind.POLICY_DOMAIN_RISK,
            challenge_class=ChallengeClass.LEGAL_EXCEPTION,
            prompt_or_case_ref=_ref("private-case"),
            expected_failure_mode="Private legal exception must be detected.",
            summary="Private policy-domain risk.",
            private_data=True,
        ),
        run_id="run_25",
        target_visibility="private",
    )
    reviewed_private = promote_generated_challenge(
        challenge,
        status=ChallengeStatus.APPROVED_FOR_PRIVATE,
        reviewer_refs=[_ref("review", kind="scientist.human_review_decision")],
    )
    registry = BenchmarkRegistry(tmp_path / "benchmarks")

    register_challenge_pack_with_benchmark_registry(
        registry,
        split_type="private",
        pack_ref=_ref("private-pack", kind="scientist.benchmark_pack"),
        challenges=[reviewed_private],
        family="policy_design",
        loop_id="loop-a",
        suite_id="private-challenges-v1",
    )

    entry = registry.snapshot().entries[0]
    assert entry.split_type == "private"
    assert entry.visibility == "private"
    assert entry.metadata["challenge_pack_lineage"]["statuses"] == ["approved_for_private"]


def test_public_export_rejects_hidden_answer_canary() -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    ).model_copy(update={"expected_failure_mode": "contains HIDDEN_CANARY_TOKEN"})
    report = generate_challenge_report_from_failure_cards(
        run_id="run_25",
        failure_cards=[],
        prompt_or_case_refs=[_ref("case")],
    ).model_copy(update={"generated": [challenge]})

    with pytest.raises(ValueError, match="canary"):
        export_public_challenge_factory_report(report, canary_tokens={"HIDDEN_CANARY_TOKEN"})


def test_public_export_is_ref_free_summary() -> None:
    challenge = generate_challenge_from_failure_card(
        _failure_card(),
        run_id="run_25",
        prompt_or_case_ref=_ref("case"),
    )
    report = generate_challenge_report_from_failure_cards(
        run_id="run_25",
        failure_cards=[],
        prompt_or_case_refs=[_ref("case")],
    ).model_copy(update={"generated": [challenge]})

    exported = export_public_challenge_factory_report(report)
    rendered = json.dumps(exported, sort_keys=True)

    assert "sha256:" not in rendered
    assert exported["challenge_classes"] == [ChallengeClass.FORGED_CITATION.value]
