from __future__ import annotations

# ruff: noqa: S101
import pytest

from polisyos.scientist.orchestration.memory import (
    MemoryAuthorityRecord,
    assert_memory_authority_for_serious_output,
    build_memory_use_authority_record,
    build_no_memory_abstention_record,
)


def test_empty_replay_surface_is_not_memory_abstention_without_runtime_record() -> None:
    with pytest.raises(ValueError, match="empty replay surface is not memory abstention"):
        assert_memory_authority_for_serious_output(
            None,
            replay_surface_empty=True,
        )


def test_no_memory_abstention_record_authorizes_serious_output_before_influence() -> None:
    record = build_no_memory_abstention_record(
        run_id="run-serious-001",
        tenant_id="tenant-default",
        cell_id="cell-default",
        replay_surface_empty=True,
        prompt_authority_refs={"prompt_tool_ledger": "sha256:prompt-ledger"},
        tool_authority_refs={"tool_authority": "quality_evidence/prompt_tool_ledger.json"},
        contamination_checks=[
            {
                "check_id": "hidden_eval_or_canary_memory_not_reused",
                "status": "pass",
                "contamination_detected": False,
                "evidence_ref": "quality_evidence/replay_manifest.json",
            }
        ],
        emission_order=20,
        serious_output_influence_order=30,
    )

    authorized = assert_memory_authority_for_serious_output(
        record,
        replay_surface_empty=True,
    )

    assert authorized.authority_kind == "no_memory_abstention"
    assert authorized.memory_used is False
    assert authorized.runtime_owned is True
    assert authorized.emission_order < authorized.serious_output_influence_order


def test_memory_use_authority_handoff_must_precede_serious_output_influence() -> None:
    late_record = build_memory_use_authority_record(
        run_id="run-serious-002",
        tenant_id="tenant-default",
        cell_id="cell-default",
        selected_memory_refs=["memory://lesson/lesson-a"],
        retrieval_event_refs=["event://memory/retrieved/lesson-a"],
        applicability_refs=["memory://applicability/lesson-a"],
        prompt_authority_refs={"prompt_tool_ledger": "sha256:prompt-ledger"},
        tool_authority_refs={"retrieval_tool": "scientist.memory.retrieve"},
        contamination_checks=[
            {
                "check_id": "tenant_scope_is_current_tenant_only",
                "status": "pass",
                "contamination_detected": False,
                "evidence_ref": "event://memory/retrieved/lesson-a",
            }
        ],
        emission_order=42,
        serious_output_influence_order=42,
    )

    with pytest.raises(ValueError, match="before serious output influence"):
        assert_memory_authority_for_serious_output(
            late_record,
            replay_surface_empty=False,
        )

    record = build_memory_use_authority_record(
        run_id="run-serious-002",
        tenant_id="tenant-default",
        cell_id="cell-default",
        selected_memory_refs=["memory://lesson/lesson-a"],
        retrieval_event_refs=["event://memory/retrieved/lesson-a"],
        applicability_refs=["memory://applicability/lesson-a"],
        prompt_authority_refs={"prompt_tool_ledger": "sha256:prompt-ledger"},
        tool_authority_refs={"retrieval_tool": "scientist.memory.retrieve"},
        contamination_checks=[
            {
                "check_id": "tenant_scope_is_current_tenant_only",
                "status": "pass",
                "contamination_detected": False,
                "evidence_ref": "event://memory/retrieved/lesson-a",
            }
        ],
        emission_order=41,
        serious_output_influence_order=42,
    )

    authorized = assert_memory_authority_for_serious_output(
        record,
        replay_surface_empty=False,
    )

    assert authorized.authority_kind == "memory_use_authority"
    assert authorized.memory_used is True
    assert authorized.selected_memory_refs == ["memory://lesson/lesson-a"]
    assert authorized.retrieval_event_refs == ["event://memory/retrieved/lesson-a"]


def test_memory_authority_record_distinguishes_kind_specific_fields() -> None:
    with pytest.raises(ValueError, match="no_memory_abstention cannot carry memory refs"):
        MemoryAuthorityRecord(
            run_id="run-serious-003",
            tenant_id="tenant-default",
            cell_id="cell-default",
            authority_kind="no_memory_abstention",
            memory_used=False,
            replay_surface_empty=True,
            selected_memory_refs=["memory://lesson/lesson-a"],
            prompt_authority_refs={"prompt_tool_ledger": "sha256:prompt-ledger"},
            tool_authority_refs={"tool_authority": "quality_evidence/prompt_tool_ledger.json"},
            contamination_checks=[
                {
                    "check_id": "hidden_eval_or_canary_memory_not_reused",
                    "status": "pass",
                    "contamination_detected": False,
                    "evidence_ref": "quality_evidence/replay_manifest.json",
                }
            ],
            emission_order=20,
            serious_output_influence_order=30,
        )
