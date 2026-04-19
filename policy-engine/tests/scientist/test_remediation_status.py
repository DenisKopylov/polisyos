from __future__ import annotations

from polisyos.scientist.remediation_status import (
    WORKSTREAM_IDS,
    RemediationStatusLevel,
    build_scientist_remediation_status_report,
)


def test_scientist_remediation_status_report_covers_all_workstreams() -> None:
    report = build_scientist_remediation_status_report()

    assert report.assessment_id == "gate0_closure"
    assert report.strict_definition_of_done is True
    assert tuple(item.workstream_id for item in report.workstreams) == WORKSTREAM_IDS
    assert tuple(item.phase for item in report.phase_rollups) == (
        "Phase 0",
        "Phase 1",
        "Phase 2",
        "Phase 3",
        "Phase 4",
    )
    assert report.overall_status == RemediationStatusLevel.DONE


def test_scientist_remediation_status_report_is_machine_readable() -> None:
    report = build_scientist_remediation_status_report()

    payload = report.to_dict()

    assert payload["schema_version"] == "1.0"
    assert payload["overall_status"] == "done"
    assert payload["workstreams"][0]["workstream_id"] == "WS-0A"
    assert payload["workstreams"][-1]["workstream_id"] == "WS-4B"
    assert "repo-tracked closure view" in payload["notes"][0]


def test_scientist_remediation_status_report_marks_all_workstreams_done() -> None:
    report = build_scientist_remediation_status_report()

    ws_0a = next(item for item in report.workstreams if item.workstream_id == "WS-0A")
    ws_0b = next(item for item in report.workstreams if item.workstream_id == "WS-0B")
    ws_1a = next(item for item in report.workstreams if item.workstream_id == "WS-1A")
    ws_1b = next(item for item in report.workstreams if item.workstream_id == "WS-1B")
    ws_1c = next(item for item in report.workstreams if item.workstream_id == "WS-1C")
    ws_1d = next(item for item in report.workstreams if item.workstream_id == "WS-1D")
    phase_0 = next(item for item in report.phase_rollups if item.phase == "Phase 0")
    phase_1 = next(item for item in report.phase_rollups if item.phase == "Phase 1")
    ws_2a = next(item for item in report.workstreams if item.workstream_id == "WS-2A")
    ws_2b = next(item for item in report.workstreams if item.workstream_id == "WS-2B")
    ws_3a = next(item for item in report.workstreams if item.workstream_id == "WS-3A")
    ws_3b = next(item for item in report.workstreams if item.workstream_id == "WS-3B")
    ws_3c = next(item for item in report.workstreams if item.workstream_id == "WS-3C")
    ws_4a = next(item for item in report.workstreams if item.workstream_id == "WS-4A")
    ws_4b = next(item for item in report.workstreams if item.workstream_id == "WS-4B")
    phase_2 = next(item for item in report.phase_rollups if item.phase == "Phase 2")
    phase_3 = next(item for item in report.phase_rollups if item.phase == "Phase 3")
    phase_4 = next(item for item in report.phase_rollups if item.phase == "Phase 4")

    assert ws_0a.status == RemediationStatusLevel.DONE
    assert ws_0a.blocking_issues == ()
    assert ws_0b.status == RemediationStatusLevel.DONE
    assert ws_0b.blocking_issues == ()
    assert ws_1a.status == RemediationStatusLevel.DONE
    assert ws_1a.blocking_issues == ()
    assert ws_1b.status == RemediationStatusLevel.DONE
    assert ws_1b.blocking_issues == ()
    assert ws_1c.status == RemediationStatusLevel.DONE
    assert ws_1c.blocking_issues == ()
    assert ws_1d.status == RemediationStatusLevel.DONE
    assert ws_1d.blocking_issues == ()
    assert phase_0.status == RemediationStatusLevel.DONE
    assert phase_1.status == RemediationStatusLevel.DONE
    assert ws_2a.status == RemediationStatusLevel.DONE
    assert ws_2a.blocking_issues == ()
    assert ws_2b.status == RemediationStatusLevel.DONE
    assert ws_2b.blocking_issues == ()
    assert ws_3a.status == RemediationStatusLevel.DONE
    assert ws_3a.blocking_issues == ()
    assert ws_3b.status == RemediationStatusLevel.DONE
    assert ws_3b.blocking_issues == ()
    assert ws_3c.status == RemediationStatusLevel.DONE
    assert ws_3c.blocking_issues == ()
    assert phase_2.status == RemediationStatusLevel.DONE
    assert phase_3.status == RemediationStatusLevel.DONE
    assert ws_4a.status == RemediationStatusLevel.DONE
    assert ws_4a.blocking_issues == ()
    assert ws_4b.status == RemediationStatusLevel.DONE
    assert ws_4b.blocking_issues == ()
    assert phase_4.status == RemediationStatusLevel.DONE
