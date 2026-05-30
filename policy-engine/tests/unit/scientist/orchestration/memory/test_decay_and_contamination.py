from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
)
from polisyos.scientist.orchestration.memory import (
    BalancedMemoryBiasPolicy,
    BalancedMemoryDecayPolicy,
    BalancedMemoryKind,
    BalancedMemoryScope,
    MemoryApplicabilityContext,
    MemoryScopeRevocationTrigger,
    MemorySourceKind,
    MemoryVisibility,
    ReflexiveMemoryFacade,
    apply_reflexive_scope,
    balanced_memory_from_lesson_card,
    balanced_memory_to_lesson_card,
    build_balanced_memory_record,
    retrieve_balanced_memories,
    retrieve_reflexive_lessons,
)

if TYPE_CHECKING:
    from pathlib import Path

NOW = datetime(2026, 1, 15, tzinfo=UTC)


def _memory(
    *,
    kind: BalancedMemoryKind,
    memory_id: str,
    pattern_type: str,
    created_at: datetime = NOW,
    confidence: float = 1.0,
    expires_at: datetime | None = None,
    source_kind: MemorySourceKind = MemorySourceKind.RUNTIME_QUALITY,
    workflow_id: str | None = "scientist_policy_design",
) -> object:
    memory = build_balanced_memory_record(
        kind=kind,
        summary=f"{kind.value} memory for {pattern_type}",
        pattern_type=pattern_type,
        stage_name="memory_review",
        source_run_id=f"source-{memory_id}",
        candidate_hash=f"candidate-{memory_id}",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="tax",
            workflow_id=workflow_id,
            expires_at=expires_at,
        ),
        source_kind=source_kind,
        confidence=confidence,
        created_at=created_at,
    )
    return memory.model_copy(update={"memory_id": memory_id, "created_at": created_at})


def test_effective_ttl_blocks_memory_without_explicit_expiry() -> None:
    memory = _memory(
        kind=BalancedMemoryKind.SUCCESS,
        memory_id="memory-success-old",
        pattern_type="old_success",
        created_at=NOW - timedelta(days=31),
    )
    result = retrieve_balanced_memories(
        [balanced_memory_to_lesson_card(memory)],
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            workflow_id="scientist_policy_design",
            now=NOW,
        ),
        decay_policy=BalancedMemoryDecayPolicy(
            default_ttl_days=30,
            half_life_days=90,
            minimum_influence_weight=0.0,
        ),
    )

    assert result.retrieved_memories == []
    rejected = result.rejected_memories[0]
    assert rejected.expires_at == NOW - timedelta(days=1)
    assert "expired_ttl" in rejected.reasons
    assert result.metadata["decay_summary"]["expired_count"] == 1


def test_warning_only_failure_lesson_older_than_default_ttl_cannot_influence() -> None:
    lesson = apply_reflexive_scope(
        LessonCard(
            lesson_id="lesson-old-failure",
            kind=LessonKind.FAILURE,
            summary="Old failure warning should fall out of current influence.",
            failure_type="old_failure_warning",
            stage_name="memory_review",
            fidelity_level=1,
            candidate_hash="candidate-old-failure",
            source_run_id="source-old-failure",
            created_at=NOW - timedelta(days=31),
            domain="tax",
            task_family="policy",
            confidence=1.0,
        ),
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id="scientist_policy_design",
    )

    result = retrieve_reflexive_lessons(
        [lesson],
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            workflow_id="scientist_policy_design",
            now=NOW,
        ),
        decay_policy=BalancedMemoryDecayPolicy(
            default_ttl_days=30,
            half_life_days=90,
            minimum_influence_weight=0.0,
        ),
    )

    assert result.retrieved_lessons == []
    rejected = result.rejected_lessons[0]
    assert rejected.expires_at == NOW - timedelta(days=1)
    assert "expired_ttl" in rejected.reasons


def test_decay_removes_low_value_pattern_before_ttl_boundary() -> None:
    memory = _memory(
        kind=BalancedMemoryKind.FAILURE,
        memory_id="memory-failure-low-value",
        pattern_type="low_value_failure",
        created_at=NOW - timedelta(days=60),
        confidence=0.35,
        expires_at=NOW + timedelta(days=30),
    )
    result = retrieve_balanced_memories(
        [balanced_memory_to_lesson_card(memory)],
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            workflow_id="scientist_policy_design",
            now=NOW,
        ),
        decay_policy=BalancedMemoryDecayPolicy(
            default_ttl_days=365,
            half_life_days=20,
            minimum_influence_weight=0.10,
        ),
    )

    rejected = result.rejected_memories[0]
    assert rejected.applies is False
    assert rejected.influence_weight < 0.10
    assert "decayed_below_threshold" in rejected.reasons
    assert result.metadata["decay_summary"]["decayed_count"] == 1


