from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.scientist.orchestrator.decision_packet import DecisionPacket


class Verdict:
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_REVISION = "NEEDS_REVISION"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


class Confidence:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @classmethod
    def from_blocker_count(cls, blocker_count: int, warning_count: int = 0) -> str:
        if blocker_count == 0 and warning_count == 0:
            return cls.HIGH
        if blocker_count == 0:
            return cls.MEDIUM
        return cls.LOW


@dataclass(frozen=True)
class KeyMetric:
    name: str
    value: float
    formatted: str
    unit: Optional[str] = None
    delta_from_baseline: Optional[float] = None


@dataclass(frozen=True)
class IssuesSummary:
    blocker_count: int
    warning_count: int
    info_count: int
    blocked_passes: List[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return self.blocker_count + self.warning_count + self.info_count

    @property
    def has_blockers(self) -> bool:
        return self.blocker_count > 0


@dataclass(frozen=True)
class ArtifactReference:
    artifact_type: str
    ref: str
    label: str


@dataclass
class DecisionCard:
    """
    Deterministic human-readable summary of a DecisionPacket.

    IMPORTANT: Construction is deterministic given the packet. For reproducibility we derive
    generated_at from packet.generated_at when available (DecisionPacket already timestamps itself).
    """

    run_id: str
    generated_at: datetime
    schema_version: str = "1.0"

    verdict: str = Verdict.UNKNOWN
    confidence: str = Confidence.LOW

    policy_summary: str = "No policy defined"
    intervention_count: int = 0

    key_metrics: List[KeyMetric] = field(default_factory=list)
    issues: IssuesSummary = field(default_factory=lambda: IssuesSummary(0, 0, 0))

    total_duration_ms: int = 0
    phase_count: int = 0

    references: List[ArtifactReference] = field(default_factory=list)
    source_hash: Optional[str] = None

    def render_markdown(self) -> str:
        lines: List[str] = [
            f"# Decision Card: {self.run_id}",
            "",
            "---",
            "",
            "## Summary",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| **Generated** | {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')} |",
            f"| **Verdict** | {self._verdict_emoji()} **{self.verdict}** |",
            f"| **Confidence** | {self.confidence} |",
            f"| **Duration** | {self._format_duration()} |",
            "",
            "## Policy",
            "",
            self.policy_summary,
            "",
        ]

        if self.intervention_count > 0:
            lines.append(f"*{self.intervention_count} intervention(s) defined*")
            lines.append("")

        if self.key_metrics:
            lines.extend(
                [
                    "## Key Metrics",
                    "",
                    "| Metric | Value |",
                    "|--------|-------|",
                ]
            )
            for metric in self.key_metrics:
                unit_str = f" {metric.unit}" if metric.unit else ""
                lines.append(f"| {metric.name} | {metric.formatted}{unit_str} |")
            lines.append("")

        lines.extend(
            [
                "## Compliance",
                "",
                f"- **Blockers**: {self.issues.blocker_count}",
                f"- **Warnings**: {self.issues.warning_count}",
                f"- **Info**: {self.issues.info_count}",
            ]
        )
        if self.issues.blocked_passes:
            lines.append(f"- **Failed Passes**: {', '.join(self.issues.blocked_passes)}")
        lines.append("")

        if self.references:
            lines.extend(["## References", ""])
            for ref in self.references:
                lines.append(f"- **{ref.label}**: `{ref.ref}`")
            lines.append("")

        lines.extend(
            [
                "---",
                "",
                f"*Schema v{self.schema_version} | Source hash: {self.source_hash or 'N/A'}*",
            ]
        )
        return "\n".join(lines)

    def _verdict_emoji(self) -> str:
        return {
            Verdict.APPROVE: "✅",
            Verdict.REJECT: "❌",
            Verdict.NEEDS_REVISION: "🔄",
            Verdict.PENDING: "⏳",
        }.get(self.verdict, "❓")

    def _format_duration(self) -> str:
        if self.total_duration_ms < 1000:
            return f"{self.total_duration_ms}ms"
        if self.total_duration_ms < 60000:
            return f"{self.total_duration_ms / 1000:.1f}s"
        minutes = self.total_duration_ms // 60000
        seconds = (self.total_duration_ms % 60000) / 1000
        return f"{minutes}m {seconds:.0f}s"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat(),
            "verdict": self.verdict,
            "confidence": self.confidence,
            "policy_summary": self.policy_summary,
            "intervention_count": self.intervention_count,
            "key_metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "formatted": m.formatted,
                    "unit": m.unit,
                    "delta_from_baseline": m.delta_from_baseline,
                }
                for m in self.key_metrics
            ],
            "issues": {
                "blocker_count": self.issues.blocker_count,
                "warning_count": self.issues.warning_count,
                "info_count": self.issues.info_count,
                "blocked_passes": list(self.issues.blocked_passes),
            },
            "total_duration_ms": self.total_duration_ms,
            "phase_count": self.phase_count,
            "references": [
                {"artifact_type": r.artifact_type, "ref": r.ref, "label": r.label}
                for r in self.references
            ],
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionCard":
        generated_at = datetime.fromisoformat(data["generated_at"])
        issues_raw = data.get("issues") or {}
        key_metrics = [
            KeyMetric(
                name=m["name"],
                value=float(m["value"]),
                formatted=m["formatted"],
                unit=m.get("unit"),
                delta_from_baseline=m.get("delta_from_baseline"),
            )
            for m in (data.get("key_metrics") or [])
        ]
        references = [
            ArtifactReference(
                artifact_type=r["artifact_type"],
                ref=r["ref"],
                label=r["label"],
            )
            for r in (data.get("references") or [])
        ]
        return cls(
            run_id=data["run_id"],
            generated_at=generated_at,
            schema_version=data.get("schema_version", "1.0"),
            verdict=data.get("verdict", Verdict.UNKNOWN),
            confidence=data.get("confidence", Confidence.LOW),
            policy_summary=data.get("policy_summary", "No policy defined"),
            intervention_count=int(data.get("intervention_count", 0) or 0),
            key_metrics=key_metrics,
            issues=IssuesSummary(
                blocker_count=int(issues_raw.get("blocker_count", 0) or 0),
                warning_count=int(issues_raw.get("warning_count", 0) or 0),
                info_count=int(issues_raw.get("info_count", 0) or 0),
                blocked_passes=list(issues_raw.get("blocked_passes") or []),
            ),
            total_duration_ms=int(data.get("total_duration_ms", 0) or 0),
            phase_count=int(data.get("phase_count", 0) or 0),
            references=references,
            source_hash=data.get("source_hash"),
        )

    @classmethod
    def from_packet(cls, packet: "DecisionPacket") -> "DecisionCard":
        import hashlib
        import json

        # Deterministic timestamp: prefer packet.generated_at, else fall back.
        gen_ts = _packet_generated_at(packet)

        source_data = {
            "run_id": packet.run_id,
            "policy_ir_hash": _hash_policy_ir(getattr(packet, "policy_ir", None)),
            "sim_results": getattr(packet, "simulation_results", None),
            "feedback": _feedback_dump(getattr(packet, "feedback", None)),
        }
        source_hash = (
            hashlib.sha256(json.dumps(source_data, sort_keys=True, default=str).encode())
            .hexdigest()[:16]
        )

        policy_ir = getattr(packet, "policy_ir", None)
        simulation_results = getattr(packet, "simulation_results", None)
        feedback = getattr(packet, "feedback", None)

        policy_summary = _extract_policy_summary(policy_ir)
        intervention_count = _count_interventions(policy_ir)
        key_metrics = _extract_key_metrics(simulation_results)
        issues = _extract_issues_summary(feedback)

        verdict = _get_verdict(feedback)
        confidence = Confidence.from_blocker_count(issues.blocker_count, issues.warning_count)

        total_duration_ms = 0
        phase_count = 0
        run_timeline = getattr(packet, "run_timeline", None)
        if isinstance(run_timeline, dict):
            total_duration_ms = int(run_timeline.get("total_duration_ms", 0) or 0)
            phase_count = sum(
                1 for e in (run_timeline.get("events") or []) if e.get("event_type") == "phase_start"
            )

        references = _build_references(packet)

        return cls(
            run_id=packet.run_id,
            generated_at=gen_ts,
            verdict=verdict,
            confidence=confidence,
            policy_summary=policy_summary,
            intervention_count=intervention_count,
            key_metrics=key_metrics,
            issues=issues,
            total_duration_ms=total_duration_ms,
            phase_count=phase_count,
            references=references,
            source_hash=source_hash,
        )


