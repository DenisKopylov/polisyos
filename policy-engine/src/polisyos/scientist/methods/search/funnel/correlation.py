"""Backward-compatible funnel correlation wrapper over search CorrelationTracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from polisyos.scientist.methods.search.funnel.types import FunnelStageResult
from polisyos.scientist.methods.search.stages import CorrelationTracker, StageResult


@dataclass
class FunnelCorrelationRecord:
    """Single candidate's results across funnel levels."""

    candidate_hash: str
    level_scores: dict[int, float]
    level_passed: dict[int, bool]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_sentinel: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class FunnelCorrelationTracker:
    """Compatibility wrapper that exposes the legacy funnel correlation API."""

    def __init__(
        self,
        max_records: int = 1000,
        *,
        drift_window_size: int = 20,
        spearman_warning_threshold: float = 0.6,
        promotion_ban_threshold: float = 0.5,
        false_negative_ceiling: float = 0.02,
        sentinel_pass_floor: float = 0.9,
    ):
        self._records: list[FunnelCorrelationRecord] = []
        self._max_records = max_records
        self._tracker_config = {
            "max_records": max_records,
            "drift_window_size": drift_window_size,
            "spearman_warning_threshold": spearman_warning_threshold,
            "promotion_ban_threshold": promotion_ban_threshold,
            "false_negative_ceiling": false_negative_ceiling,
            "sentinel_pass_floor": sentinel_pass_floor,
        }

    def record(
        self,
        candidate_hash: str,
        level_results: dict[int, FunnelStageResult],
        *,
        is_sentinel: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        rec = FunnelCorrelationRecord(
            candidate_hash=candidate_hash,
            level_scores={level: result.objective_value for level, result in level_results.items()},
            level_passed={level: result.is_promising for level, result in level_results.items()},
            is_sentinel=bool(is_sentinel),
            metadata=dict(metadata or {}),
        )
        self._records.append(rec)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]

    @property
    def record_count(self) -> int:
        return len(self._records)

    def false_negative_rate(
        self,
        gate_level: int,
        truth_level: int,
    ) -> float:
        tracker = self._pair_tracker(gate_level, truth_level)
        return tracker.false_negative_rate()

    def true_positive_rate(
        self,
        gate_level: int,
        truth_level: int,
    ) -> float:
        metrics = self.compute_level_metrics(gate_level, truth_level)
        return float(metrics.get("true_positive_rate", 0.0))

    def compute_level_metrics(
        self,
        level_a: int,
        level_b: int,
    ) -> dict[str, Any]:
        tracker = self._pair_tracker(level_a, level_b)
        metrics = tracker.compute_metrics()
        metrics["sample_count"] = sum(
            1
            for record in self._records
            if level_a in record.level_scores and level_b in record.level_scores
        )
        return metrics

    def to_jsonl_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "candidate_hash": record.candidate_hash,
                "level_scores": record.level_scores,
                "level_passed": record.level_passed,
                "timestamp": record.timestamp.isoformat(),
                "is_sentinel": record.is_sentinel,
                "metadata": record.metadata,
            }
            for record in self._records
        ]

    def _pair_tracker(
        self,
        level_a: int,
        level_b: int,
    ) -> CorrelationTracker:
        tracker = CorrelationTracker(**self._tracker_config)
        for record in self._records:
            if level_a not in record.level_scores or level_b not in record.level_scores:
                continue
            tracker.record(
                self._stage_result(
                    score=record.level_scores[level_a],
                    passed=record.level_passed[level_a],
                    stage_name=f"funnel_L{level_a}",
                ),
                self._stage_result(
                    score=record.level_scores[level_b],
                    passed=record.level_passed[level_b],
                    stage_name=f"funnel_L{level_b}",
                ),
                record.candidate_hash,
                is_sentinel=record.is_sentinel,
                metadata={
                    **record.metadata,
                    "level_a": level_a,
                    "level_b": level_b,
                },
            )
        return tracker

    @staticmethod
    def _stage_result(
        *,
        score: float,
        passed: bool,
        stage_name: str,
    ) -> StageResult:
        return StageResult(
            policy_candidate={},
            objective_value=score,
            is_promising=passed,
            stage_name=stage_name,
            predicted_score=score,
            actual_score=score,
        )