def test_scope_revocation_trigger_invalidates_only_matching_rule_scope(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    matching = _memory(
        kind=BalancedMemoryKind.FAILURE,
        memory_id="memory-legal-gap",
        pattern_type="legal_competence_gap",
    )
    unaffected = _memory(
        kind=BalancedMemoryKind.SUCCESS,
        memory_id="memory-search-success",
        pattern_type="primary_source_success",
    )
    facade.record_balanced_memory(matching)
    facade.record_balanced_memory(unaffected)

    trigger = MemoryScopeRevocationTrigger(
        trigger_id="rule-change-legal-2026-01",
        reason="legal competence rule tightened",
        changed_rule_ref="rules/legal-competence",
        previous_rule_version="1.0",
        new_rule_version="1.1",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="tax",
            workflow_id="scientist_policy_design",
        ),
        affected_pattern_types=("legal_competence_gap",),
        changed_at=NOW,
    )

    events = facade.revoke_balanced_scope(
        trigger,
        query=LessonQuery(domain="tax", task_family="policy", limit=10),
    )
    result = facade.retrieve_balanced(
        LessonQuery(domain="tax", task_family="policy", limit=10),
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            workflow_id="scientist_policy_design",
            now=NOW,
        ),
    )

    assert [event.action for event in events] == ["revoked"]
    assert events[0].lesson_id == "memory-legal-gap"
    assert events[0].metadata["scope_revocation_trigger"]["trigger_id"] == trigger.trigger_id
    assert [item.memory.memory_id for item in result.retrieved_memories] == [
        "memory-search-success"
    ]


def test_recorded_balanced_memory_persists_contamination_check_status(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = LessonRegistry(root=tmp_path / "lessons", store=store)
    facade = ReflexiveMemoryFacade(registry)
    memory = _memory(
        kind=BalancedMemoryKind.OPPORTUNITY,
        memory_id="memory-opportunity-clean",
        pattern_type="counterevidence_opportunity",
        source_kind=MemorySourceKind.HUMAN_REVIEW,
    )

    facade.record_balanced_memory(memory, canary_tokens={"hidden-canary-token"})

    stored = registry.query(LessonQuery(domain="tax", task_family="policy", limit=1))
    round_tripped = balanced_memory_from_lesson_card(stored[0])
    assert round_tripped.contamination_checked is True
    assert round_tripped.contamination_findings == ()


def test_conservative_bias_metrics_track_failure_heavy_memory_posture() -> None:
    failure_a = _memory(
        kind=BalancedMemoryKind.FAILURE,
        memory_id="memory-failure-a",
        pattern_type="risk_overprediction_a",
    )
    failure_b = _memory(
        kind=BalancedMemoryKind.FAILURE,
        memory_id="memory-failure-b",
        pattern_type="risk_overprediction_b",
    )
    expired_opportunity = _memory(
        kind=BalancedMemoryKind.OPPORTUNITY,
        memory_id="memory-opportunity-expired",
        pattern_type="suppressed_opportunity",
        created_at=NOW - timedelta(days=45),
    )

    result = retrieve_balanced_memories(
        [
            balanced_memory_to_lesson_card(failure_a),
            balanced_memory_to_lesson_card(failure_b),
            balanced_memory_to_lesson_card(expired_opportunity),
        ],
        context=MemoryApplicabilityContext(
            run_id="run-target",
            domain="tax",
            workflow_id="scientist_policy_design",
            now=NOW,
        ),
        decay_policy=BalancedMemoryDecayPolicy(default_ttl_days=30),
        bias_policy=BalancedMemoryBiasPolicy(
            risk_overprediction_threshold=0.60,
            opportunity_suppression_threshold=0.50,
            excessive_blocker_threshold=0.50,
        ),
        limit=10,
    )

    metrics = result.metadata["conservative_bias_metrics"]
    assert metrics["risk_overprediction_rate"] == 1.0
    assert metrics["opportunity_suppression_rate"] == 1.0
    assert metrics["excessive_blocker_rate"] == 1.0
    assert set(metrics["warnings"]) == {
        "risk_overprediction",
        "opportunity_suppression",
        "excessive_blocker_rate",
    }
