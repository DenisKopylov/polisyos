from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality.claim_registry import normalize_runtime_claim_registry
from polisyos.runtime.quality.memory_influence import (
    MemoryInfluenceRecord,
    assert_memory_influence_not_claim_evidence,
    build_memory_influence_record,
    is_memory_influence_ref,
)
from polisyos.scientist.orchestration.memory import (
    BalancedMemoryKind,
    BalancedMemoryRecord,
    BalancedMemoryScope,
    MemoryApplicabilityContext,
    MemorySourceKind,
    MemoryVisibility,
    build_balanced_memory_record,
)


def _success_memory() -> BalancedMemoryRecord:
    return build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Reviewer-confirmed source triangulation improved future search coverage.",
        pattern_type="source_triangulation_success",
        stage_name="evidence_review",
        source_run_id="run-success",
        candidate_hash="candidate-success",
        scope=BalancedMemoryScope(
            visibility=MemoryVisibility.DOMAIN,
            domain="tax",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        ),
        source_kind=MemorySourceKind.HUMAN_REVIEW,
    )


def test_success_memory_influence_guides_search_and_review_but_not_claim_evidence() -> None:
    record = build_memory_influence_record(
        _success_memory(),
        run_id="run-target",
        context=MemoryApplicabilityContext(run_id="run-target", domain="tax"),
        contamination_check_ref="quality_evidence/memory_contamination_pass.json",
    )

    assert record.memory_kind == BalancedMemoryKind.SUCCESS
    assert record.influence_modes == ("guide_search", "guide_review")
    assert "future_search" in record.authoritative_for
    assert "future_review" in record.authoritative_for
    assert is_memory_influence_ref(record.record_id)
    assert set(record.may_not_use_for) >= {
        "current_claim_evidence",
        "current_claim_closure",
        "claim_support",
        "claim_refutation",
    }
    assert_memory_influence_not_claim_evidence(record)


def test_memory_influence_record_rejects_current_evidence_slots() -> None:
    with pytest.raises(ValidationError, match="memory influence cannot carry current evidence"):
        MemoryInfluenceRecord(
            run_id="run-target",
            memory_id="memory-success",
            memory_kind=BalancedMemoryKind.SUCCESS,
            source_run_id="run-success",
            source_kind=MemorySourceKind.HUMAN_REVIEW,
            source_status="verified",
            influence_modes=("guide_search",),
            authoritative_for=("future_search",),
            may_not_use_for=(
                "current_claim_evidence",
                "current_claim_closure",
                "claim_support",
                "claim_refutation",
            ),
            scope={"visibility": "domain", "domain": "tax"},
            contamination_check_ref="quality_evidence/memory_contamination_pass.json",
            evidence_slot_refs=("claim-a:evidence-ref",),
        )


def test_llm_candidate_memory_cannot_emit_active_influence_record() -> None:
    memory = build_balanced_memory_record(
        kind=BalancedMemoryKind.OPPORTUNITY,
        summary="The drafter guessed there may be an unseen fiscal-risk analogy.",
        pattern_type="speculative_fiscal_analogy",
        stage_name="draft_review",
        source_run_id="run-source",
        candidate_hash="candidate-llm",
        scope=BalancedMemoryScope(visibility=MemoryVisibility.DOMAIN, domain="tax"),
        source_kind=MemorySourceKind.LLM_CANDIDATE,
    )

    with pytest.raises(ValueError, match="llm_candidate_unverified"):
        build_memory_influence_record(
            memory,
            run_id="run-target",
            context=MemoryApplicabilityContext(run_id="run-target", domain="tax"),
            contamination_check_ref="quality_evidence/memory_contamination_pass.json",
        )


def test_contaminated_memory_cannot_emit_influence_record() -> None:
    memory = build_balanced_memory_record(
        kind=BalancedMemoryKind.SUCCESS,
        summary="Hidden suite memory should be rejected before future routing.",
        pattern_type="contaminated_success",
        stage_name="semantic_eval",
        source_run_id="run-source",
        candidate_hash="candidate-contaminated",
        scope=BalancedMemoryScope(visibility=MemoryVisibility.DOMAIN, domain="tax"),
        source_kind=MemorySourceKind.DETERMINISTIC_PRODUCER,
        metadata={"hidden_suite_id": "hidden-suite"},
    )

    with pytest.raises(ValueError, match="reusable memory contamination"):
        build_memory_influence_record(
            memory,
            run_id="run-target",
            context=MemoryApplicabilityContext(run_id="run-target", domain="tax"),
            contamination_check_ref="quality_evidence/memory_contamination_block.json",
            hidden_suite_ids={"hidden-suite"},
        )


def test_memory_influence_ref_cannot_satisfy_claim_registry_evidence_slot() -> None:
    registry = normalize_runtime_claim_registry(
        {
            "schema_version": "policyos.runtime.claim_registry.v1",
            "claims": [
                {
                    "claim_id": "claim-a",
                    "scenario_requirement_refs": ["scenario.req.a"],
                    "data_refs": ["memory-influence:success-memory-a"],
                    "selected_norm_refs": ["norm.a"],
                    "method_output_refs": ["method.a"],
                    "portfolio_refs": ["portfolio.a"],
                    "argument_refs": ["argument.a"],
                    "warrant_refs": ["warrant.a"],
                    "rebuttal_refs": ["rebuttal.a"],
                    "counter_evidence_refs": ["counter.a"],
                    "limitation_refs": ["limitation.a"],
                    "accepted_deficit_refs": ["deficit.a"],
                }
            ],
        }
    )

    issue_codes = {issue["code"] for issue in registry["issues"]}

    assert registry["status"] == "fail"
    assert "memory_influence_ref_not_admissible_as_claim_evidence" in issue_codes
