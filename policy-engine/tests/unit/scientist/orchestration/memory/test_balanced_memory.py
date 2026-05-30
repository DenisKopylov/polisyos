from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.lessons import LessonKind, LessonQuery, LessonRegistry
from polisyos.scientist.orchestration.memory import (
    BalancedMemoryKind,
    BalancedMemoryScope,
    MemoryApplicabilityContext,
    MemorySourceKind,
    MemoryVisibility,
    ReflexiveMemoryFacade,
    balanced_memory_from_lesson_card,
    balanced_memory_to_lesson_card,
    build_balanced_memory_record,
    evaluate_balanced_memory_applicability,
    format_balanced_memory_context,
    retrieve_balanced_memories,
    retrieve_balanced_memories_from_registry,
    revoke_balanced_memory_record,
)
from polisyos.scientist.orchestration.memory.contamination import MemoryContaminationPolicy


def test_success_and_opportunity_memories_persist_as_balanced_records(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    expires_at = datetime.now(UTC) + timedelta(days=14)
    success = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Primary-source first search produced publishable legal anchors.",
        pattern_type="primary_source_first",
        stage_name="lex_search",
        source_run_id="run-success",
        candidate_hash="candidate-success",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="tax",
            workflow_id="scientist_policy_design",
            expires_at=expires_at,
        ),
        source_kind=MemorySourceKind.DETERMINISTIC_PRODUCER,
        tags=("legal", "search"),
    )
    opportunity = build_balanced_memory_record(
        kind=BalancedMemoryKind.OPPORTUNITY,
        summary="Participation dissent was unresolved; future runs should search counterevidence.",
        pattern_type="unresolved_participation_dissent",
        stage_name="participation_review",
        source_run_id="run-opportunity",
        candidate_hash="candidate-opportunity",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="tax",
            workflow_id="scientist_policy_design",
            expires_at=expires_at,
        ),
        source_kind=MemorySourceKind.HUMAN_REVIEW,
        tags=("participation", "counterevidence"),
    )

    facade.record_balanced_memory(success)
    facade.record_balanced_memory(opportunity)

    stored = registry.query(LessonQuery(domain="tax", task_family="policy", limit=10))
    stored_by_kind = {lesson.kind for lesson in stored}

    assert LessonKind.SUCCESS in stored_by_kind
    assert LessonKind.OPPORTUNITY in stored_by_kind
    round_tripped = [balanced_memory_from_lesson_card(lesson) for lesson in stored]
    assert {memory.kind for memory in round_tripped} == {
        BalancedMemoryKind.SUCCESS,
        BalancedMemoryKind.OPPORTUNITY,
    }
    assert all(
        "current_claim_evidence" in memory.authority_boundary.may_not_use_for
        for memory in round_tripped
    )
    assert all(memory.scope.expires_at == expires_at for memory in round_tripped)


def test_balanced_memory_applicability_uses_scope_expiry_and_revocation() -> None:
    expires_at = datetime.now(UTC) + timedelta(days=7)
    memory = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Domain-specific query expansion improved recall without changing claim truth.",
        pattern_type="query_expansion_success",
        stage_name="scholar_search",
        source_run_id="run-source",
        candidate_hash="candidate-a",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="tax",
            workflow_id="scientist_policy_design",
            expires_at=expires_at,
        ),
        source_kind=MemorySourceKind.DETERMINISTIC_PRODUCER,
    )
    matching_context = MemoryApplicabilityContext(
        run_id="run-target",
        domain="tax",
        workflow_id="scientist_policy_design",
    )

    applicability = evaluate_balanced_memory_applicability(memory, matching_context)

    assert applicability.applies is True
    assert "domain_scope_match" in applicability.reasons
    assert "not_expired" in applicability.reasons
    assert applicability.influence_modes == ("guide_search", "guide_review")

    revoked = revoke_balanced_memory_record(memory, reason="later contradicted by audit")

    revoked_applicability = evaluate_balanced_memory_applicability(revoked, matching_context)

    assert revoked_applicability.applies is False
    assert "revoked" in revoked_applicability.reasons


