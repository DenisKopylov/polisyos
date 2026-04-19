from __future__ import annotations

from tools.workspace import core_runtime_closeout


def test_core_runtime_closeout_ledger_loads_and_matches_expected_blockers() -> None:
    report = core_runtime_closeout.run_closeout(
        ledger_path=core_runtime_closeout.DEFAULT_LEDGER_PATH,
        plan_path=core_runtime_closeout.DEFAULT_PLAN_PATH,
    )

    assert [entry.workstream_id for entry in report.workstreams] == [
        "WS-0A",
        "WS-0B",
        "WS-0C",
        "WS-0D",
        "WS-1A",
        "WS-1B",
        "WS-1C",
        "WS-1D",
        "WS-2A",
        "WS-2B",
        "WS-2C",
        "WS-2D",
        "WS-3A",
        "WS-3B",
        "WS-3C",
    ]
    assert report.blocking_workstreams == ()


def test_core_runtime_closeout_supports_complete_manual_evidence(tmp_path) -> None:
    evidence = tmp_path / "core-runtime-closeout.toml"
    evidence.write_text(
        "\n".join(
            [
                "[manual]",
                "engineering_signoff = true",
                "operator_signoff = true",
                "release_review_bundle = true",
                "reopened_followups = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = core_runtime_closeout.run_closeout(
        ledger_path=core_runtime_closeout.DEFAULT_LEDGER_PATH,
        plan_path=core_runtime_closeout.DEFAULT_PLAN_PATH,
        manual_evidence=core_runtime_closeout.load_manual_evidence(evidence),
        require_manual_evidence=True,
        manual_path=evidence,
    )

    assert all(check.status == "pass" for check in report.manual_checks)


def test_core_runtime_closeout_summary_and_exit_codes(tmp_path) -> None:
    summary = tmp_path / "core-runtime-closeout.md"

    assert (
        core_runtime_closeout.main(
            [
                "--summary",
                str(summary),
            ]
        )
        == 0
    )
    rendered = summary.read_text(encoding="utf-8")
    assert "WS-2A" in rendered
    assert "Reopen / Residual Gaps" in rendered

    assert core_runtime_closeout.main(["--require-full-closeout"]) == 0
