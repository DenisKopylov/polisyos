from __future__ import annotations

# ruff: noqa: S101
from polisyos.runtime.quality.memory_influence import MemoryInfluenceRecord
from polisyos.scientist.methods.research_dag.projections import (
    project_memory_influence_records_to_research_dag,
    project_reflexive_memory_events_to_research_dag,
    validate_memory_influence_dag_attribution,
    validate_memory_influence_record_dag_attribution,
)
from polisyos.scientist.orchestration.memory import (
    LessonApplicability,
    build_reflexive_memory_event,
)


def test_memory_events_are_projected_to_research_dag() -> None:
    event = build_reflexive_memory_event(
        run_id="run_target",
        lesson_id="lesson_a",
        action="retrieved",
        applicability=LessonApplicability(
            lesson_id="lesson_a",
            applies=True,
            reasons=["failure_lesson", "domain_scope_match"],
            scope={"domain": "tax"},
        ),
    )

    dag = project_reflexive_memory_events_to_research_dag([event], run_id="run_target")

    assert dag.metadata["memory_influence_status"] == "visible"
    assert validate_memory_influence_dag_attribution([event], dag) == []
    memory_node = next(node for node in dag.nodes if node.metadata.get("lesson_id") == "lesson_a")
    assert memory_node.metadata["memory_influence_visible"] is True
    assert memory_node.metadata["influence_mode"] == "warning_anti_pattern"


def test_missing_memory_dag_attribution_is_reported() -> None:
    event = build_reflexive_memory_event(
        run_id="run_target",
        lesson_id="lesson_a",
        action="retrieved",
        applicability=LessonApplicability(
            lesson_id="lesson_a",
            applies=True,
            reasons=["failure_lesson", "domain_scope_match"],
        ),
    )
    empty_dag = project_reflexive_memory_events_to_research_dag([], run_id="run_target")

    violations = validate_memory_influence_dag_attribution([event], empty_dag)

    assert violations == [f"memory_influence_missing_dag_node:{event.event_id}"]


def test_balanced_memory_influence_records_project_as_future_only_dag_nodes() -> None:
    record = MemoryInfluenceRecord(
        run_id="run_target",
        memory_id="memory-success",
        memory_kind="success",
        source_run_id="run-success",
        source_kind="human_review",
        source_status="verified",
        influence_modes=("guide_search", "guide_review"),
        authoritative_for=("future_search", "future_review"),
        may_not_use_for=(
            "current_claim_evidence",
            "current_claim_closure",
            "claim_support",
            "claim_refutation",
        ),
        scope={"visibility": "domain", "domain": "tax"},
        applicability_reasons=("success_memory", "domain_scope_match"),
        contamination_check_ref="quality_evidence/memory_contamination_pass.json",
    )

    dag = project_memory_influence_records_to_research_dag([record], run_id="run_target")

    assert dag.metadata["memory_influence_status"] == "visible"
    assert validate_memory_influence_record_dag_attribution([record], dag) == []
    memory_node = next(
        node for node in dag.nodes if node.metadata.get("memory_id") == "memory-success"
    )
    assert memory_node.metadata["memory_kind"] == "success"
    assert memory_node.metadata["memory_influence_visible"] is True
    assert memory_node.metadata["influence_modes"] == ["guide_search", "guide_review"]
    assert "current_claim_evidence" in memory_node.metadata["may_not_use_for"]
    assert memory_node.metadata["evidence_slot_admission"] == "forbidden"