def _packet_generated_at(packet: Any) -> datetime:
    ts = getattr(packet, "generated_at", None)
    if isinstance(ts, str):
        try:
            parsed = datetime.fromisoformat(ts)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _feedback_dump(feedback: Any) -> Any:
    if feedback is None:
        return None
    if hasattr(feedback, "model_dump"):
        try:
            return feedback.model_dump()
        except Exception:
            return str(feedback)
    return feedback


def _hash_policy_ir(policy_ir: Optional[Any]) -> str:
    if policy_ir is None:
        return "none"
    try:
        import hashlib
        import json

        data = (
            policy_ir.model_dump(mode="json")
            if hasattr(policy_ir, "model_dump")
            else str(policy_ir)
        )
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:8]
    except Exception:
        return "error"


def _extract_policy_summary(policy_ir: Optional[Any]) -> str:
    if policy_ir is None:
        return "No policy defined"
    try:
        semantic = getattr(policy_ir, "semantic", None)
        if semantic is not None:
            interventions = getattr(semantic, "interventions", []) or []
            if interventions:
                names = [getattr(i, "name", str(i)) for i in interventions[:3]]
                suffix = f" (+{len(interventions) - 3} more)" if len(interventions) > 3 else ""
                return f"Policy with interventions: {', '.join(names)}{suffix}"
        return "Policy defined (details unavailable)"
    except Exception:
        return "Policy defined (parsing error)"


