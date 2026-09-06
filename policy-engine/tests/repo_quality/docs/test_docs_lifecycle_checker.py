from __future__ import annotations

from pathlib import Path

from tools.quality.validation import check_docs_lifecycle

OLD_FRONTEND_DASHBOARD = "frontend" + "/runtime-dashboard"
CANONICAL_FRONTEND_DASHBOARD = "apps" + "/runtime-dashboard"
EVIDENCE_START = "<!-- docs-lifecycle-evidence:start -->"
EVIDENCE_END = "<!-- docs-lifecycle-evidence:end -->"


def _format_finding(finding: check_docs_lifecycle.LifecycleFinding) -> str:
    return f"- [{finding.check}] {finding.path}: {finding.message}"


def _current_six_findings() -> tuple[check_docs_lifecycle.LifecycleFinding, ...]:
    stale_message = (
        f"stale direct reference `{OLD_FRONTEND_DASHBOARD}`; "
        f"use `{CANONICAL_FRONTEND_DASHBOARD}`."
    )
    return (
        check_docs_lifecycle.LifecycleFinding(
            "active_plan_metadata",
            "docs/plans/active/LEDGER.md",
            "active plan missing `status` front matter.",
        ),
        check_docs_lifecycle.LifecycleFinding(
            "active_plan_metadata",
            "docs/plans/active/LEDGER.md",
            "active plan missing `owner` front matter.",
        ),
        *(
            check_docs_lifecycle.LifecycleFinding(
                "removed_stub_reference",
                path,
                stale_message,
            )
            for path in (
                "architecture/atlas_surfaces/atlas-v15-adoption-ledger.json",
                "architecture/atlas_surfaces/atlas-v15-archive-map.json",
                "docs/reference/frontend/atlas-v15-adjudication.md",
                "docs/research/policy-operations/audits/"
                "pao-r0/pao-r0-test-and-fixture-verification.md",
            )
        ),
    )


def test_quoted_evidence_is_not_a_live_reference(tmp_path: Path) -> None:
    """Verbatim gate evidence does not become a seventh live finding."""

    current_six = _current_six_findings()
    for finding in current_six[2:]:
        target = tmp_path / finding.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(OLD_FRONTEND_DASHBOARD, encoding="utf-8")

    live_findings = tuple(check_docs_lifecycle.check_removed_stub_references(tmp_path))
    assert current_six[:2] + live_findings == current_six

    journal = tmp_path / "docs/superpowers/journals/task-closeout.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(
        "\n".join(
            (
                EVIDENCE_START,
                "```text",
                "Docs lifecycle gate FAILED:",
                *map(_format_finding, current_six),
                "```",
                EVIDENCE_END,
                "",
            )
        ),
        encoding="utf-8",
    )

    quoted_findings = tuple(check_docs_lifecycle.check_removed_stub_references(tmp_path))
    assert current_six[:2] + quoted_findings == current_six

    unclosed = tmp_path / "docs/unclosed-evidence.md"
    unclosed.write_text(
        f"{EVIDENCE_START}\n{OLD_FRONTEND_DASHBOARD}\n",
        encoding="utf-8",
    )
    fenced = tmp_path / "docs/ordinary-fence.md"
    fenced.write_text(
        f"```text\n{OLD_FRONTEND_DASHBOARD}\n```\n",
        encoding="utf-8",
    )

    divergent_paths = {
        finding.path
        for finding in check_docs_lifecycle.check_removed_stub_references(tmp_path)
    }
    assert "docs/unclosed-evidence.md" in divergent_paths
    assert "docs/ordinary-fence.md" in divergent_paths
