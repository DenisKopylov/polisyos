from __future__ import annotations

from datetime import UTC, datetime

from polisyos.core.security.quality_gates import (
    build_security_assurance_report,
    security_gates_from_report,
)


def test_report_pass_projection_can_be_suppressed_without_suppressing_failures() -> None:
    now = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
    valid_pass = build_security_assurance_report(payloads={}, now=now)
    assert valid_pass["status"] == "pass"
    default_gates = security_gates_from_report(valid_pass)
    assert [gate["code"] for gate in default_gates] == ["security_assurance_passed"]
    assert security_gates_from_report(valid_pass, include_report_gate=False) == []

    valid_failure = build_security_assurance_report(
        payloads={"artifact": {"rendered_content": "<script>window.injected=true</script>"}},
        now=now,
    )
    assert valid_failure["status"] == "fail"
    failure_gates = security_gates_from_report(
        valid_failure,
        include_report_gate=False,
    )
    assert any(
        gate["code"] == "unsafe_artifact_rendering_detected" and gate["status"] == "fail"
        for gate in failure_gates
    )

    malformed = {**valid_pass, "schema_version": "unrecognized"}
    malformed_gates = security_gates_from_report(
        malformed,
        include_report_gate=False,
    )
    assert len(malformed_gates) == 1
    assert malformed_gates[0]["code"] == "security_assurance_failed"
    assert malformed_gates[0]["status"] == "fail"
    assert malformed_gates[0]["blocking"] is True
