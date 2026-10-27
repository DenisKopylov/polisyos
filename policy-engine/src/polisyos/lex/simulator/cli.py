"""Public simulator cli module API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.ir.loading.norm_pack import NormPack

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.lex.legal_evaluation.impact_diff import NormImpactReport


def load_norm_pack(cas: FileSystemCAS, ref_or_path: str) -> NormPack:
    """Load norm pack."""
    from polisyos.core.artifacts import load_core_json_artifact

    path = Path(ref_or_path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return NormPack.model_validate(payload)

    artifact_id = ArtifactID.model_validate(ref_or_path)
    payload = load_core_json_artifact(cas, artifact_id)
    return NormPack.model_validate(payload)


def render_impact_markdown(report: NormImpactReport) -> str:
    """Render impact markdown helper."""
    lines: list[str] = [
        "# Norm Impact Report",
        "",
        f"- Old pack: `{report.old_pack_id}`",
        f"- New pack: `{report.new_pack_id}`",
        f"- Report jurisdiction (old pack): `{report.jurisdiction}`",
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

    old_scope = report.metadata.get("declared_old_jurisdiction")
    new_scope = report.metadata.get("declared_new_jurisdiction")
    if isinstance(old_scope, str) and isinstance(new_scope, str):
        if old_scope != new_scope:
            lines.extend(
                [
                    "**Jurisdiction limitation:** Input pack declarations differ "
                    f"(old: `{old_scope}`, new: `{new_scope}`); compatibility is not established.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "**Jurisdiction limitation:** Both packs declare "
                    f"`{old_scope}`; source authenticity and applicability are not established.",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "**Jurisdiction limitation:** Both input pack declarations were not recorded; "
                "scope compatibility is not established.",
                "",
            ]
        )

    if report.schema_version == "1.0" and report.norm_diff_ref is not None:
        lines.extend(
            [
                "**Diff view limitation:** Legacy report does not bind the issued manifest profile.",
                "",
            ]
        )

    if "legal" in report.passes_executed:
        backend = report.metadata.get("legal_backend")
        if backend == "stub":
            limitation = "The report records the stub backend, which does not evaluate legal rules."
        elif backend == "expr_ast":
            limitation = (
                "The report records expr_ast, which evaluates only rules assigned to it; "
                "source authenticity, complete rule coverage, and comparison-context "
                "binding are not established."
            )
        else:
            limitation = "The legal backend or its evaluation scope is not established."
        lines.extend([f"**Legal evaluation limitation:** {limitation}", ""])

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
        lines.extend(
            [
                "## Candidate Impact Topics",
                "",
                (
                    "These are heuristic topics inferred from changed rule types, not measured "
                    "effects or legal conclusions."
                ),
                "",
            ]
        )
        for item in report.affected_kpis:
            norm_ids = ", ".join(item.affected_norm_ids)
            lines.append(f"- `{item.kpi_id}`: {item.description} ({norm_ids})")
        lines.append("")

    return "\n".join(lines)