def test_llm_candidate_memory_is_recordable_but_not_applicable_for_influence() -> None:
    memory = build_balanced_memory_record(
        kind=BalancedMemoryKind.OPPORTUNITY,
        summary="The drafter speculated that procurement data might reveal hidden costs.",
        pattern_type="speculative_procurement_data_gap",
        stage_name="draft_review",
        source_run_id="run-source",
        candidate_hash="candidate-llm",
        scope=BalancedMemoryScope(visibility=MemoryVisibility.DOMAIN, domain="procurement"),
        source_kind=MemorySourceKind.LLM_CANDIDATE,
    )

    applicability = evaluate_balanced_memory_applicability(
        memory,
        MemoryApplicabilityContext(run_id="run-target", domain="procurement"),
    )

    assert applicability.applies is False
    assert "llm_candidate_unverified" in applicability.reasons
    assert applicability.influence_modes == ()


def test_contaminated_balanced_memory_is_blocked_before_persistence(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    memory = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Hidden fixture answer must never become reusable success memory.",
        pattern_type="contaminated_success",
        stage_name="semantic_eval",
        source_run_id="run-source",
        candidate_hash="candidate-contaminated",
        scope=BalancedMemoryScope(visibility=MemoryVisibility.DOMAIN, domain="tax"),
        source_kind=MemorySourceKind.DETERMINISTIC_PRODUCER,
        metadata={"hidden_suite_id": "hidden-suite"},
    )

    with pytest.raises(ValueError, match="reusable memory contamination"):
        facade.record_balanced_memory(memory, hidden_suite_ids={"hidden-suite"})


def test_balanced_memory_retrieval_returns_all_kinds_as_future_influence(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    expires_at = datetime.now(UTC) + timedelta(days=14)
    shared_scope = BalancedMemoryScope(
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id="scientist_policy_design",
        expires_at=expires_at,
    )
    for memory in (
        build_balanced_memory_record(
            kind=BalancedMemoryKind.FAILURE,
            summary="Prior run over-promoted a claim before legal competence was checked.",
            pattern_type="legal_competence_gap",
            stage_name="lex_review",
            source_run_id="run-failure",
            candidate_hash="candidate-failure",
            scope=shared_scope,
            source_kind=MemorySourceKind.RUNTIME_QUALITY,
            anti_patterns=("P15",),
        ),
        build_balanced_memory_record(
            kind=BalancedMemoryKind.SUCCESS,
            summary="Primary-source-first search found admissible legal anchors quickly.",
            pattern_type="primary_source_first_success",
            stage_name="lex_search",
            source_run_id="run-success",
            candidate_hash="candidate-success",
            scope=shared_scope,
            source_kind=MemorySourceKind.HUMAN_REVIEW,
            tags=("search",),
        ),
        build_balanced_memory_record(
            kind=BalancedMemoryKind.OPPORTUNITY,
            summary="Unresolved participation dissent should drive future acquisition.",
            pattern_type="participation_dissent_opportunity",
            stage_name="participation_review",
            source_run_id="run-opportunity",
            candidate_hash="candidate-opportunity",
            scope=shared_scope,
            source_kind=MemorySourceKind.HUMAN_REVIEW,
            tags=("acquisition",),
        ),
    ):
        facade.record_balanced_memory(memory)

    result = retrieve_balanced_memories_from_registry(
        registry,
        LessonQuery(domain="tax", task_family="policy", limit=3),
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            workflow_id="scientist_policy_design",
        ),
        limit=3,
    )

    assert [item.memory.kind for item in result.retrieved_memories] == [
        BalancedMemoryKind.FAILURE,
        BalancedMemoryKind.SUCCESS,
        BalancedMemoryKind.OPPORTUNITY,
    ]
    assert result.metadata["balance_status"] == "balanced"
    assert result.metadata["retrieved_kind_counts"] == {
        "failure": 1,
        "success": 1,
        "opportunity": 1,
    }
    modes_by_kind = {
        item.memory.kind: item.applicability.influence_modes for item in result.retrieved_memories
    }
    assert modes_by_kind[BalancedMemoryKind.FAILURE] == (
        "warning_anti_pattern",
        "guide_review",
    )
    assert modes_by_kind[BalancedMemoryKind.SUCCESS] == ("guide_search", "guide_review")
    assert modes_by_kind[BalancedMemoryKind.OPPORTUNITY] == (
        "suggest_acquisition",
        "guide_review",
    )
    assert all(
        "current_claim_evidence" in event.metadata["authority_boundary"]["may_not_use_for"]
        for event in result.events
        if event.action == "retrieved"
    )

    rendered = format_balanced_memory_context(result)

    assert "not claim evidence" in rendered
    assert "kind=success" in rendered
    assert "mode=guide_search" in rendered
    assert "mode=suggest_acquisition" in rendered


