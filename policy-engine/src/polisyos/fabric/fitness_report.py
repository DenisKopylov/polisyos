"""Assemble human-readable data-fitness reports from Fabric quality indicators."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List

from polisyos.common.logger import get_logger
from polisyos.fabric.temporal import parse_datetime_utc, utc_now

from .quality import QualityIndicators, QualityLevel, QualityThresholds

logger = get_logger(__name__)


@dataclass
class MetricFitness:
    """
    Fitness assessment for a single metric.

    Combines raw QualityIndicators with computed level and
    human-readable failure reasons.
    """

    metric_id: str
    indicators: QualityIndicators
    level: QualityLevel
    fail_reasons: List[str] = field(default_factory=list)
    profile_used: str = "mvp"

    @property
    def passed(self) -> bool:
        """Return True if quality level is acceptable or better."""
        return self.level.is_passing()

    @classmethod
    def from_indicators(
        cls,
        indicators: QualityIndicators,
        thresholds: QualityThresholds | None = None,
        profile: str = "mvp",
    ) -> "MetricFitness":
        thresholds = thresholds or QualityThresholds.for_profile(profile)
        level = indicators.overall_level(thresholds)
        reasons = indicators.get_failure_reasons(thresholds)
        return cls(
            metric_id=indicators.metric_id,
            indicators=indicators,
            level=level,
            fail_reasons=reasons,
            profile_used=profile,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return {
            "metric_id": self.metric_id,
            "indicators": self.indicators.to_dict(),
            "level": self.level.value,
            "fail_reasons": self.fail_reasons,
            "profile_used": self.profile_used,
            "passed": self.passed,
        }


@dataclass
class DataFitnessReport:
    """
    Human-readable fitness report attached to DecisionPacket.

    Provides a summary of data quality for all metrics used
    in a simulation run.
    """

    run_id: str
    profile: str = "mvp"
    metrics: List[MetricFitness] = field(default_factory=list)
    overall_passed: bool = True
    summary: str = ""
    computed_at: datetime = field(default_factory=utc_now)
    diagnostics: List[dict[str, str]] = field(default_factory=list)

    total_metrics: int = 0
    passed_metrics: int = 0
    failed_metrics: int = 0

    def add_metric(self, fitness: MetricFitness) -> None:
        """Add a metric fitness assessment to the report."""
        self.metrics.append(fitness)
        self.total_metrics += 1

        if fitness.passed:
            self.passed_metrics += 1
        else:
            self.failed_metrics += 1
            self.overall_passed = False

    def generate_summary(self) -> str:
        """
        Generate a human-readable ASCII summary.

        Format suitable for logging, UI display, and audit trails.
        """
        lines = [
            "DATA FITNESS REPORT",
            f"Run ID: {self.run_id}",
            f"Profile: {self.profile}",
            f"Time: {self.computed_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Metric ID | Level | Status",
            "-----------------------------------------------",
        ]

        for metric in self.metrics:
            status = "PASSED" if metric.passed else "FAILED"
            lines.append(
                f"{metric.metric_id} | {metric.level.value.upper()} | {status}"
            )
            for reason in metric.fail_reasons[:3]:
                lines.append(f"  - {reason}")

        lines.extend(
            [
                "",
                f"Summary: {self.passed_metrics}/{self.total_metrics} metrics passed",
                f"Verdict: {'PASSED' if self.overall_passed else 'FAILED'}",
            ]
        )

        self.summary = "\n".join(lines)
        return self.summary

    def generate_markdown_summary(self) -> str:
        """Generate Markdown summary for documentation."""
        lines = [
            "# Data Fitness Report",
            "",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Profile:** `{self.profile}`  ",
            f"**Computed:** {self.computed_at.strftime('%Y-%m-%d %H:%M:%S')}  ",
            "",
            "## Summary",
            "",
            "| Metric | Level | Status |",
            "|--------|-------|--------|",
        ]

        for metric in self.metrics:
            status = "PASS" if metric.passed else "FAIL"
            lines.append(f"| `{metric.metric_id}` | {metric.level.value} | {status} |")

        lines.extend(
            [
                "",
                "## Verdict",
                "",
                f"**{self.passed_metrics}/{self.total_metrics}** metrics passed.",
                "",
                f"Overall: **{'PASSED' if self.overall_passed else 'FAILED'}**",
            ]
        )

        failed = [metric for metric in self.metrics if not metric.passed]
        if failed:
            lines.extend(["", "## Failure Details", ""])
            for metric in failed:
                lines.append(f"### `{metric.metric_id}`")
                lines.append("")
                for reason in metric.fail_reasons:
                    lines.append(f"- {reason}")
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return {
            "run_id": self.run_id,
            "profile": self.profile,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "overall_passed": self.overall_passed,
            "summary": self.summary,
            "computed_at": self.computed_at.isoformat(),
            "diagnostics": self.diagnostics,
            "total_metrics": self.total_metrics,
            "passed_metrics": self.passed_metrics,
            "failed_metrics": self.failed_metrics,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        strict: bool = False,
    ) -> "DataFitnessReport":
        """Deserialize from JSON storage."""
        report = cls(
            run_id=data["run_id"],
            profile=data.get("profile", "mvp"),
            overall_passed=data.get("overall_passed", True),
            summary=data.get("summary", ""),
            computed_at=parse_datetime_utc(data["computed_at"], what="computed_at"),
            diagnostics=[
                {
                    "code": str(item.get("code", "report_diagnostic")),
                    "message": str(item.get("message", "")),
                    "metric_id": str(item.get("metric_id", "")),
                }
                for item in data.get("diagnostics", [])
                if isinstance(item, dict)
            ],
        )

        metrics: list[MetricFitness] = []
        for metric in data.get("metrics", []):
            try:
                indicators = QualityIndicators.from_dict(metric["indicators"])
                level = QualityLevel(metric["level"])
                metrics.append(
                    MetricFitness(
                        metric_id=metric["metric_id"],
                        indicators=indicators,
                        level=level,
                        fail_reasons=metric.get("fail_reasons", []),
                        profile_used=metric.get("profile_used", report.profile),
                    )
                )
            except Exception as exc:
                if strict:
                    raise ValueError(
                        "Failed to parse metric fitness entry for metric_id="
                        f"{metric.get('metric_id', '<unknown>')}: {exc}"
                    ) from exc
                report.diagnostics.append(
                    {
                        "code": "metric_deserialize_failed",
                        "metric_id": str(metric.get("metric_id", "<unknown>")),
                        "message": str(exc),
                    }
                )
                logger.warning(
                    "Failed to parse metric fitness entry for metric_id=%s",
                    metric.get("metric_id", "<unknown>"), exc_info=True,
                )
        report.metrics = metrics

        if report.diagnostics:
            report.total_metrics = len(metrics)
            report.passed_metrics = sum(1 for metric in metrics if metric.passed)
            report.failed_metrics = report.total_metrics - report.passed_metrics
            report.overall_passed = report.failed_metrics == 0
        elif all(key in data for key in ("total_metrics", "passed_metrics", "failed_metrics")):
            report.total_metrics = int(data.get("total_metrics", 0))
            report.passed_metrics = int(data.get("passed_metrics", 0))
            report.failed_metrics = int(data.get("failed_metrics", 0))
            report.overall_passed = bool(data.get("overall_passed", report.failed_metrics == 0))
        else:
            report.total_metrics = len(metrics)
            report.passed_metrics = sum(1 for metric in metrics if metric.passed)
            report.failed_metrics = report.total_metrics - report.passed_metrics
            report.overall_passed = report.failed_metrics == 0
        return report
