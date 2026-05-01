"""Public orchestrator decision card module API."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.canon import truncated_hash

logger = get_logger(__name__)


class Verdict(str, Enum):
    """Verdict public type."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class Confidence(str, Enum):
    """Confidence public type."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_blocker_count(cls, blocker_count: int, warning_count: int) -> Confidence:
        if blocker_count > 0:
            return cls.LOW
        if warning_count > 0:
            return cls.MEDIUM
        return cls.HIGH


@dataclass(frozen=True)
class KeyMetric:
    """Key metric public type."""

    name: str
    value: float
    formatted: str
    unit: str = ""
    ci_lower: float | None = None
    ci_upper: float | None = None
    ci_level: float | None = None


@dataclass(frozen=True)
class DiagnosticBadge:
    """Diagnostic badge public type."""

    label: str
    kind: str = "info"


@dataclass(frozen=True)
class IssuesSummary:
    """Counts and blocked-pass ids that explain why governance approved, warned, or blocked a run."""

    blocker_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    blocked_passes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CohortSummaryRow:
    """Cohort summary row public type."""

    cohort_label: str
    population_share: float
    primary_delta: float
    direction: str
    is_vulnerable: bool = False


@dataclass(frozen=True)
class DistributionalSummary:
    """Compact distributional-impact snapshot rendered on the final decision card."""

    breakdowns: list[tuple[str, list[CohortSummaryRow]]]
    gini_before: float | None = None
    gini_after: float | None = None
    gini_delta: float | None = None
    winners_count: int = 0
    losers_count: int = 0
    winners_share: float = 0.0
    losers_share: float = 0.0
    vulnerable_losers_count: int = 0


@dataclass(frozen=True)
class TrustProvenanceSummary:
    """Compact trust/provenance hooks for frontend decision-card rendering."""

    claims_ref: str
    research_dag_ref: str
    claim_count: int = 0
    blocked_claim_count: int = 0
    research_step_count: int = 0
    research_dag_status: str | None = None
    continuous_governance_status: str | None = None


@dataclass(frozen=True)
class DecisionCard:
    """Decision card public type."""

    run_id: str
    source_hash: str | None = None
    verdict: Verdict = Verdict.REVIEW
    confidence: Confidence = Confidence.MEDIUM
    policy_summary: str = "N/A"
    intervention_count: int = 0
    key_metrics: list[KeyMetric] = field(default_factory=list)
    diagnostic_badges: list[DiagnosticBadge] = field(default_factory=list)
    issues: IssuesSummary = field(default_factory=IssuesSummary)
    distributional: DistributionalSummary | None = None
    trust_provenance: TrustProvenanceSummary | None = None
    total_duration_ms: int = 0
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_packet(cls, packet: Any) -> DecisionCard:
        decision_grade_export = _read(packet, "decision_grade_export", None)
        if decision_grade_export is not None:
            return cls.from_decision_grade_export(decision_grade_export)

        run_id = str(_read(packet, "run_id", "unknown"))
        generated_at = _parse_datetime(_read(packet, "generated_at", None))

        feedback = _read(packet, "feedback", None)
        if not isinstance(feedback, dict):
            feedback = _read(packet, "governance", {})
        verdict = _extract_verdict(feedback)
        issues = _extract_issues_summary(feedback)
        confidence = Confidence.from_blocker_count(issues.blocker_count, issues.warning_count)

        simulation_results = _read(packet, "simulation_results", None)
        if not isinstance(simulation_results, dict):
            simulation_results = {}
        uncertainty_bounds = _read(packet, "uncertainty_bounds", None)
        key_metrics = _extract_key_metrics(
            simulation_results, uncertainty_bounds=uncertainty_bounds
        )
        diagnostic_badges = _extract_diagnostic_badges(packet)

        distributional = _extract_distributional_summary(_read(packet, "distributional", None))

        policy_ir = _read(packet, "policy_ir", None)
        policy_summary, intervention_count = _extract_policy_summary(policy_ir)

        total_duration_ms = _extract_duration_ms(packet)
        source_hash = _compute_source_hash(packet)

        return cls(
            run_id=run_id,
            source_hash=source_hash,
            verdict=verdict,
            confidence=confidence,
            policy_summary=policy_summary,
            intervention_count=intervention_count,
            key_metrics=key_metrics,
            diagnostic_badges=diagnostic_badges,
            issues=issues,
            distributional=distributional,
            total_duration_ms=total_duration_ms,
            generated_at=generated_at,
        )

    @classmethod
    def from_decision_grade_export(cls, export: Any) -> DecisionCard:
        """Build a compact card from a Phase 2.7 decision-grade compiler export."""

        payload = _read(export, "payload", {})
        if not isinstance(payload, dict):
            payload = {}
        run_id = str(_read(export, "run_id", payload.get("run_id", "unknown")))
        generated_at = _parse_datetime(payload.get("generated_at"))
        trust = _extract_trust_provenance_summary(payload.get("trust_provenance"))
        blocked_summary = payload.get("blocked_claim_summary")
        if not isinstance(blocked_summary, dict):
            blocked_summary = {}
        blocker_count = int(blocked_summary.get("blocked_count", 0) or 0)
        warning_count = 1 if payload.get("continuous_governance", {}).get("status") in {
            "review_required",
            "stale",
        } else 0
        issues = IssuesSummary(blocker_count=blocker_count, warning_count=warning_count)
        policy_summary = _compiler_policy_summary(payload)
        claim_count = trust.claim_count if trust is not None else 0
        audience_label = _enum_or_text(_read(export, "audience", "unknown"))
        badges = [
            DiagnosticBadge(label=f"compiler:{audience_label}", kind="info"),
            DiagnosticBadge(label=f"claims:{claim_count}", kind="ok" if blocker_count == 0 else "warn"),
        ]
        if trust is not None and trust.research_dag_status:
            badges.append(
                DiagnosticBadge(
                    label=f"research:{trust.research_dag_status}",
                    kind="ok" if trust.research_dag_status == "available" else "warn",
                )
            )
        return cls(
            run_id=run_id,
            source_hash=_compute_source_hash(payload),
            verdict=Verdict.REVIEW if blocker_count else Verdict.APPROVE,
            confidence=Confidence.from_blocker_count(blocker_count, warning_count),
            policy_summary=policy_summary,
            intervention_count=0,
            diagnostic_badges=badges[:5],
            issues=issues,
            trust_provenance=trust,
            generated_at=generated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verdict"] = self.verdict.value
        payload["confidence"] = self.confidence.value
        payload["generated_at"] = self.generated_at.isoformat()
        return payload

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

        if self.diagnostic_badges:
            lines.append("## Diagnostics")
            lines.append("")
            lines.append(
                " | ".join(f"`{badge.kind}` {badge.label}" for badge in self.diagnostic_badges)
            )
            lines.append("")

        lines.append("## Policy")
        lines.append("")
        lines.append(self.policy_summary)
        if self.intervention_count > 0:
            lines.append("")
            lines.append(f"Interventions: **{self.intervention_count}**")
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
                assert metric.ci_lower is not None
                assert metric.ci_upper is not None
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

        if self.distributional is not None:
            lines.extend(_render_distributional(self.distributional))

        if self.trust_provenance is not None:
            lines.append("## Trust And Provenance")
            lines.append("")
            lines.append(
                f"Claims: **{self.trust_provenance.claim_count}** | "
                f"Blocked: **{self.trust_provenance.blocked_claim_count}** | "
                f"Research steps: **{self.trust_provenance.research_step_count}**"
            )
            if self.trust_provenance.continuous_governance_status:
                lines.append(
                    f"Continuous governance: {self.trust_provenance.continuous_governance_status}"
                )
            lines.append("")

        lines.append("## Issues")
        lines.append("")
        lines.append(
            f"**Blockers**: {self.issues.blocker_count} | "
            f"**Warnings**: {self.issues.warning_count} | "
            f"**Info**: {self.issues.info_count}"
        )
        if self.issues.blocked_passes:
            blocked = ", ".join(self.issues.blocked_passes)
            lines.append(f"Blocked passes: {blocked}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"*Duration: {self.total_duration_ms}ms*")
        lines.append("")
        return "\n".join(lines)


def _render_distributional(summary: DistributionalSummary) -> list[str]:
    lines: list[str] = ["## Distributional Impact", ""]
    if summary.gini_before is not None and summary.gini_after is not None:
        arrow = (
            "↑"
            if (summary.gini_delta or 0.0) > 0
            else "↓"
            if (summary.gini_delta or 0.0) < 0
            else "→"
        )
        lines.append(
            f"**Gini:** {summary.gini_before:.4f} → {summary.gini_after:.4f} "
            f"({arrow} {summary.gini_delta:+.4f})"
        )
        lines.append("")

    lines.append(
        f"**Winners:** {summary.winners_count} groups ({summary.winners_share:.0%} pop.) | "
        f"**Losers:** {summary.losers_count} groups ({summary.losers_share:.0%} pop.)"
    )
    if summary.vulnerable_losers_count > 0:
        lines.append(f"⚠️ Vulnerable losers: {summary.vulnerable_losers_count}")
    lines.append("")

    for dimension_label, rows in summary.breakdowns:
        lines.append(f"### {dimension_label}")
        lines.append("")
        lines.append("| Cohort | Pop. Share | Δ Primary | Dir. | Vuln. |")
        lines.append("|--------|-----------:|----------:|:----:|:-----:|")
        for row in rows:
            vulnerable = "⚠️" if row.is_vulnerable else ""
            lines.append(
                f"| {row.cohort_label} | {row.population_share:.0%} | "
                f"{row.primary_delta:+.2f}% | {row.direction} | {vulnerable} |"
            )
        lines.append("")

    return lines


def _read(obj: Any, key: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            logger.debug(
                "Failed to parse datetime from string: %r",
                raw,
                exc_info=True,
            )
            return datetime.now(UTC)
    return datetime.now(UTC)


def _compute_source_hash(packet: Any) -> str:
    payload = {
        "run_id": _read(packet, "run_id", None),
        "generated_at": _read(packet, "generated_at", None),
        "simulation_results": _read(packet, "simulation_results", None),
        "feedback": _read(packet, "feedback", _read(packet, "governance", None)),
        "distributional": _read(packet, "distributional", None),
        "diagnostics_summary": _read(packet, "diagnostics_summary", None),
        "analysis_limits": _read(packet, "analysis_limits", None),
    }
    canonical = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    return truncated_hash(canonical, length=16)


def _extract_verdict(feedback: Any) -> Verdict:
    if not isinstance(feedback, dict):
        return Verdict.REVIEW
    raw = str(feedback.get("verdict", "REVIEW")).strip().upper()
    if raw in {"APPROVE", "APPROVED", "PASS"}:
        return Verdict.APPROVE
    if raw in {"REJECT", "DENY", "BLOCK"}:
        return Verdict.REJECT
    return Verdict.REVIEW


def _extract_policy_summary(policy_ir: Any) -> tuple[str, int]:
    if policy_ir is None:
        return "N/A", 0
    if isinstance(policy_ir, dict):
        interventions = (
            _read(_read(policy_ir, "policy_spec", {}), "interventions", [])
            if isinstance(_read(policy_ir, "policy_spec", {}), dict)
            else []
        )
        if isinstance(interventions, list):
            count = len(interventions)
            return f"Policy with {count} intervention(s)", count
    return "Policy data attached", 0


def _extract_key_metrics(
    results: dict[str, Any] | None,
    *,
    uncertainty_bounds: Any | None = None,
) -> list[KeyMetric]:
    if not results or not isinstance(results, dict):
        return []

    bounds = uncertainty_bounds if isinstance(uncertainty_bounds, dict) else {}
    metrics: list[KeyMetric] = []
    specs: list[tuple[str, str, float, str]] = [
        ("gdp_change", "GDP Change", 100.0, "%"),
        ("unemployment_change", "Unemployment Change", 100.0, "%"),
        ("inflation_change", "Inflation Change", 100.0, "%"),
        ("gini_coefficient", "Gini Coefficient", 1.0, ""),
    ]

    for key, display_name, scale, unit in specs:
        value_raw = results.get(key)
        if not isinstance(value_raw, (int, float)):
            continue
        value = float(value_raw) * scale
        ci_lower = _safe_float(bounds.get(f"{key}_lower"))
        ci_upper = _safe_float(bounds.get(f"{key}_upper"))
        ci_level = _safe_float(bounds.get(f"{key}_ci_level"))
        metrics.append(
            KeyMetric(
                name=display_name,
                value=value,
                formatted=f"{value:+.2f}",
                unit=unit,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                ci_level=ci_level,
            )
        )

    if metrics:
        return metrics

    for key, value_raw in sorted(results.items()):
        if isinstance(value_raw, (int, float)):
            value = float(value_raw)
            metrics.append(
                KeyMetric(
                    name=key.replace("_", " ").title(),
                    value=value,
                    formatted=f"{value:+.2f}",
                )
            )
    return metrics


def _extract_issues_summary(feedback: Any) -> IssuesSummary:
    if not isinstance(feedback, dict):
        return IssuesSummary()
    issues = feedback.get("issues", [])
    if not isinstance(issues, list):
        return IssuesSummary()

    blocker_count = 0
    warning_count = 0
    info_count = 0
    blocked_passes: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", "")).strip().lower()
        pass_id = issue.get("pass_id")
        if severity == "blocker":
            blocker_count += 1
            if isinstance(pass_id, str):
                blocked_passes.add(pass_id)
        elif severity == "warning":
            warning_count += 1
        elif severity == "info":
            info_count += 1

    return IssuesSummary(
        blocker_count=blocker_count,
        warning_count=warning_count,
        info_count=info_count,
        blocked_passes=tuple(sorted(blocked_passes)),
    )


def _extract_diagnostic_badges(packet: Any) -> list[DiagnosticBadge]:
    badges_payload = _read(packet, "diagnostic_badges", None)
    if isinstance(badges_payload, list):
        badges: list[DiagnosticBadge] = []
        for item in badges_payload:
            if isinstance(item, dict):
                label = item.get("label")
                if isinstance(label, str):
                    kind = item.get("kind")
                    badges.append(
                        DiagnosticBadge(
                            label=label,
                            kind=str(kind) if isinstance(kind, str) else "info",
                        )
                    )
        if badges:
            return badges[:5]

    summary = _read(packet, "diagnostics_summary", None)
    if not isinstance(summary, dict):
        return []

    badges = [
        DiagnosticBadge(
            label=f"transport:{summary.get('transport_status', 'not_available')}",
            kind=_badge_kind_for_transport(summary.get("transport_status")),
        ),
        DiagnosticBadge(
            label=("legal:checked" if summary.get("legal_executed") is True else "legal:not_run"),
            kind="ok" if summary.get("legal_executed") is True else "warn",
        ),
        DiagnosticBadge(
            label=f"replay:{summary.get('replay_readiness', 'not_available')}",
            kind=_badge_kind_for_replay(summary.get("replay_readiness")),
        ),
        DiagnosticBadge(
            label=(
                "human-review:required"
                if summary.get("human_review_needed") is True
                else "human-review:not_required"
            ),
            kind="warn" if summary.get("human_review_needed") is True else "ok",
        ),
        DiagnosticBadge(
            label=(
                "uncertainty:available"
                if summary.get("uncertainty_available") is True
                else "uncertainty:not_available"
            ),
            kind="ok" if summary.get("uncertainty_available") is True else "warn",
        ),
    ]
    return badges[:5]


def _extract_distributional_summary(raw: Any) -> DistributionalSummary | None:
    if not isinstance(raw, dict):
        return None
    breakdowns_raw = raw.get("breakdowns")
    if not isinstance(breakdowns_raw, list):
        return None

    breakdowns: list[tuple[str, list[CohortSummaryRow]]] = []
    vulnerable_losers_count = 0
    for breakdown in breakdowns_raw:
        if not isinstance(breakdown, dict):
            continue
        label = str(breakdown.get("dimension_label", "Breakdown"))
        rows: list[CohortSummaryRow] = []
        for cohort in breakdown.get("cohorts", []):
            if not isinstance(cohort, dict):
                continue
            delta = _safe_float(cohort.get("delta"))
            if delta is None:
                continue
            direction = "+" if delta > 0.5 else "-" if delta < -0.5 else "~"
            is_vulnerable = bool(cohort.get("is_vulnerable", False))
            if is_vulnerable and delta < -0.5:
                vulnerable_losers_count += 1
            rows.append(
                CohortSummaryRow(
                    cohort_label=str(cohort.get("cohort_label", "Unknown")),
                    population_share=float(cohort.get("population_share", 0.0)),
                    primary_delta=delta,
                    direction=direction,
                    is_vulnerable=is_vulnerable,
                )
            )
        if rows:
            breakdowns.append((label, rows))

    if not breakdowns:
        return None

    return DistributionalSummary(
        breakdowns=breakdowns,
        gini_before=_safe_float(raw.get("overall_gini_before")),
        gini_after=_safe_float(raw.get("overall_gini_after")),
        gini_delta=_safe_float(raw.get("overall_gini_delta")),
        winners_count=int(raw.get("winners_count", 0) or 0),
        losers_count=int(raw.get("losers_count", 0) or 0),
        winners_share=float(raw.get("winners_share", 0.0) or 0.0),
        losers_share=float(raw.get("losers_share", 0.0) or 0.0),
        vulnerable_losers_count=vulnerable_losers_count,
    )


def _extract_duration_ms(packet: Any) -> int:
    run_timeline = _read(packet, "run_timeline", None)
    if not isinstance(run_timeline, dict):
        return 0
    summary = run_timeline.get("summary")
    if not isinstance(summary, dict):
        return 0
    value = summary.get("duration_ms")
    return int(value) if isinstance(value, (int, float)) else 0


def _extract_trust_provenance_summary(raw: Any) -> TrustProvenanceSummary | None:
    if not isinstance(raw, dict):
        return None
    claims_ref = raw.get("claims_ref")
    research_dag_ref = raw.get("research_dag_ref")
    if not isinstance(claims_ref, dict) or not isinstance(research_dag_ref, dict):
        return None
    claims_artifact_id = claims_ref.get("artifact_id")
    dag_artifact_id = research_dag_ref.get("artifact_id")
    if not isinstance(claims_artifact_id, str) or not isinstance(dag_artifact_id, str):
        return None
    return TrustProvenanceSummary(
        claims_ref=claims_artifact_id,
        research_dag_ref=dag_artifact_id,
        claim_count=int(raw.get("claim_count", 0) or 0),
        blocked_claim_count=int(raw.get("blocked_claim_count", 0) or 0),
        research_step_count=int(raw.get("research_step_count", 0) or 0),
        research_dag_status=(
            str(raw.get("research_dag_status")) if raw.get("research_dag_status") else None
        ),
        continuous_governance_status=(
            str(raw.get("continuous_governance_status"))
            if raw.get("continuous_governance_status")
            else None
        ),
    )


def _compiler_policy_summary(payload: dict[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    approved_claims = payload.get("approved_claims")
    if isinstance(approved_claims, list):
        for item in approved_claims:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                return item["text"]
    claim_export = payload.get("claim_ledger_export")
    if isinstance(claim_export, dict):
        for item in claim_export.get("claims", []) or []:
            if isinstance(item, dict) and item.get("visible") and isinstance(item.get("text"), str):
                return item["text"]
    return "Decision-grade output compiled from governed research artifacts."


def _enum_or_text(value: Any) -> str:
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _badge_kind_for_transport(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"direct", "transportable"}:
        return "ok"
    if normalized in {"non_transportable"}:
        return "fail"
    return "warn"


def _badge_kind_for_replay(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized == "complete":
        return "ok"
    if normalized == "incomplete":
        return "fail"
    return "warn"


__all__ = [
    "CohortSummaryRow",
    "Confidence",
    "DecisionCard",
    "DiagnosticBadge",
    "DistributionalSummary",
    "IssuesSummary",
    "KeyMetric",
    "TrustProvenanceSummary",
    "Verdict",
    "_extract_issues_summary",
    "_extract_key_metrics",
]
