from __future__ import annotations

from pathlib import Path

from tools.devx.workspace import acceptance_audit


def test_acceptance_audit_has_no_automated_blockers_for_repo() -> None:
    report = acceptance_audit.run_audit()

    automated_blockers = [check for check in report.blockers if check.kind == "automated"]
    assert automated_blockers == []
    assert any(
        check.check_id == "toolchain-consistency" and check.status == "pass"
        for check in report.checks
    )


def test_acceptance_audit_accepts_complete_manual_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "platform-acceptance.toml"
    evidence.write_text(
        "\n".join(
            [
                "[manual]",
                "clean_machine_bootstrap = true",
                "backend_walkthrough = true",
                "frontend_walkthrough = true",
                "platform_walkthrough = true",
                "release_dry_run = true",
                "incident_tabletop = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = acceptance_audit.run_audit(
        manual_evidence=acceptance_audit.load_manual_evidence(evidence),
        require_manual_evidence=True,
        manual_path=evidence,
    )

    assert report.blockers == ()
    assert all(check.status == "pass" for check in report.checks if check.kind == "manual")


def test_acceptance_audit_supports_structured_manual_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "platform-acceptance.toml"
    evidence.write_text(
        "\n".join(
            [
                "[manual.clean_machine_bootstrap]",
                "status = true",
                'notes = "Fresh local rehearsal succeeded."',
                'evidence = ["docs/archive/reports/platform-acceptance-manual.md"]',
                "",
                "[manual.backend_walkthrough]",
                "status = false",
                'notes = "Backend gate is blocked by one benchmark failure."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = acceptance_audit.run_audit(
        manual_evidence=acceptance_audit.load_manual_evidence(evidence),
        require_manual_evidence=True,
        manual_path=evidence,
    )

    clean_bootstrap = next(
        check for check in report.checks if check.check_id == "manual.clean_machine_bootstrap"
    )
    backend_walkthrough = next(
        check for check in report.checks if check.check_id == "manual.backend_walkthrough"
    )

    assert clean_bootstrap.status == "pass"
    assert "Fresh local rehearsal succeeded." in clean_bootstrap.detail
    assert "docs/archive/reports/platform-acceptance-manual.md" in clean_bootstrap.evidence
    assert backend_walkthrough.status == "fail"
    assert "benchmark failure" in backend_walkthrough.detail
