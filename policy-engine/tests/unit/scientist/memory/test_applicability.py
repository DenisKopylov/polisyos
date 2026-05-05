from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from polisyos.scientist.memory import (
    LessonApplicability,
    MemoryApplicabilityContext,
    MemoryVisibility,
    apply_reflexive_scope,
    evaluate_lesson_applicability,
)
from polisyos.scientist.search.lessons import LessonCard, LessonKind
from pydantic import ValidationError


def _lesson(**updates) -> LessonCard:
    base = LessonCard(
        lesson_id="lesson_a",
        kind=LessonKind.FAILURE,
        summary="Candidate failed because citation support was absent.",
        failure_type="missing_citation_support",
        stage_name="citation_gate",
        fidelity_level=2,
        candidate_hash="candidate_a",
        source_run_id="source_run",
        task_family="policy",
        domain="tax",
        origin_tenant_hash="tenant_a",
        anti_patterns=["missing_citation_support"],
        remediation_hint="Fetch primary source before promotion.",
    )
    return base.model_copy(update=updates)


def test_domain_scoped_failure_lesson_is_applicable_with_reasons() -> None:
    expires_at = datetime.now(UTC) + timedelta(days=7)
    lesson = apply_reflexive_scope(
        _lesson(),
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        workflow_id="scientist_policy_design",
        method_family="deep_research",
        expires_at=expires_at,
    )
    context = MemoryApplicabilityContext(
        run_id="run_target",
        domain="tax",
        workflow_id="scientist_policy_design",
        method_family="deep_research",
    )

    applicability = evaluate_lesson_applicability(lesson, context)

    assert applicability.applies is True
    assert "domain_scope_match" in applicability.reasons
    assert "workflow_id_match" in applicability.reasons
    assert "method_family_match" in applicability.reasons
    assert applicability.expires_at == expires_at


def test_expired_or_out_of_scope_lesson_is_non_applicable() -> None:
    lesson = apply_reflexive_scope(
        _lesson(),
        visibility=MemoryVisibility.DOMAIN,
        domain="tax",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    context = MemoryApplicabilityContext(run_id="run_target", domain="health")

    applicability = evaluate_lesson_applicability(lesson, context)

    assert applicability.applies is False
    assert "expired" in applicability.reasons
    assert "domain_scope_mismatch" in applicability.reasons


def test_tenant_and_local_run_scope_isolate_cross_run_transfer() -> None:
    tenant_lesson = apply_reflexive_scope(
        _lesson(),
        visibility=MemoryVisibility.TENANT,
        tenant_hash="tenant_a",
        domain="tax",
    )
    wrong_tenant = MemoryApplicabilityContext(
        run_id="run_target",
        tenant_hash="tenant_b",
        domain="tax",
    )

    tenant_applicability = evaluate_lesson_applicability(tenant_lesson, wrong_tenant)

    assert tenant_applicability.applies is False
    assert "tenant_scope_mismatch" in tenant_applicability.reasons

    local_lesson = apply_reflexive_scope(
        _lesson(),
        visibility=MemoryVisibility.LOCAL_RUN,
        domain="tax",
    )
    other_run = MemoryApplicabilityContext(run_id="different_run", domain="tax")

    local_applicability = evaluate_lesson_applicability(local_lesson, other_run)

    assert local_applicability.applies is False
    assert "run_scope_mismatch" in local_applicability.reasons


def test_memory_retrieval_without_applicability_reasons_fails_validation() -> None:
    with pytest.raises(ValidationError):
        LessonApplicability(lesson_id="lesson_a", applies=True, reasons=[])
