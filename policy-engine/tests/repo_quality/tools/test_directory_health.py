from __future__ import annotations

from pathlib import Path

from tools.devx.workspace import clean_local_reports
from tools.quality.validation import directory_health


def test_phase1_3_phase_local_junk_build_residue_fails_hygiene(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    (residue / "audit.tar.gz").write_text("local residue\n", encoding="utf-8")

    findings = directory_health._phase_local_junk_findings(tmp_path, {})

    assert findings == [
        directory_health.Finding(
            "phase-local-junk-residue",
            "blocker",
            "_build/phase7-local-junk-20260505T092233Z",
            "phase-local-junk build residue must be deleted or registered as a dated "
            "scratch exception",
        )
    ]


def test_phase1_3_phase_local_junk_exception_requires_explicit_scratch_policy(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    contract = {
        "health_exception": [
            {
                "kind": "phase_local_junk_residue",
                "source_glob": "_build/phase7-local-junk-20260505T092233Z",
            }
        ]
    }

    findings = directory_health._phase_local_junk_findings(tmp_path, contract)

    assert findings == [
        directory_health.Finding(
            "phase-local-junk-residue",
            "blocker",
            "_build/phase7-local-junk-20260505T092233Z",
            "phase-local-junk build residue must be deleted or registered as a dated "
            "scratch exception",
        )
    ]


def test_phase1_3_registered_phase_local_junk_exception_is_allowed(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    contract = {
        "health_exception": [
            {
                "kind": "phase_local_junk_residue",
                "scratch_policy": "explicitly_ignored",
                "source_glob": "_build/phase7-local-junk-20260505T092233Z",
            }
        ]
    }

    assert directory_health._phase_local_junk_findings(tmp_path, contract) == []


def test_phase1_3_clean_local_reports_collects_phase_local_junk_roots(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    (residue / "audit.tar.gz").write_text("local residue\n", encoding="utf-8")
    reviewed_report = tmp_path / "docs" / "archive" / "reports" / "reviewed.md"
    reviewed_report.parent.mkdir(parents=True)
    reviewed_report.write_text("reviewed evidence\n", encoding="utf-8")
    baseline = tmp_path / "architecture" / "baselines" / "reviewed" / "summary.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("{}", encoding="utf-8")

    plan = clean_local_reports.build_cleanup_plan(tmp_path)
    candidates = {item["path"]: item for item in plan["candidates"]}

    assert candidates["_build/phase7-local-junk-20260505T092233Z"] == {
        "path": "_build/phase7-local-junk-20260505T092233Z",
        "kind": "phase_local_junk_residue",
        "reason": "ignored phase-local-junk build residue",
        "owner_approval_required": False,
    }
    assert "docs/archive/reports/reviewed.md" not in candidates
    assert "architecture/baselines/reviewed/summary.json" not in candidates
