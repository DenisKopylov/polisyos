"""Render human-readable markdown summaries from audit verification reports."""

from __future__ import annotations

from collections.abc import Iterable

from .models import StepResult, StepStatus, VerificationIssue, VerificationReport


def render_markdown(report: VerificationReport) -> str:
    """Return a markdown report suitable for CLI/stdout and saved artifacts."""
    status = "✅ PASS" if report.overall_status == "PASS" else "❌ FAIL"
    lines: list[str] = [
        "# Policy OS Audit Verification Report",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Package | `{report.package_path}` |",
        f"| Run ID | `{report.run_id or 'unknown'}` |",
        f"| Verified at | {report.verified_at.isoformat()} |",
        f"| Verifier | {report.verifier_version} |",
        f"| **Overall Status** | **{status}** |",
        "",
        "## Summary",
        "",
        "| Check | Status | Passed | Failed | Skipped |",
        "|-------|--------|--------|--------|---------|",
    ]
    for step in _steps(report):
        lines.append(
            f"| {step.step_name} | {_status_icon(step.status)} {step.status.value} | "
            f"{step.checks_passed} | {step.checks_failed} | {step.checks_skipped} |"
        )

    lines.extend(
        [
            "",
            "## Counters",
            "",
            f"- Artifacts: {report.artifacts_checked}/{report.artifacts_total}",
            f"- Signatures: {report.signatures_valid}/{report.signatures_total}",
            (
                f"- Provenance: entities={report.prov_entities}, "
                f"activities={report.prov_activities}, agents={report.prov_agents}"
            ),
            "",
        ]
    )

    lines.append("## Failures")
    if report.failures:
        lines.extend(_render_issues(report.failures))
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Warnings")
    if report.warnings:
        lines.extend(_render_issues(report.warnings))
    else:
        lines.append("- None")
    lines.append("")

    if report.environment:
        lines.extend(
            [
                "## Environment",
                "",
                "| Key | Value |",
                "|-----|-------|",
            ]
        )
        for key, value in sorted(report.environment.items(), key=lambda item: item[0]):
            lines.append(f"| {key} | {value} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _steps(report: VerificationReport) -> list[StepResult]:
    return [
        report.package_integrity,
        report.cas_integrity,
        report.signature_verification,
        report.provenance_validation,
        report.dependency_completeness,
        report.slsa_verification,
    ]


def _render_issues(issues: Iterable[VerificationIssue]) -> list[str]:
    lines: list[str] = []
    for issue in issues:
        suffix = f" ({issue.path})" if issue.path else ""
        lines.append(f"- `{issue.code}`{suffix}: {issue.message}")
    return lines


def _status_icon(status: StepStatus) -> str:
    if status == StepStatus.PASS:
        return "✅"
    if status == StepStatus.FAIL:
        return "❌"
    if status == StepStatus.WARN:
        return "⚠️"
    return "⏭️"
