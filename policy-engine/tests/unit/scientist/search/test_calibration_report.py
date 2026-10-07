from __future__ import annotations

import json
import math

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.calibration_report import (
    build_calibration_report,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
    render_calibration_report,
)
from polisyos.scientist.methods.search.cold_start import BurnInRunReport
from polisyos.scientist.methods.search.lessons import LessonCard, LessonKind, LessonRegistry
from polisyos.scientist.methods.search.sentinels import SentinelCandidate, SentinelKind, SentinelSet
from polisyos.scientist.methods.search.stages import CorrelationTracker, StageResult
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _resolve_degradation_mode,
    _resolve_runtime_correlation_metrics,
    _resolve_runtime_correlation_tracker,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


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


def _native_report_tracker(*, reverse: bool = False) -> CorrelationTracker:
    tracker = CorrelationTracker(drift_window_size=5)
    for number in range(5):
        cheap = float(number + 1)
        full = float(5 - number if reverse else number + 1)
        tracker.record(
            StageResult(
                policy_candidate={},
                objective_value=cheap,
                predicted_score=cheap,
                is_promising=True,
                stage_name="L2",
            ),
            StageResult(
                policy_candidate={},
                objective_value=full,
                actual_score=full,
                is_promising=True,
                stage_name="L4",
            ),
            f"paired-{number}",
            metadata={"fixture_profile": "ordered_distinct_ranks", "input_basis": "same-corpus"},
        )
    return tracker


def _rank_oracle(reverse: bool) -> float:
    cheap_ranks = list(range(1, 6))
    full_ranks = list(reversed(cheap_ranks)) if reverse else cheap_ranks
    center = 3.0
    numerator = sum(
        (x - center) * (y - center) for x, y in zip(cheap_ranks, full_ranks, strict=True)
    )
    denominator = math.sqrt(
        sum((x - center) ** 2 for x in cheap_ranks) * sum((y - center) ** 2 for y in full_ranks)
    )
    return numerator / denominator


@pytest.mark.parametrize("reverse", [False, True])
def test_report_snapshot_reaches_native_consumer_with_same_corpus_and_routing(tmp_path, reverse):
    tracker = _native_report_tracker(reverse=reverse)
    expected_snapshot = tracker.to_snapshot().model_dump(mode="json")
    report = build_calibration_report(correlation_tracker=tracker)
    store = FileSystemCAS(tmp_path / "report-cas")
    ref = persist_funnel_calibration_report(store, report)
    loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "report-cas"), ref)
    restored = _resolve_runtime_correlation_tracker(loaded)

    assert restored is not None, "ordinary report producer dropped native reusable tracker corpus"
    assert restored is not tracker
    assert loaded.metadata["correlation_tracker_snapshot"] == expected_snapshot
    assert restored.to_snapshot().model_dump(mode="json") == expected_snapshot
    metrics = restored.compute_metrics()
    assert metrics["sample_count"] == metrics["rolling_sample_count"] == 5
    assert metrics["calibration_state"] == "observed"
    assert metrics["spearman_correlation"] == pytest.approx(_rank_oracle(reverse))
    assert metrics["routing_mode"] == restored.routing_mode() == loaded.current_mode
    assert restored.routing_mode() == ("no_promotion" if reverse else "normal")
    assert bool(metrics["promotion_ban_active"]) is reverse
    # Later source mutation does not rewrite the already persisted corpus.
    tracker.record(
        StageResult(policy_candidate={}, objective_value=6.0, is_promising=True, stage_name="L2"),
        StageResult(policy_candidate={}, objective_value=6.0, is_promising=True, stage_name="L4"),
        "after-publish",
    )
    fresh_loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "report-cas"), ref)
    fresh_restored = _resolve_runtime_correlation_tracker(fresh_loaded)
    assert fresh_restored is not None
    assert fresh_restored.to_snapshot().model_dump(mode="json") == expected_snapshot
    assert fresh_restored.record_count == 5
    assert tracker.record_count == 6


def test_supplied_empty_tracker_restores_not_established_without_measured_drift(tmp_path):
    report = build_calibration_report(correlation_tracker=CorrelationTracker())
    store = FileSystemCAS(tmp_path / "empty-cas")
    ref = persist_funnel_calibration_report(store, report)
    loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "empty-cas"), ref)
    restored = _resolve_runtime_correlation_tracker(loaded)
    assert restored is not None
    assert restored.record_count == 0
    assert restored.compute_metrics()["calibration_state"] == "not_established"
    assert restored.routing_mode() == loaded.current_mode == "no_promotion"
    assert restored.drift_alerts() == []


def test_absent_tracker_report_keeps_legacy_projection_without_invented_state(tmp_path):
    report = build_calibration_report()
    store = FileSystemCAS(tmp_path / "absent-cas")
    ref = persist_funnel_calibration_report(store, report)
    loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "absent-cas"), ref)
    assert "correlation_tracker_snapshot" not in loaded.metadata
    assert _resolve_runtime_correlation_tracker(loaded) is None
    assert loaded.current_mode == "no_promotion"