def test_balanced_memory_retrieval_rejects_scope_expiry_revocation_and_contamination() -> None:
    now = datetime.now(UTC)
    matching_scope = BalancedMemoryScope(
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        expires_at=now + timedelta(days=1),
    )
    out_of_scope = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="A success in procurement must not steer tax-policy search.",
        pattern_type="out_of_scope_success",
        stage_name="search",
        source_run_id="run-success",
        candidate_hash="candidate-success",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="procurement",
            expires_at=now + timedelta(days=1),
        ),
        source_kind=MemorySourceKind.HUMAN_REVIEW,
    )
    expired = build_balanced_memory_record(
        kind=BalancedMemoryKind.OPPORTUNITY,
        summary="Old opportunity should expire before influencing future acquisition.",
        pattern_type="expired_opportunity",
        stage_name="acquisition",
        source_run_id="run-expired",
        candidate_hash="candidate-expired",
        scope=matching_scope,
        source_kind=MemorySourceKind.HUMAN_REVIEW,
    )
    revoked = revoke_balanced_memory_record(
        build_balanced_memory_record(
            kind=BalancedMemoryKind.FAILURE,
            summary="Revoked failure should not make the system conservative.",
            pattern_type="revoked_failure",
            stage_name="review",
            source_run_id="run-revoked",
            candidate_hash="candidate-revoked",
            scope=matching_scope,
            source_kind=MemorySourceKind.RUNTIME_QUALITY,
        ),
        reason="later audit cleared the issue",
    )
    contaminated = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Hidden benchmark answer must not become reusable success memory.",
        pattern_type="contaminated_success",
        stage_name="semantic_eval",
        source_run_id="run-contaminated",
        candidate_hash="candidate-contaminated",
        scope=matching_scope,
        source_kind=MemorySourceKind.HUMAN_REVIEW,
        metadata={"hidden_suite_id": "hidden-suite"},
    )

    result = retrieve_balanced_memories(
        [
            balanced_memory_to_lesson_card(out_of_scope),
            balanced_memory_to_lesson_card(expired),
            balanced_memory_to_lesson_card(revoked),
            balanced_memory_to_lesson_card(contaminated),
        ],
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            now=now + timedelta(days=2),
        ),
        contamination_policy=MemoryContaminationPolicy(hidden_suite_ids={"hidden-suite"}),
        limit=10,
    )

    assert result.retrieved_memories == []
    rejected_by_kind: dict[BalancedMemoryKind, set[str]] = {}
    for applicability in result.rejected_memories:
        rejected_by_kind.setdefault(applicability.memory_kind, set()).update(applicability.reasons)
    assert "domain_scope_mismatch" in rejected_by_kind[BalancedMemoryKind.SUCCESS]
    assert "expired" in rejected_by_kind[BalancedMemoryKind.OPPORTUNITY]
    assert "revoked" in rejected_by_kind[BalancedMemoryKind.FAILURE]
    assert any(
        "contaminated_hidden_eval" in applicability.reasons
        for applicability in result.rejected_memories
    )
