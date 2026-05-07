from __future__ import annotations

from polisyos.scientist.orchestration.memory import LessonApplicability, build_reflexive_memory_event
from polisyos.scientist.methods.research_dag.projections import (
    project_reflexive_memory_events_to_research_dag,
    validate_memory_influence_dag_attribution,
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
