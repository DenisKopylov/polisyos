"""Calibration report builder for funnel health and degraded-mode visibility."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.search.cold_start import BurnInRunReport
from polisyos.scientist.search.lessons import LessonIndexSnapshot, LessonPattern, LessonRegistry
from polisyos.scientist.search.sentinels import SentinelObservation, SentinelSet
from polisyos.scientist.search.stages import CorrelationTracker, DriftAlert

_CALIBRATION_REPORT_KIND = "scientist.search.calibration_report"
_CALIBRATION_REPORT_SCHEMA = SchemaInfo(
    name="polisyos.scientist.search.FunnelCalibrationReport",
    version="1.0",
)


class AcceptanceCriterionStatus(BaseModel):
    """Single acceptance criterion verdict."""

    model_config = ConfigDict(extra="forbid")

    name: str
    target: str
    actual: float | None = None
    passed: bool | None = None
    note: str | None = None


class FunnelCalibrationReport(BaseModel):
    """Machine-readable funnel health report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    current_mode: str = Field(min_length=1)
    gaps: list[str] = Field(default_factory=list)
    routing_health: dict[str, Any] = Field(default_factory=dict)
    expensive_stage_load_reduction: float | None = Field(default=None, ge=0.0, le=1.0)
    sentinel_health: dict[str, Any] = Field(default_factory=dict)
    top_lessons: list[LessonPattern] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterionStatus] = Field(default_factory=list)
    drift_alerts: list[DriftAlert] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_funnel_calibration_report(
    store: FileSystemCAS,
    report: FunnelCalibrationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist funnel calibration report helper."""
    return store.put_json(
        report,
        PutOptions(
            kind=_CALIBRATION_REPORT_KIND,
            media_type="application/json",
            schema=_CALIBRATION_REPORT_SCHEMA,
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def build_calibration_report(
    *,
    correlation_tracker: CorrelationTracker | None = None,
    lesson_registry: LessonRegistry | LessonIndexSnapshot | None = None,
    sentinel_set: SentinelSet | None = None,
    sentinel_observations: list[SentinelObservation] | None = None,
    burn_in_report: BurnInRunReport | None = None,
) -> FunnelCalibrationReport:
    """Build the funnel calibration report from tracker, lessons, and sentinels."""

    tracker = correlation_tracker or CorrelationTracker()
    metrics = tracker.compute_metrics()
    alerts = tracker.drift_alerts()
    observations = list(sentinel_observations or [])
    sentinel_pass_rate = metrics.get("sentinel_pass_rate")
    if sentinel_pass_rate is None and observations:
        sentinel_pass_rate = sum(1 for item in observations if item.stage_a_passed) / len(observations)

    gaps: list[str] = []
    if burn_in_report is None:
        gaps.append("missing_burn_in")
    if sentinel_set is None and sentinel_pass_rate is None:
        gaps.append("missing_sentinels")
    if int(metrics.get("rolling_sample_count", 0)) < 3:
        gaps.append("insufficient_correlation_window")

    top_lessons = _resolve_top_lessons(lesson_registry)
    expensive_stage_load_reduction = (
        burn_in_report.expensive_stage_load_reduction if burn_in_report is not None else None
    )
    acceptance_criteria = [
        AcceptanceCriterionStatus(
            name="false_negative_rate",
            target="< 0.02",
            actual=float(metrics.get("false_negative_rate", 0.0)),
            passed=float(metrics.get("false_negative_rate", 0.0)) < 0.02,
        ),
        AcceptanceCriterionStatus(
            name="spearman_l2_l4",
            target="> 0.6",
            actual=float(metrics.get("spearman_correlation", 0.0)),
            passed=float(metrics.get("spearman_correlation", 0.0)) > 0.6,
        ),
        AcceptanceCriterionStatus(
            name="expensive_stage_load_reduction",
            target="> 0.5",
            actual=expensive_stage_load_reduction,
            passed=(
                None
                if expensive_stage_load_reduction is None
                else expensive_stage_load_reduction > 0.5
            ),
            note=(
                "No burn-in or operational evaluation totals available."
                if expensive_stage_load_reduction is None
                else None
            ),
        ),
        AcceptanceCriterionStatus(
            name="sentinel_pass_rate",
            target="> 0.95",
            actual=None if sentinel_pass_rate is None else float(sentinel_pass_rate),
            passed=None if sentinel_pass_rate is None else float(sentinel_pass_rate) > 0.95,
            note="Sentinel set missing." if sentinel_pass_rate is None else None,
        ),
    ]

    recommended_actions = _recommended_actions(alerts, gaps)
    sentinel_health = {
        "configured_injection_rate": (
            None if sentinel_set is None else sentinel_set.injection_rate
        ),
        "configured_pass_rate_floor": (
            None if sentinel_set is None else sentinel_set.pass_rate_floor
        ),
        "observed_pass_rate": None if sentinel_pass_rate is None else float(sentinel_pass_rate),
        "observation_count": len(observations),
    }

    return FunnelCalibrationReport(
        current_mode=str(metrics.get("routing_mode", "normal")),
        gaps=gaps,
        routing_health={
            "sample_count": metrics.get("sample_count", 0),
            "rolling_sample_count": metrics.get("rolling_sample_count", 0),
            "false_positive_rate": metrics.get("false_positive_rate", 0.0),
            "false_negative_rate": metrics.get("false_negative_rate", 0.0),
            "spearman_correlation": metrics.get("spearman_correlation", 0.0),
            "rolling_spearman_correlation": metrics.get("rolling_spearman_correlation", 0.0),
            "promotion_ban_active": metrics.get("promotion_ban_active", False),
        },
        expensive_stage_load_reduction=expensive_stage_load_reduction,
        sentinel_health=sentinel_health,
        top_lessons=top_lessons,
        recommended_actions=recommended_actions,
        acceptance_criteria=acceptance_criteria,
        drift_alerts=alerts,
        metadata={
            "burn_in_present": burn_in_report is not None,
            "lesson_pattern_count": len(top_lessons),
        },
    )


def render_calibration_report(
    report: FunnelCalibrationReport,
    *,
    format: str = "json",
) -> str:
    """Render calibration report as JSON or Markdown."""

    normalized = format.strip().lower()
    if normalized == "json":
        return report.model_dump_json(indent=2, exclude_none=True)
    if normalized != "md":
        raise ValueError(f"Unsupported calibration report format: {format}")

    lines = [
        "# Funnel Calibration Report",
        "",
        f"- Mode: `{report.current_mode}`",
        f"- Gaps: {', '.join(report.gaps) if report.gaps else 'none'}",
        f"- Sample count: {report.routing_health.get('sample_count', 0)}",
        f"- Spearman (L2 vs L4): {float(report.routing_health.get('spearman_correlation', 0.0)):.3f}",
        f"- False-negative rate: {float(report.routing_health.get('false_negative_rate', 0.0)):.3f}",
        "",
        "## Acceptance Criteria",
    ]
    for criterion in report.acceptance_criteria:
        status = (
            "PASS"
            if criterion.passed is True
            else "FAIL"
            if criterion.passed is False
            else "GAP"
        )
        actual = "n/a" if criterion.actual is None else f"{criterion.actual:.4f}"
        lines.append(
            f"- {criterion.name}: {status} (target {criterion.target}, actual {actual})"
        )
    lines.append("")
    lines.append("## Sentinel Health")
    lines.append(
        f"- Observed pass rate: {report.sentinel_health.get('observed_pass_rate', 'n/a')}"
    )
    lines.append(
        f"- Configured floor: {report.sentinel_health.get('configured_pass_rate_floor', 'n/a')}"
    )
    lines.append("")
    lines.append("## Top Lessons")
    if report.top_lessons:
        for lesson in report.top_lessons:
            lines.append(
                f"- [{lesson.stage_name}] {lesson.summary} "
                f"(occurrences={lesson.occurrence_count}, failure_type={lesson.failure_type})"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Recommended Actions")
    if report.recommended_actions:
        for action in report.recommended_actions:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def load_funnel_calibration_report(
    store: FileSystemCAS,
    ref: ArtifactRef | str,
) -> FunnelCalibrationReport:
    """Load funnel calibration report."""
    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref
    return FunnelCalibrationReport.model_validate(
        from_canonical_bytes(store.get_bytes(artifact_id))
    )


def _resolve_top_lessons(
    source: LessonRegistry | LessonIndexSnapshot | None,
) -> list[LessonPattern]:
    if source is None:
        return []
    if isinstance(source, LessonRegistry):
        return source.top_patterns(limit=5)
    entries = sorted(
        [entry for entry in source.entries if not entry.invalidated],
        key=lambda item: (-item.occurrence_count, -item.last_seen.timestamp()),
    )
    return [
        LessonPattern(
            lesson_id=entry.lesson_id,
            artifact_ref=entry.artifact_ref,
            occurrence_count=entry.occurrence_count,
            kind=entry.kind,
            summary=entry.summary,
            failure_type=entry.failure_type,
            stage_name=entry.stage_name,
            fidelity_level=entry.fidelity_level,
            confidence=entry.confidence,
            trust_level=entry.trust_level,
            tags=list(entry.tags),
            remediation_hint=entry.remediation_hint,
            last_seen=entry.last_seen,
        )
        for entry in entries[:5]
    ]


def _recommended_actions(alerts: list[DriftAlert], gaps: list[str]) -> list[str]:
    actions: list[str] = []
    for alert in alerts:
        if alert.recommended_action and alert.recommended_action not in actions:
            actions.append(alert.recommended_action)
    for gap in gaps:
        if gap == "missing_burn_in":
            actions.append("Run calibration burn-in to seed lessons and tracker baselines.")
        elif gap == "missing_sentinels":
            actions.append("Attach a SentinelSet and begin mandatory sentinel injection.")
        elif gap == "insufficient_correlation_window":
            actions.append("Collect more Level 2/Level 4 paired evaluations before trusting VOI.")
    return actions


__all__ = [
    "AcceptanceCriterionStatus",
    "FunnelCalibrationReport",
    "build_calibration_report",
    "load_funnel_calibration_report",
    "persist_funnel_calibration_report",
    "render_calibration_report",
]
