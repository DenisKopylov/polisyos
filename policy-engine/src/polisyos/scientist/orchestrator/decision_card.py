from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class KeyMetric:
    name: str
    value: float
    formatted: str
    unit: str = ""
    ci_lower: float | None = None
    ci_upper: float | None = None
    ci_level: float | None = None


@dataclass(frozen=True)
class IssuesSummary:
    blocker_count: int = 0
    warning_count: int = 0


@dataclass(frozen=True)
class DecisionCard:
    run_id: str
    verdict: Verdict = Verdict.REVIEW
    confidence: Confidence = Confidence.MEDIUM
    policy_summary: str = "N/A"
    key_metrics: list[KeyMetric] = field(default_factory=list)
    issues: IssuesSummary = field(default_factory=IssuesSummary)
    total_duration_ms: int = 0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def render_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Decision Card: {self.run_id}")
        lines.append("")
        lines.append(f"**Generated:** {self.generated_at.isoformat()}")
        lines.append("")

        icon = {
            Verdict.APPROVE: "✅",
            Verdict.REJECT: "❌",
            Verdict.REVIEW: "⚠️",
        }.get(self.verdict, "❓")
        lines.append(f"## Verdict: {icon} **{self.verdict.value}**")
        lines.append("")
        lines.append(f"**Confidence:** {self.confidence.value}")
        lines.append("")

        lines.append("## Policy")
        lines.append("")
        lines.append(self.policy_summary)
        lines.append("")

        if self.key_metrics:
            lines.append("## Key Metrics")
            lines.append("")
            lines.append("| Metric | Value | 95% CI |")
            lines.append("|--------|-------|--------|")
            for metric in self.key_metrics:
                if metric.ci_lower is not None and metric.ci_upper is not None:
                    ci = f"[{metric.ci_lower:+.2f}, {metric.ci_upper:+.2f}]"
                else:
                    ci = "—"
                unit = f" {metric.unit}" if metric.unit else ""
                lines.append(f"| {metric.name} | {metric.formatted}{unit} | {ci} |")
            lines.append("")

        metrics_with_ci = [
            metric
            for metric in self.key_metrics
            if metric.ci_lower is not None and metric.ci_upper is not None
        ]
        if metrics_with_ci:
            lines.append("## Uncertainty Summary")
            lines.append("")
            for metric in metrics_with_ci:
                assert metric.ci_lower is not None  # narrowed above
                assert metric.ci_upper is not None  # narrowed above
                width = metric.ci_upper - metric.ci_lower
                rel_width = (width / abs(metric.value) * 100.0) if metric.value != 0 else 0.0
                bar_fill = min(int(rel_width / 5.0), 20)
                bar = "█" * bar_fill + "░" * (20 - bar_fill)
                level = f"{metric.ci_level:.0%}" if metric.ci_level is not None else "95%"
                lines.append(
                    f"- **{metric.name}:** {metric.formatted} ± {width / 2.0:.2f} "
                    f"({level} CI, relative width: {rel_width:.1f}%)"
                )
                lines.append(f"  `{bar}` {rel_width:.0f}%")
            lines.append("")

        lines.append("## Issues")
        lines.append("")
        lines.append(
            f"**Blockers**: {self.issues.blocker_count} | "
            f"**Warnings**: {self.issues.warning_count}"
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"*Duration: {self.total_duration_ms}ms*")
        lines.append("")
        return "\n".join(lines)


__all__ = [
    "Confidence",
    "DecisionCard",
    "IssuesSummary",
    "KeyMetric",
    "Verdict",
]