@pytest.mark.parametrize("mutation", ["remove", "foreign_field", "wrong_type"])
def test_report_snapshot_removal_or_foreign_shape_cannot_reconstruct_from_markers(
    tmp_path, mutation
):
    tracker = _native_report_tracker()
    report = build_calibration_report(correlation_tracker=tracker)
    assert report.current_mode == "normal"
    assert report.routing_health["sample_count"] == 5
    metadata = dict(report.metadata)
    if mutation == "remove":
        metadata.pop("correlation_tracker_snapshot", None)
    elif mutation == "foreign_field":
        foreign = tracker.to_snapshot().model_dump(mode="json")
        foreign["foreign_profile"] = "another-tracker"
        metadata["correlation_tracker_snapshot"] = foreign
    else:
        metadata["correlation_tracker_snapshot"] = "observed:5:normal"
    altered = report.model_copy(update={"metadata": metadata})
    store = FileSystemCAS(tmp_path / "negative-cas")
    ref = persist_funnel_calibration_report(store, altered)
    loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "negative-cas"), ref)
    assert loaded.current_mode == "normal"
    assert loaded.routing_health == report.routing_health
    assert _resolve_runtime_correlation_tracker(loaded) is None


@pytest.mark.parametrize("supplied", [False, True])
def test_empty_report_preserves_unassessed_null_through_render_cas_and_native_metrics(
    tmp_path, supplied
):
    report = build_calibration_report(
        correlation_tracker=CorrelationTracker() if supplied else None,
    )
    store = FileSystemCAS(tmp_path / "unassessed-cas")
    ref = persist_funnel_calibration_report(store, report)
    loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "unassessed-cas"), ref)
    assert loaded.routing_health["calibration_state"] == "not_established"
    for field in [
        "false_positive_rate",
        "false_negative_rate",
        "spearman_correlation",
        "rolling_spearman_correlation",
    ]:
        assert loaded.routing_health[field] is None
    criteria = {row.name: row for row in loaded.acceptance_criteria}
    for name in ["false_negative_rate", "spearman_l2_l4"]:
        assert criteria[name].actual is None
        assert criteria[name].passed is None
    document = json.loads(render_calibration_report(loaded, format="json"))
    json_criteria = {row["name"]: row for row in document["acceptance_criteria"]}
    assert json_criteria["false_negative_rate"]["actual"] is None
    assert json_criteria["false_negative_rate"]["passed"] is None
    assert json_criteria["spearman_l2_l4"]["actual"] is None
    markdown = render_calibration_report(loaded, format="md")
    assert "Spearman (L2 vs L4): n/a" in markdown
    assert "False-negative rate: n/a" in markdown
    assert "false_negative_rate: GAP" in markdown
    assert "spearman_l2_l4: GAP" in markdown
    state = ExperimentState(run_id="unassessed-native-report")
    metrics = _resolve_runtime_correlation_metrics(state, loaded)
    assert metrics["calibration_state"] == "not_established"
    assert metrics["spearman_correlation"] is None
    assert metrics["false_negative_rate"] is None
    assert _resolve_degradation_mode(state, calibration_report=loaded) == "no_promotion"


def test_observed_zero_correlation_is_measured_and_distinct_from_empty(tmp_path):
    cheap_ranks = [1, 2, 3, 4]
    full_ranks = [2, 4, 1, 3]
    # Independent distinct-rank Spearman formula, with no tracker analysis call.
    oracle = 1 - 6 * sum((x - y) ** 2 for x, y in zip(cheap_ranks, full_ranks, strict=True)) / (
        4 * (4**2 - 1)
    )
    assert oracle == 0.0
    tracker = CorrelationTracker(drift_window_size=5)
    for cheap, full in zip(cheap_ranks, full_ranks, strict=True):
        tracker.record(
            StageResult(
                policy_candidate={},
                objective_value=float(cheap),
                is_promising=True,
                stage_name="L2",
            ),
            StageResult(
                policy_candidate={}, objective_value=float(full), is_promising=True, stage_name="L4"
            ),
            f"zero-rank-{cheap}",
        )
    report = build_calibration_report(correlation_tracker=tracker)
    store = FileSystemCAS(tmp_path / "measured-zero-cas")
    ref = persist_funnel_calibration_report(store, report)
    loaded = load_funnel_calibration_report(FileSystemCAS(tmp_path / "measured-zero-cas"), ref)
    assert loaded.routing_health["calibration_state"] == "observed"
    assert loaded.routing_health["sample_count"] == 4
    assert loaded.routing_health["spearman_correlation"] == pytest.approx(oracle)
    criteria = {row.name: row for row in loaded.acceptance_criteria}
    assert criteria["spearman_l2_l4"].actual == pytest.approx(oracle)
    assert criteria["spearman_l2_l4"].passed is False
    assert criteria["false_negative_rate"].actual == 0.0
    assert criteria["false_negative_rate"].passed is True
    assert "Spearman (L2 vs L4): 0.000" in render_calibration_report(loaded, format="md")
    state = ExperimentState(run_id="measured-zero-native-report")
    metrics = _resolve_runtime_correlation_metrics(state, loaded)
    assert metrics["calibration_state"] == "observed"
    assert metrics["spearman_correlation"] == pytest.approx(oracle)
    assert _resolve_degradation_mode(state, calibration_report=loaded) == "no_promotion"
