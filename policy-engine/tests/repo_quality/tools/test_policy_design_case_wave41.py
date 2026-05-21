from __future__ import annotations

# ruff: noqa: S101
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_PLAN = (
    REPO_ROOT
    / "docs"
    / "plans"
    / "active"
    / "POLICYOS_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
)
ARCHIVED_PLAN = (
    REPO_ROOT
    / "docs"
    / "plans"
    / "archive"
    / "2026-05-19-policyos-policy-design-case-implementation-plan.md"
)
BACKLOG = REPO_ROOT / "docs" / "backlog" / "production-data-e2e-diagnostic-backlog.md"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "policy-design-case-operator-triage.md"
DECISION_LOG = (
    REPO_ROOT / "docs" / "system-design-decisions" / "policy-design-case-decision-log.md"
)
CLOSEOUT_REPORT = (
    REPO_ROOT / "docs" / "archive" / "reports" / "2026-05-19-policy-design-case-wave41-closeout.md"
)

PASS2_FRAGMENT_PDDS = (
    "PDD-034",
    "PDD-037",
    "PDD-038",
    "PDD-044",
    "PDD-046",
    "PDD-048",
    "PDD-050",
    "PDD-051",
    "PDD-055",
    "PDD-056",
    "PDD-057",
    "PDD-064",
    "PDD-065",
    "PDD-069",
    "PDD-077",
    "PDD-078",
    "PDD-083",
    "PDD-087",
    "PDD-088",
    "PDD-090",
    "PDD-097",
    "PDD-098",
    "PDD-099",
    "PDD-100",
    "PDD-101",
    "PDD-103",
    "PDD-104",
)

RUNBOOK_FAILURE_MODES = (
    "Missing case",
    "Missing intent",
    "Missing spine",
    "Missing producer refs",
    "Portfolio divergence",
    "Synthesis fragility",
    "Unsupported claim",
    "BERL failure",
    "DDM failure",
    "External audit failure",
    "Self-FMEA failure",
    "Maturity regression",
    "Missing formal invariant",
    "Missing consultation response",
    "Hidden expert judgement",
    "Proportionality failure",
    "Benchmarking failure",
)

CLOSEOUT_EVIDENCE_PATHS = (
    "_build/policy-design-case/rebaseline/wave-35H/wave35h_exit_fence.json",
    "_build/policy-design-case/rebaseline/wave-35H/wave35h_provenance_integrity_report.json",
    "_build/policy-design-case/rebaseline/wave-40/wave40_readiness_bundle_inspection.json",
    "_build/policy-design-case/rebaseline/wave-40/wave40_exit_fence.json",
)


def test_wave41_archives_plan_after_recording_closeout_evidence() -> None:
    assert not ACTIVE_PLAN.exists()
    assert ARCHIVED_PLAN.is_file()
    plan = ARCHIVED_PLAN.read_text(encoding="utf-8")
    report = CLOSEOUT_REPORT.read_text(encoding="utf-8")

    assert "status: archived" in plan
    assert re.search(r"(?m)^- \[ \]", plan) is None
    assert "2026-05-19-policy-design-case-wave41-closeout.md" in plan
    assert "## Remaining Limitations" in report
    for path in CLOSEOUT_EVIDENCE_PATHS:
        assert path in report


def test_wave41_backlog_merges_every_generated_pass2_fragment() -> None:
    backlog = BACKLOG.read_text(encoding="utf-8")

    assert "## Wave 41 - Generated Pass 2 Diagnostic Fragment Merge" in backlog
    for pdd_id in PASS2_FRAGMENT_PDDS:
        fragment = f"repo://_build/diagnostics/pass2/backlog_fragments/{pdd_id.lower()}.md"
        assert f"`{pdd_id}`" in backlog
        assert fragment in backlog


def test_wave41_operator_runbook_covers_required_failure_modes() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    for failure_mode in RUNBOOK_FAILURE_MODES:
        assert f"| {failure_mode} |" in runbook


def test_wave41_decision_log_retired_due_policy_design_entries() -> None:
    text = DECISION_LOG.read_text(encoding="utf-8")
    closeout_entry = _entry_body(text, "DL-PDC-0016")

    assert "- **Promotion status**: retired" in closeout_entry
    assert "Wave 41" in closeout_entry
    for number in range(1, 16):
        assert f"DL-PDC-{number:04d}" in closeout_entry

    closed = set(re.findall(r"DL-PDC-\d{4}", closeout_entry))
    due_pending: list[str] = []
    for entry_id, body in _entry_bodies(text).items():
        if entry_id == "DL-PDC-0016" or entry_id in closed:
            continue
        status = _field(body, "Promotion status")
        revisit_wave = _field(body, "Revisit wave")
        wave_match = re.search(r"Wave\s+(\d+)", revisit_wave or "")
        wave = int(wave_match.group(1)) if wave_match else None
        if status == "log_only_pending_revisit" and wave is not None and wave <= 41:
            due_pending.append(entry_id)

    assert due_pending == []


def _entry_bodies(source: str) -> dict[str, str]:
    blocks = re.finditer(
        r"^### (?P<entry_id>DL-PDC-\d{4})\b.*?\n(?P<body>.*?)(?=^### DL-PDC-\d{4}\b|\Z)",
        source.split("\n## Entries\n", maxsplit=1)[1],
        flags=re.MULTILINE | re.DOTALL,
    )
    return {match.group("entry_id"): match.group("body") for match in blocks}


def _entry_body(source: str, entry_id: str) -> str:
    entries = _entry_bodies(source)
    return entries[entry_id]


def _field(body: str, field: str) -> str | None:
    match = re.search(rf"^- \*\*{re.escape(field)}\*\*: (?P<value>.+)$", body, re.M)
    return match.group("value") if match else None
