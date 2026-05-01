from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.memory import (
    MemoryContaminationPolicy,
    MemoryVisibility,
    ReflexiveMemoryFacade,
    failure_card_to_reflexive_lesson,
)
from polisyos.scientist.memory.contamination import lesson_payload_for_contamination
from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard
from polisyos.scientist.search.lessons import LessonKind, LessonQuery, LessonRegistry


def test_failure_card_becomes_scoped_retrieval_lesson() -> None:
    failure = TypedFailureCard(
        judge_name="citation_gate",
        failure_type="missing_primary_source",
        severity=FailureSeverity.BLOCKER,
        description="The candidate cited a secondary source for a legal claim.",
        remediation_hint="Fetch and verify the primary legal source.",
    )

    lesson = failure_card_to_reflexive_lesson(
        failure,
        candidate_hash="candidate_a",
        stage_name="evidence_gate",
        fidelity_level=2,
        source_run_id="source_run",
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id="scientist_policy_verified",
        method_family="legal_research",
    )

    assert lesson.kind is LessonKind.FAILURE
    assert lesson.anti_patterns == ["missing_primary_source"]
    assert lesson.remediation_hint == "Fetch and verify the primary legal source."
    assert lesson.metadata["memory_scope"]["workflow_id"] == "scientist_policy_verified"
    assert lesson.metadata["memory_scope"]["method_family"] == "legal_research"


def test_facade_records_clean_lessons_and_blocks_contaminated_lessons(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    clean_failure = TypedFailureCard(
        judge_name="evidence_gate",
        failure_type="unsupported_claim",
        severity=FailureSeverity.WARNING,
        description="The policy claim had no source snippets.",
    )

    facade.record_failure_card(
        clean_failure,
        candidate_hash="candidate_a",
        stage_name="evidence_gate",
        fidelity_level=1,
        source_run_id="source_run",
        domain="tax",
    )

    assert registry.query(LessonQuery(domain="tax", task_family="policy"))

    contaminated = failure_card_to_reflexive_lesson(
        clean_failure,
        candidate_hash="candidate_b",
        stage_name="evidence_gate",
        fidelity_level=1,
        source_run_id="source_run",
        domain="tax",
    ).model_copy(update={"metadata": {"hidden_suite_id": "hidden-suite"}})
    policy = MemoryContaminationPolicy(hidden_suite_ids={"hidden-suite"})
    assert "hidden-suite" in str(lesson_payload_for_contamination(contaminated))
    with pytest.raises(ValueError, match="reusable memory contamination"):
        facade.record_lesson(
            contaminated,
            hidden_suite_ids=policy.hidden_suite_ids,
        )


def test_facade_retrieve_coerces_context_and_applies_contamination_policy(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    failure = TypedFailureCard(
        judge_name="evidence_gate",
        failure_type="unsupported_claim",
        severity=FailureSeverity.WARNING,
        description="The policy claim had no source snippets.",
    )
    facade.record_failure_card(
        failure,
        candidate_hash="candidate_a",
        stage_name="evidence_gate",
        fidelity_level=1,
        source_run_id="source_run",
        domain="tax",
    )

    result = facade.retrieve(
        LessonQuery(domain="tax", task_family="policy"),
        context={"run_id": "run_target", "domain": "tax"},
    )

    assert result.retrieved_lessons
    assert result.retrieved_lessons[0].applicability.reasons
