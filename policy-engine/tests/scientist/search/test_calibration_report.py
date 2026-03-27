from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.search.calibration_report import (
    build_calibration_report,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
    render_calibration_report,
)
from polisyos.scientist.search.cold_start import BurnInRunReport
from polisyos.scientist.search.lessons import LessonCard, LessonKind, LessonRegistry
from polisyos.scientist.search.sentinels import SentinelCandidate, SentinelKind, SentinelSet
from polisyos.scientist.search.stages import CorrelationTracker, StageResult


def _stage_result(*, score: float, passed: bool, stage_name: str) -> StageResult:
    return StageResult(
        policy_candidate={},
        objective_value=score,
        is_promising=passed,
        stage_name=stage_name,
        predicted_score=score,
        actual_score=score,
    )


def test_calibration_report_builds_from_tracker_lessons_and_burn_in(tmp_path) -> None:
    tracker = CorrelationTracker(drift_window_size=5)
    for index, row in enumerate(
        [
            (0.1, True, 0.9, True),
            (0.2, True, 0.8, True),
            (0.3, True, 0.7, True),
            (0.4, True, 0.6, True),
            (0.5, True, 0.5, True),
        ]
    ):
        tracker.record(
            _stage_result(score=row[0], passed=row[1], stage_name="L2"),
            _stage_result(score=row[2], passed=row[3], stage_name="L4"),
            f"cand-{index}",
        )

    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
    registry.record(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="Transportability repeatedly breaks for this policy family.",
            failure_type="transport_failure",
            stage_name="funnel_L2_causal",
            fidelity_level=2,
            candidate_hash="cand-transport",
            source_run_id="run-1",
            tags=["transport"],
        )
    )

    sentinel_set = SentinelSet(
        set_id="s1",
        suite_id="bench",
        sentinels=[
            SentinelCandidate(
                sentinel_id="sentinel-a",
                kind=SentinelKind.CALIBRATION,
                candidate={"semantic": {"interventions": [], "objectives": []}},
            )
        ],
        injection_rate=20,
        pass_rate_floor=0.95,
    )
    burn_in_report = BurnInRunReport(
        run_id="burn-in-1",
        cohort_sizes={"calibration": 10, "lesson_seeding": 5},
        baseline_level4_candidates=15,
        actual_level4_candidates=6,
        level4_execution_rate=0.4,
        expensive_stage_load_reduction=0.6,
        false_negative_rate=0.01,
        spearman_correlation=0.7,
        sentinel_pass_rate=1.0,
        degradation_mode="normal",
    )

    report = build_calibration_report(
        correlation_tracker=tracker,
        lesson_registry=registry,
        sentinel_set=sentinel_set,
        burn_in_report=burn_in_report,
    )
    rendered_md = render_calibration_report(report, format="md")

    assert report.top_lessons
    assert "Top Lessons" in rendered_md
    assert report.expensive_stage_load_reduction == 0.6

    ref = persist_funnel_calibration_report(store, report)
    loaded = load_funnel_calibration_report(store, ref)
    assert loaded.current_mode == report.current_mode


def test_calibration_report_marks_gaps_when_inputs_missing() -> None:
    report = build_calibration_report()
    assert "missing_burn_in" in report.gaps
    assert "missing_sentinels" in report.gaps
    assert "insufficient_correlation_window" in report.gaps
