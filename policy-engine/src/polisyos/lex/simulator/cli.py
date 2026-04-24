"""Public simulator cli module API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.norm_pack import NormPack

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

    from .report import NormImpactReport


def load_norm_pack(cas: FileSystemCAS, ref_or_path: str) -> NormPack:
    """Load norm pack."""
    path = Path(ref_or_path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return NormPack.model_validate(payload)

    artifact_id = ArtifactID.model_validate(ref_or_path)
    payload = from_canonical_bytes(cas.get_bytes(artifact_id))
    return NormPack.model_validate(payload)


def render_impact_markdown(report: NormImpactReport) -> str:
    """Render impact markdown helper."""
    lines: list[str] = [
        "# Norm Impact Report",
        "",
        f"- Old pack: `{report.old_pack_id}`",
        f"- New pack: `{report.new_pack_id}`",
        f"- Jurisdiction: `{report.jurisdiction}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Norms added | {report.norms_added} |",
        f"| Norms removed | {report.norms_removed} |",
        f"| Norms modified | {report.norms_modified} |",
        f"| New blockers | {report.new_blockers} |",
        f"| Resolved blockers | {report.resolved_blockers} |",
        f"| New warnings | {report.new_warnings} |",
        f"| Resolved warnings | {report.resolved_warnings} |",
        "",
    ]

    if report.compliance_deltas:
        lines.extend(["## Compliance Changes", ""])
        for delta in report.compliance_deltas:
            message = "n/a"
            if delta.new_issue is not None:
                message = delta.new_issue.message
            elif delta.old_issue is not None:
                message = delta.old_issue.message
            lines.append(
                f"- `{delta.norm_id}` {delta.transition.value} [{delta.pass_id}] - {message}"
            )
        lines.append("")

    if report.affected_kpis:
        lines.extend(["## Affected KPIs", ""])
        for item in report.affected_kpis:
            norm_ids = ", ".join(item.affected_norm_ids)
            lines.append(f"- `{item.kpi_id}`: {item.description} ({norm_ids})")
        lines.append("")

    return "\n".join(lines)
