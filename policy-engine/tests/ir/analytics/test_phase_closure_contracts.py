from __future__ import annotations

from pathlib import Path

from polisyos.ir.analytics.frontier import (
    ALL_PHASE_CLOSURE_MANIFESTS,
    PHASE1_CLOSURE_MANIFEST,
    PHASE2_CLOSURE_MANIFEST,
    PHASE3_CLOSURE_MANIFEST,
    PHASE4_CLOSURE_MANIFEST,
    all_stage_declarations,
    build_phase_closure_validation_report,
    parse_research_plan_stage_index,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_manifests_cover_all_first_occurrence_document_stages() -> None:
    document_stage_entries, duplicate_document_stages = parse_research_plan_stage_index(
        _REPO_ROOT / "docs/archive/plans/CAUSAL_ENGINE_RESEARCH_RESULT_PLAN.md"
    )

    manifest_stage_ids = {stage.stage_id for stage in all_stage_declarations()}
    document_stage_ids = set(document_stage_entries)

    assert manifest_stage_ids == document_stage_ids
    assert duplicate_document_stages["11.2"]
    assert {manifest.phase_id for manifest in ALL_PHASE_CLOSURE_MANIFESTS} == {
        PHASE1_CLOSURE_MANIFEST.phase_id,
        PHASE2_CLOSURE_MANIFEST.phase_id,
        PHASE3_CLOSURE_MANIFEST.phase_id,
        PHASE4_CLOSURE_MANIFEST.phase_id,
    }


def test_phase_manifest_partition_matches_expected_stage_sets() -> None:
    expected = {
        PHASE1_CLOSURE_MANIFEST.phase_id: {
            "2.1",
            "3.1",
            "4.4",
            "5.3",
            "8.1",
            "11.1",
            "11.2",
            "12.1",
            "13.1",
            "15.1",
            "16.1",
        },
        PHASE2_CLOSURE_MANIFEST.phase_id: {
            "2.2",
            "3.2",
            "5.1",
            "5.2",
            "6.1",
            "7.2",
            "8.2",
            "9.1",
            "9.2",
            "10.1",
            "12.2",
            "13.2",
            "15.2",
            "16.2",
        },
        PHASE3_CLOSURE_MANIFEST.phase_id: {
            "2.3",
            "4.1",
            "4.2",
            "4.3",
            "4.5",
            "6.2",
            "6.3",
            "6.4",
            "7.1",
            "8.3",
            "10.2",
            "10.3",
            "11.3",
            "12.3",
            "13.3",
            "15.3",
            "16.3",
        },
        PHASE4_CLOSURE_MANIFEST.phase_id: {
            "2.4",
            "2.5",
            "9.3",
            "13.4",
            "14.1",
            "14.2",
        },
    }

    actual = {
        manifest.phase_id: {stage.stage_id for stage in manifest.stages}
        for manifest in ALL_PHASE_CLOSURE_MANIFESTS
    }
    assert actual == expected


def test_non_execution_grade_stages_have_machine_readable_boundaries() -> None:
    non_execution = [stage for stage in all_stage_declarations() if stage.closure_state != "execution_grade"]

    assert non_execution
    for stage in non_execution:
        assert stage.boundary_reason
        assert stage.downstream_promotion_rule
        assert stage.kill_rule
        assert stage.evidence_tests
        assert stage.evidence_contracts


def test_phase_closure_validator_returns_complete_repo_report() -> None:
    report = build_phase_closure_validation_report(repo_root=_REPO_ROOT)

    assert report.overall_status == "complete"
    assert all(status == "complete" for status in report.phase_status.values())
    assert all(result.status == "complete" for result in report.stage_results)
    assert any(issue.code == "duplicate_document_stage_heading" for issue in report.issues)
    assert all(issue.severity != "error" for issue in report.issues)
