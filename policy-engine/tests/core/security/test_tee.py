from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from polisyos.core.security.tee import (
    AttestationFetchError,
    AttestationPolicy,
    AttestationStatus,
    SEVSNPVerifier,
    TEEPlatform,
)


def _report_dict(*, measurement: str = "abc123", age_seconds: int = 30) -> dict[str, object]:
    return {
        "platform": TEEPlatform.SEV_SNP.value,
        "measurement": measurement,
        "host_data": "host-hash",
        "guest_svn": 5,
        "tcb_version": 7,
        "report_data_hex": "001122",
        "report_hash": "report-hash",
        "signature_validated": True,
        "collected_at": (
            datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        ).isoformat(),
    }


def test_verify_with_expected_measurement_passes(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_report_dict(measurement="feedbeef")), encoding="utf-8")

    verifier = SEVSNPVerifier(report_path=report_path)
    report = verifier.fetch_report(nonce=bytes.fromhex("00"))
    result = verifier.verify(
        report,
        AttestationPolicy(
            expected_measurements=("feedbeef",),
            require_host_data_match=True,
            expected_host_data="host-hash",
            min_tcb_version=3,
            min_guest_svn=1,
        ),
        nonce=bytes.fromhex("00"),
    )
    assert result.status == AttestationStatus.VERIFIED


def test_verify_rejects_old_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_report_dict(age_seconds=1000)), encoding="utf-8")

    verifier = SEVSNPVerifier(report_path=report_path)
    report = verifier.fetch_report()
    result = verifier.verify(report, AttestationPolicy(max_report_age_seconds=10))
    assert result.status == AttestationStatus.FAILED
    assert any("expired" in item for item in result.errors)


def test_verify_rejects_measurement_mismatch(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_report_dict(measurement="deadbeef")), encoding="utf-8")

    verifier = SEVSNPVerifier(report_path=report_path)
    report = verifier.fetch_report()
    result = verifier.verify(report, AttestationPolicy(expected_measurements=("feedbeef",)))
    assert result.status == AttestationStatus.FAILED
    assert any("measurement" in item for item in result.errors)


def test_fetch_report_nonce_mismatch_raises(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report = _report_dict()
    report["report_data_hex"] = "aaaaaaaa"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    verifier = SEVSNPVerifier(report_path=report_path)
    with pytest.raises(AttestationFetchError):
        verifier.fetch_report(nonce=b"\x00\x11")
