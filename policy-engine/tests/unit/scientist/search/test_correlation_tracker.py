from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
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


def test_correlation_tracker_preserves_legacy_metrics() -> None:
    tracker = CorrelationTracker()
    tracker.record(
        _stage_result(score=0.1, passed=True, stage_name="cheap"),
        _stage_result(score=0.2, passed=True, stage_name="full"),
        "a",
    )
    metrics = tracker.compute_metrics()
    assert "false_positive_rate" in metrics
    assert "true_positive_rate" in metrics
    assert "spearman_correlation" in metrics


def test_correlation_tracker_triggers_promotion_ban_on_correlation_collapse() -> None:
    tracker = CorrelationTracker(drift_window_size=5)
    rows = [
        (0.1, True, 0.9, True),
        (0.2, True, 0.8, True),
        (0.3, True, 0.7, True),
        (0.4, True, 0.6, True),
        (0.5, True, 0.5, True),
    ]
    for index, row in enumerate(rows):
        tracker.record(
            _stage_result(score=row[0], passed=row[1], stage_name="L2"),
            _stage_result(score=row[2], passed=row[3], stage_name="L4"),
            f"cand-{index}",
        )

    assert tracker.promotion_ban_active() is True
    assert tracker.routing_mode() == "no_promotion"


def test_correlation_tracker_detects_false_negative_spike() -> None:
    tracker = CorrelationTracker(drift_window_size=5, false_negative_ceiling=0.1)
    for index in range(5):
        tracker.record(
            _stage_result(score=0.9, passed=False, stage_name="L2"),
            _stage_result(score=0.1, passed=True, stage_name="L4"),
            f"fn-{index}",
        )

    metrics = tracker.compute_metrics()
    alerts = tracker.drift_alerts()
    assert metrics["false_negative_rate"] > 0.1
    assert any(alert.code == "FALSE_NEGATIVE_SPIKE" for alert in alerts)


def test_correlation_tracker_tracks_sentinel_pass_rate_and_jsonl_rows() -> None:
    tracker = CorrelationTracker(drift_window_size=4, sentinel_pass_floor=0.95)
    tracker.record(
        _stage_result(score=0.2, passed=False, stage_name="L2"),
        _stage_result(score=0.2, passed=True, stage_name="L4"),
        "sentinel-1",
        is_sentinel=True,
    )
    tracker.record(
        _stage_result(score=0.1, passed=True, stage_name="L2"),
        _stage_result(score=0.1, passed=True, stage_name="L4"),
        "regular-1",
    )

    metrics = tracker.compute_metrics()
    rows = tracker.to_jsonl_rows()
    assert metrics["sentinel_pass_rate"] == 0.0
    assert rows[0]["candidate_hash"] == "sentinel-1"
    assert "is_sentinel" in rows[0]


def test_correlation_tracker_snapshot_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    tracker = CorrelationTracker()
    tracker.record(
        _stage_result(score=0.1, passed=True, stage_name="L2"),
        _stage_result(score=0.2, passed=True, stage_name="L4"),
        "snap-1",
    )

    ref = tracker.persist_snapshot(store)
    restored = CorrelationTracker.load_snapshot(store, ref)
    assert restored.record_count == 1
    assert restored.compute_metrics()["sample_count"] == 1