def _count_interventions(policy_ir: Optional[Any]) -> int:
    if policy_ir is None:
        return 0
    try:
        semantic = getattr(policy_ir, "semantic", None)
        interventions = getattr(semantic, "interventions", None)
        if interventions is not None:
            return len(interventions)
    except Exception:
        pass
    return 0


def _extract_key_metrics(simulation_results: Optional[Dict[str, Any]]) -> List[KeyMetric]:
    if not simulation_results:
        return []

    metrics: List[KeyMetric] = []
    metric_configs = [
        ("gdp_change", "GDP Change", "%", lambda v: f"{v * 100:+.2f}"),
        ("budget_deficit", "Budget Deficit", "%", lambda v: f"{v * 100:.2f}"),
        ("gini_coefficient", "Gini Coefficient", None, lambda v: f"{v:.4f}"),
        ("unemployment_rate", "Unemployment", "%", lambda v: f"{v * 100:.1f}"),
        ("welfare_change", "Welfare Change", "%", lambda v: f"{v * 100:+.2f}"),
    ]

    for key, name, unit, formatter in metric_configs:
        if key not in simulation_results:
            continue
        value = simulation_results[key]
        if isinstance(value, (int, float)):
            metrics.append(
                KeyMetric(
                    name=name,
                    value=float(value),
                    formatted=formatter(value),
                    unit=unit,
                )
            )

    return metrics


def _extract_issues_summary(feedback: Optional[Any]) -> IssuesSummary:
    if feedback is None:
        return IssuesSummary(0, 0, 0)

    issues: Any = []
    if hasattr(feedback, "issues"):
        issues = getattr(feedback, "issues", []) or []
    elif isinstance(feedback, dict):
        issues = feedback.get("issues", []) or []

    blocker_count = 0
    warning_count = 0
    info_count = 0
    blocked_passes: set[str] = set()

    for issue in issues:
        severity = issue.get("severity", "") if isinstance(issue, dict) else getattr(issue, "severity", "")
        severity_str = str(severity).lower()

        if "blocker" in severity_str:
            blocker_count += 1
            pass_id = issue.get("pass_id") if isinstance(issue, dict) else getattr(issue, "pass_id", None)
            if pass_id:
                blocked_passes.add(str(pass_id))
        elif "warning" in severity_str:
            warning_count += 1
        else:
            info_count += 1

    return IssuesSummary(
        blocker_count=blocker_count,
        warning_count=warning_count,
        info_count=info_count,
        blocked_passes=sorted(blocked_passes),
    )


def _get_verdict(feedback: Optional[Any]) -> str:
    if feedback is None:
        return Verdict.UNKNOWN

    verdict = None
    if hasattr(feedback, "verdict"):
        verdict = getattr(feedback, "verdict", None)
    elif isinstance(feedback, dict):
        verdict = feedback.get("verdict")

    if verdict in (Verdict.APPROVE, Verdict.REJECT, Verdict.NEEDS_REVISION, Verdict.PENDING):
        return str(verdict)
    return Verdict.UNKNOWN


def _build_references(packet: Any) -> List[ArtifactReference]:
    refs: List[ArtifactReference] = []
    run_id = getattr(packet, "run_id", "unknown")

    if getattr(packet, "policy_ir", None) is not None:
        refs.append(ArtifactReference(artifact_type="policy_ir", ref=f"run/{run_id}/policy_ir", label="Policy IR"))

    if getattr(packet, "simulation_results", None) is not None:
        refs.append(
            ArtifactReference(
                artifact_type="simulation_results",
                ref=f"run/{run_id}/simulation_results",
                label="Simulation Results",
            )
        )

    evidence_ref = getattr(packet, "evidence_ref", None)
    if evidence_ref is not None:
        bundle_id = getattr(evidence_ref, "bundle_id", None)
        refs.append(
            ArtifactReference(
                artifact_type="evidence_bundle",
                ref=str(bundle_id) if bundle_id is not None else str(evidence_ref),
                label="Evidence Bundle",
            )
        )

    if getattr(packet, "validation_trace", None):
        refs.append(
            ArtifactReference(
                artifact_type="validation_trace",
                ref=f"run/{run_id}/validation_trace",
                label="Validation Trace",
            )
        )

    return refs

