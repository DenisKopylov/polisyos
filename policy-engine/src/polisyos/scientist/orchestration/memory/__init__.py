"""Reflexive memory and failure intelligence contracts."""

from polisyos.scientist.orchestration.memory.applicability import (
    MemoryApplicabilityContext,
    evaluate_lesson_applicability,
    lesson_scope_from_card,
)
from polisyos.scientist.orchestration.memory.authority import (
    MemoryAuthorityContaminationCheck,
    MemoryAuthorityKind,
    MemoryAuthorityRecord,
    assert_memory_authority_for_serious_output,
    build_memory_use_authority_record,
    build_no_memory_abstention_record,
)
from polisyos.scientist.orchestration.memory.consolidation import (
    ConsolidatedLessonSet,
    assert_lesson_can_influence,
    consolidate_lessons,
    revoke_lesson,
)
from polisyos.scientist.orchestration.memory.contamination import (
    MemoryContaminationFinding,
    MemoryContaminationPolicy,
    assert_reusable_memory_clean,
    detect_memory_contamination,
    lesson_payload_for_contamination,
)
from polisyos.scientist.orchestration.memory.failure_lessons import (
    LessonApplicability,
    MemoryVisibility,
    ReflexionRecoveryEvalReport,
    ReflexiveMemoryEvent,
    ReflexiveMemoryFacade,
    apply_reflexive_scope,
    build_reflexion_memory_recovery_eval_report,
    build_reflexion_recovery_eval_report,
    build_reflexive_lesson_scope,
    build_reflexive_memory_event,
    failure_card_to_reflexive_lesson,
)
from polisyos.scientist.orchestration.memory.retrieval import (
    MemoryRetrievalResult,
    MemoryRetrievedLesson,
    format_warning_only_memory_context,
    retrieve_reflexive_lessons,
    retrieve_reflexive_lessons_from_registry,
)

__all__ = [
    "ConsolidatedLessonSet",
    "LessonApplicability",
    "MemoryApplicabilityContext",
    "MemoryAuthorityContaminationCheck",
    "MemoryAuthorityKind",
    "MemoryAuthorityRecord",
    "MemoryContaminationFinding",
    "MemoryContaminationPolicy",
    "MemoryRetrievalResult",
    "MemoryRetrievedLesson",
    "MemoryVisibility",
    "ReflexionRecoveryEvalReport",
    "ReflexiveMemoryEvent",
    "ReflexiveMemoryFacade",
    "apply_reflexive_scope",
    "assert_lesson_can_influence",
    "assert_memory_authority_for_serious_output",
    "assert_reusable_memory_clean",
    "build_memory_use_authority_record",
    "build_no_memory_abstention_record",
    "build_reflexion_memory_recovery_eval_report",
    "build_reflexion_recovery_eval_report",
    "build_reflexive_lesson_scope",
    "build_reflexive_memory_event",
    "consolidate_lessons",
    "detect_memory_contamination",
    "evaluate_lesson_applicability",
    "failure_card_to_reflexive_lesson",
    "format_warning_only_memory_context",
    "lesson_payload_for_contamination",
    "lesson_scope_from_card",
    "retrieve_reflexive_lessons",
    "retrieve_reflexive_lessons_from_registry",
    "revoke_lesson",
]
